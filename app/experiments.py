"""Persistent developer experiments built on the production review queue."""
import html
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .automatic_review import REVIEW_VERSION
from .evidence import PROMPT_VERSION
from .evaluation.benchmark import evaluate
from .retrieval import VERSION as RETRIEVAL_VERSION
from .text_io import read_text_compat, write_text_utf8


CONTEXT_CONFIGS = {
    'bm25': {'label': 'A · 现有 BM25', 'review_mode': 'retrieval', 'description': 'BM25 命中单元，并补齐不完整句子的同页块。'},
    'bm25_neighbor': {'label': 'B · BM25 + 邻近上下文', 'review_mode': 'retrieval', 'description': '在 A 的候选上加入同页前后完整段落；整段纳入或整段丢弃。'},
    'deep': {'label': 'C · 深度核查', 'review_mode': 'deep', 'description': '复用全文或大范围分块、验证后分层合并的固定路径。'},
}

ARCHITECTURE = [
    dict(id='interaction', name='用户交互层', responsibility='导入稿件与 PDF、模型连接、任务控制、结果阅读和导出。', files=['web/index.html','web/app.js','web/automatic-review.js'], input='用户稿件、来源文件与运行选项', output='本地 API 请求与可视化结果', llm=False, tokens=False),
    dict(id='citation', name='引用识别与来源匹配', responsibility='识别作者—年份引用，划定主张范围，并按经验证的作者与年份匹配来源。', files=['app/citations.py','app/matching.py','app/tasks.py'], input='稿件正文与来源身份', output='引用位置、成员和身份状态', llm=False, tokens=False),
    dict(id='pdf', name='PDF 解析与证据索引', responsibility='提取逐字文本、物理页和字符坐标，并建立可复用的磁盘索引。', files=['app/pdf_index.py','app/evidence_storage.py'], input='可读取 PDF', output='带指纹、块 ID 和坐标的证据包', llm=False, tokens=False),
    dict(id='retrieval', name='证据检索与上下文构建', responsibility='按固定实验配置构造候选证据或全文分块，不自行选择策略。', files=['app/retrieval.py','app/evidence_selection.py','app/automatic_review.py'], input='当前主张与已确认来源', output='可追踪的证据块和上下文摘要', llm=False, tokens=False),
    dict(id='agent', name='Review Agent 语义核查', responsibility='逐子观点和逐来源判断支持关系，输出证据引用与问题类型。', files=['app/agent/review_agent.py','app/agent/schemas.py','app/agent/runner.py'], input='主张、上下文、来源身份、候选证据和规则', output='结构化逐源判断与共同结论', llm=True, tokens=True),
    dict(id='verification', name='确定性证据验证', responsibility='校验来源归属、逐字摘录、PDF 指纹、块 ID 和页面坐标。', files=['app/evidence.py','app/evidence_identity.py'], input='Agent 判断和证据引用', output='已验证证据或明确的定位失败', llm=False, tokens=False),
    dict(id='quality', name='任务质量评估', responsibility='检查完成度、来源、模型失败、证据真实性、定位和人工复核需求。', files=['app/evaluation/task_quality.py'], input='任务、检查记录和证据结果', output='不代表语义准确率的质量摘要', llm=False, tokens=False),
    dict(id='reporting', name='结果、历史与报告', responsibility='持久化任务、恢复历史，生成工作台、JSON、Markdown 和独立 ZIP 报告。', files=['app/tasks.py','app/report_archive.py','web/evidence.js'], input='核查任务和质量摘要', output='可复查、可导出的报告', llm=False, tokens=False),
]

BENCHMARK = dict(id='benchmark', name='独立 Benchmark Evaluation', responsibility='使用人工金标离线计算分类、错误识别、检索、定位和运行指标；不在普通用户流水线中执行。', files=['app/evaluation/benchmark.py'], input='版本化人工金标与一个或多个预测结果', output='JSON/HTML 指标、混淆矩阵和逐样本对比', llm=False, tokens=False)

LEGACY_COMPARISON = [
    ('调用链','固定管线直接进入旧核查函数','固定管线通过 AgentRunner 进入 Review Agent','重构'),
    ('语义规则','沿用相同 REVIEW_PROMPT 规则','沿用相同 REVIEW_PROMPT 规则','沿用'),
    ('输入输出契约','由 automatic_review 内部字典约定','ReviewInput/ReviewOutput 显式校验','新增'),
    ('候选证据检索','BM25，可对无法判断项进行第二轮扩展','BM25 单轮语义执行；消融配置显式记录','重构'),
    ('深度核查','全文分块、验证后合并','沿用同一深度核查实现','沿用'),
    ('原文和位置验证','程序验证逐字原文与 PDF 坐标','沿用同一 EvidenceService 验证','沿用'),
    ('缓存与任务恢复','持久化检查点、依赖缓存和重试保护','沿用，并在 Agent 结果中记录缓存状态','沿用'),
    ('运行记录','任务级状态、错误和用量','增加 Agent 决策、耗时和轻量流程事件','新增'),
    ('Evaluation','没有统一的最终质量摘要','任务质量摘要和独立人工金标 Benchmark','新增'),
    ('可测试性','主要测试整体核查函数','Agent 契约、执行器、上下文配置可独立测试','新增'),
    ('可维护性','语义调用与主流程耦合较紧，但既有缓存和恢复逻辑完整','语义契约、运行连接和评估边界拆分，既有缓存和恢复逻辑沿用','重构'),
]


def _safe_id(value, label='实验 ID'):
    if not re.fullmatch(r'[a-f0-9]{32}', str(value or '')):
        raise ValueError(label + '无效')
    return value


class ExperimentStore:
    def __init__(self, root, tasks, assets, checks, model_settings):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.tasks=tasks;self.assets=assets;self.checks=checks;self.model_settings=model_settings

    def path(self, experiment_id):
        return self.root/(_safe_id(experiment_id)+'.json')

    def _save(self, record):
        target=self.path(record['id']);temporary=target.with_suffix('.tmp')
        write_text_utf8(temporary,json.dumps(record,ensure_ascii=False,indent=2));temporary.replace(target)

    def _load(self, experiment_id):
        try:return json.loads(read_text_compat(self.path(experiment_id)))
        except FileNotFoundError:raise ValueError('实验不存在') from None

    def list(self):
        rows=[]
        for path in self.root.glob('*.json'):
            try:
                record=json.loads(read_text_compat(path));rows.append(self.refresh(record,save=False))
            except (ValueError,OSError,KeyError,TypeError):continue
        return sorted(rows,key=lambda row:row.get('created_at',''),reverse=True)

    def get(self, experiment_id):
        return self.refresh(self._load(experiment_id))

    def create(self, data):
        if data.get('confirmed_paid_calls') is not True:
            raise ValueError('启动实验前必须明确确认将调用付费模型 API')
        task=self.tasks.get(_safe_id(data.get('task_id'),'任务 ID'))
        configurations=data.get('configurations')
        if not isinstance(configurations,list) or not 1<=len(configurations)<=6:
            raise ValueError('实验配置数量应为 1—6 个')
        normalized=[];labels=set()
        for config in configurations:
            if not isinstance(config,dict):raise ValueError('实验配置无效')
            execution=config.get('execution_mode');context=config.get('context_mode')
            if execution not in {'legacy','agent'} or context not in CONTEXT_CONFIGS:raise ValueError('实验执行模式或上下文方案无效')
            label=str(config.get('label') or (execution+' · '+CONTEXT_CONFIGS[context]['label']))[:100]
            if label in labels:raise ValueError('实验配置名称重复')
            labels.add(label);normalized.append(dict(label=label,execution_mode=execution,context_mode=context,review_mode=CONTEXT_CONFIGS[context]['review_mode']))
        source_ids=[source['id'] for source in task.get('sources',[]) if source.get('id')]
        if not source_ids:raise ValueError('任务没有可复用的来源')
        scope=data.get('scope','all');location_limit=3 if scope=='3' else None
        experiment_id=uuid.uuid4().hex;snapshot=self.model_settings.public()
        record=dict(schema_version=1,id=experiment_id,name=str(data.get('name') or '架构对照实验')[:120],created_at=datetime.now(timezone.utc).isoformat(),kind='live',task_id=task['id'],dataset_version=str(data.get('dataset_version') or ('task-'+task['id'][:8]+'-v1'))[:120],sample_count=min(3,len(task.get('locations',[]))) if location_limit else len(task.get('locations',[])),scope=scope,model={k:snapshot.get(k) for k in ('provider','model','base_url')},prompt_version=PROMPT_VERSION,review_version=REVIEW_VERSION,retrieval_version=RETRIEVAL_VERSION,arms=[],gold=None)
        self._save(record)
        try:
            for config in normalized:
                job=self.checks.start(task['text'],source_ids,review_mode=config['review_mode'],location_limit=location_limit,max_requests=data.get('max_requests'),token_budget=data.get('token_budget'),execution_mode=config['execution_mode'],context_mode=config['context_mode'])
                self.checks._update(job['id'],experiment_id=experiment_id,experiment_arm=config['label'])
                record['arms'].append({**config,'check_id':job['id']})
                self._save(record)
        except Exception:
            self._save(record);raise
        return self.refresh(record)

    def attach_gold(self, experiment_id, document):
        record=self._load(experiment_id)
        if not isinstance(document,(dict,list)):raise ValueError('人工金标必须为 JSON 对象或列表')
        from .evaluation.benchmark import rows
        rows(document)  # validates shape when evaluated; sample IDs are checked below.
        record['gold']=document
        if isinstance(document,dict) and document.get('dataset_version'):
            record['dataset_version']=str(document['dataset_version'])[:120]
        self._save(record);return self.refresh(record)

    def import_document(self, document):
        if not isinstance(document,dict):raise ValueError('实验导入文件必须为 JSON 对象')
        if document.get('kind') in {'ab_comparison','experiment_comparison','human_gold_benchmark'}:
            result=document
        else:
            gold=document.get('gold');predictions=document.get('predictions')
            if not isinstance(gold,(dict,list)) or not isinstance(predictions,dict) or not predictions:raise ValueError('导入文件需包含 gold 和 predictions')
            result=dict(kind='experiment_comparison',dataset_version=document.get('dataset_version'),arms={name:evaluate(gold,prediction,document.get('k',5)) for name,prediction in predictions.items()})
        experiment_id=uuid.uuid4().hex
        record=dict(schema_version=1,id=experiment_id,name=str(document.get('name') or '导入的实验结果')[:120],created_at=datetime.now(timezone.utc).isoformat(),kind='imported',dataset_version=document.get('dataset_version'),sample_count=(result.get('counts') or {}).get('samples'),arms=[],result=result)
        self._save(record);return record

    def refresh(self, record, save=True):
        if record.get('kind')!='live':return record
        arm_results={};states=[]
        for arm in record.get('arms',[]):
            try:
                job=self.checks.get(arm['check_id']);states.append(job.get('status'))
                arm['status']=job.get('status');arm['task_id']=job.get('task_id');arm['model_requests']=job.get('budget_usage',{}).get('requests',0);arm['tokens']=job.get('budget_usage',{}).get('actual_tokens');arm['duration_seconds']=(job.get('evaluation') or {}).get('duration_seconds');arm['cache_usage']='reused' if arm['model_requests']==0 and job.get('completed',0) else 'new_requests' if arm['model_requests'] else 'none'
                if record.get('gold') is not None and job.get('task_id'):
                    arm_results[arm['label']]=evaluate(record['gold'],self.tasks.get(job['task_id']))
            except ValueError:
                arm['status']='missing';states.append('missing')
        record['status']='running' if any(state in {'queued','running'} for state in states) else 'completed' if states and all(state=='completed' for state in states) else 'partial' if states else 'empty'
        record['result']=dict(kind='experiment_comparison',dataset_version=record.get('dataset_version'),prompt_version=record.get('prompt_version'),model=record.get('model'),positive_class='错误引用 = 部分支持、不支持、存在矛盾；支持和无法判断不是正类',arms=arm_results) if arm_results else None
        if save:self._save(record)
        return record

    def trace(self, experiment_id):
        record=self.get(experiment_id);arms=[]
        for arm in record.get('arms',[]):
            try:
                job=self.checks.get(arm['check_id'])
                arms.append(dict(label=arm['label'],execution_mode=arm['execution_mode'],context_mode=arm['context_mode'],status=job.get('status'),task_id=job.get('task_id'),trace=job.get('trace',[]),errors=job.get('errors',[])))
            except ValueError:arms.append(dict(label=arm['label'],status='missing',trace=[],errors=['检查记录不存在']))
        return dict(experiment_id=record['id'],arms=arms)

    def export_json(self, experiment_id):
        return json.dumps(self.get(experiment_id),ensure_ascii=False,indent=2).encode()

    def export_html(self, experiment_id):
        record=self.get(experiment_id);payload=html.escape(json.dumps(record,ensure_ascii=False,indent=2))
        return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>BackedUp 实验报告</title><style>body{font:15px/1.65 system-ui;max-width:1120px;margin:40px auto;padding:0 24px;color:#18222f}pre{white-space:pre-wrap;background:#f4f6f9;border:1px solid #dfe4eb;border-radius:14px;padding:22px;overflow:auto}</style><h1>'+html.escape(record.get('name','BackedUp 实验报告'))+'</h1><p>仅展示保存的真实运行或导入结果；缺少人工金标时不计算语义准确率。</p><pre>'+payload+'</pre></html>').encode()
