"""Offline comparison against independently annotated citation gold data."""
import argparse
import html
import json
from pathlib import Path

LABELS = ('支持', '部分支持', '不支持', '存在矛盾', '无法判断')
ERROR_LABELS = {'部分支持', '不支持', '存在矛盾'}


def rows(document):
    if isinstance(document, list):
        return document
    if not isinstance(document, dict):
        raise ValueError('评估输入须为对象或样本列表')
    if isinstance(document.get('samples'), list):
        return document['samples']
    if isinstance(document.get('predictions'), list):
        return document['predictions']
    # Existing task report: one location and one bibliographic source per sample.
    reviews = {r['location_id']: r for r in document.get('evidence_review', {}).get('locations', [])}
    rows = []
    for loc in document.get('locations', []):
        review = reviews.get(loc['id'], {})
        for member in loc.get('members', []):
            sid = member.get('match', {}).get('source_id')
            if not sid:
                sid = member.get('id', 'unmatched')
            judgments = [j for c in review.get('claims', []) for j in c.get('source_judgments', []) if j.get('source_id') == sid]
            statuses = [j.get('status') for j in judgments]
            if not statuses:
                status = None
            elif '无法判断' in statuses:
                status = '无法判断'
            elif '存在矛盾' in statuses:
                status = '存在矛盾'
            elif len(set(statuses)) == 1:
                status = statuses[0]
            else:
                status = '部分支持'
            rows.append(dict(sample_id=f"{loc['id']}::{sid}", location_id=loc['id'], source_id=sid,
                             status=status, source_status=member.get('match', {}).get('status'),
                             evidence=[dict(id=e.get('block_id'), page_index=(e.get('regions') or [{}])[0].get('page_index'),
                                            validation=e.get('validation'), location_state=e.get('location_state'))
                                       for j in judgments for e in j.get('evidence', [])],
                             model_status='completed' if judgments else 'failed',
                             requires_human_review=review.get('state') != 'complete' or status == '无法判断'))
    return rows


def _index(rows, name):
    index = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('sample_id'), str) or not row['sample_id']:
            raise ValueError(name + '缺少 sample_id')
        if row['sample_id'] in index:
            raise ValueError(name + '有重复 sample_id: ' + row['sample_id'])
        index[row['sample_id']] = row
    return index


def _ratio(a, b):
    return round(a / b, 4) if b else None


def evaluate(gold_document, predictions_document, k=5):
    if type(k) is not int or k < 1:
        raise ValueError('K 必须为正整数')
    gold = _index(rows(gold_document), '金标')
    predicted = _index(rows(predictions_document), '预测')
    counts = dict(samples=len(gold), matched=0, missing_predictions=0, completed_predictions=0,
                  technical_failures=0, source_missing=0, human_review=0, labeled=0,
                  invalid_labels=0, invalid_prediction_labels=0)
    matrix = {label: {other: 0 for other in LABELS} for label in LABELS}
    correct = 0; tp = fp = fn = 0; retrieval_hits = retrieval_total = 0
    localization_hits = localization_total = 0
    token_values = []; request_values = []; duration_values = []; sample_results = []
    for sample_id, g in gold.items():
        p = predicted.get(sample_id)
        if p is None:
            counts['missing_predictions'] += 1
            p = {}
        else:
            counts['matched'] += 1
        if p.get('status') is not None and p['status'] not in LABELS:
            counts['invalid_prediction_labels'] += 1
        failed = not p or p.get('model_status') in {'failed', 'incomplete', 'error'} or p.get('status') not in LABELS
        counts['technical_failures'] += failed
        counts['source_missing'] += p.get('source_status') in {'unmatched', 'missing_attachment', 'needs_assignment'}
        counts['completed_predictions'] += not failed and p.get('source_status') not in {'unmatched', 'missing_attachment', 'needs_assignment'}
        counts['human_review'] += bool(p.get('requires_human_review'))
        label = g.get('status')
        if label is not None:
            if label not in LABELS:
                counts['invalid_labels'] += 1
                continue
            counts['labeled'] += 1
            pred = p.get('status')
            if pred in LABELS and not failed:
                matrix[label][pred] += 1
                correct += pred == label
            gold_error = label in ERROR_LABELS
            predicted_error = pred in ERROR_LABELS and not failed
            tp += gold_error and predicted_error
            fp += not gold_error and predicted_error
            fn += gold_error and not predicted_error
        gold_evidence = g.get('evidence')
        if isinstance(gold_evidence, list) and gold_evidence:
            expected = {e.get('id') for e in gold_evidence if isinstance(e, dict) and e.get('id')}
            if expected:
                retrieval_total += 1
                actual = {e.get('id') for e in p.get('evidence', [])[:k] if isinstance(e, dict)}
                retrieval_hits += bool(expected & actual)
            gold_pages = {(e.get('id'), e.get('page_index')) for e in gold_evidence if isinstance(e, dict) and e.get('id') and e.get('page_index') is not None}
            if gold_pages:
                localization_total += len(gold_pages)
                actual_pages = {(e.get('id'), e.get('page_index')) for e in p.get('evidence', []) if isinstance(e, dict) and e.get('location_state') == 'mapped' and e.get('validation') == 'verified'}
                localization_hits += len(gold_pages & actual_pages)
        for key, values in [('tokens', token_values), ('requests', request_values), ('duration_seconds', duration_values)]:
            if isinstance(p.get(key), (int, float)) and not isinstance(p[key], bool):
                values.append(p[key])
        sample_results.append(dict(sample_id=sample_id,gold_status=label,predicted_status=p.get('status'),
                                   correct=bool(label in LABELS and p.get('status')==label and not failed),
                                   technical_failure=bool(failed),source_status=p.get('source_status'),
                                   requires_human_review=bool(p.get('requires_human_review')),
                                   evidence_gold=len(g.get('evidence') or []) if isinstance(g.get('evidence'),list) else None,
                                   evidence_predicted=len(p.get('evidence') or []) if isinstance(p.get('evidence'),list) else 0))
    per_label = {}
    for label in LABELS:
        t = matrix[label][label]
        support = sum(1 for g in gold.values() if g.get('status') == label)
        predicted_count = sum(matrix[g][label] for g in LABELS)
        precision = _ratio(t, predicted_count)
        recall = _ratio(t, support)
        per_label[label] = dict(support=support, precision=precision, recall=recall,
                                f1=_ratio(2 * t, predicted_count + support))
    macro = [v['f1'] for v in per_label.values() if v['support'] and v['f1'] is not None]
    error_precision = _ratio(tp, tp + fp); error_recall = _ratio(tp, tp + fn)
    dataset_version=gold_document.get('dataset_version') if isinstance(gold_document,dict) else None
    benchmark_config=predictions_document.get('benchmark_config') if isinstance(predictions_document,dict) else None
    return dict(kind='human_gold_benchmark', dataset_version=dataset_version, sample_matching='exact sample_id', benchmark_config=benchmark_config, counts=counts,
                classification=dict(accuracy=_ratio(correct, counts['labeled']), macro_f1=_ratio(sum(macro), len(macro)),
                                    eligible=counts['labeled'],coverage=_ratio(counts['labeled'],counts['samples']),per_label=per_label, confusion=matrix),
                error_detection=dict(precision=error_precision, recall=error_recall,
                                     f1=_ratio(2 * tp, 2 * tp + fp + fn),positive_class=list(sorted(ERROR_LABELS)),negative_class=['支持','无法判断'],tp=tp,fp=fp,fn=fn),
                retrieval=dict(k=k, recall_at_k=_ratio(retrieval_hits, retrieval_total), eligible=retrieval_total),
                localization=dict(accuracy=_ratio(localization_hits, localization_total), eligible=localization_total),
                operations=dict(completion_rate=_ratio(counts['completed_predictions'], counts['samples']),
                                technical_failure_rate=_ratio(counts['technical_failures'], counts['samples']),
                                average_tokens=_ratio(sum(token_values), len(token_values)),
                                average_requests=_ratio(sum(request_values), len(request_values)),
                                average_duration_seconds=_ratio(sum(duration_values), len(duration_values)),
                                usage_samples=dict(tokens=len(token_values), requests=len(request_values),
                                                   duration=len(duration_values))), samples=sample_results,
                note='人工金标指标；缺失预测及技术失败计入分母。无相应金标的指标为 null。')


def compare(gold, legacy, agent, k=5):
    def config(document):
        if not isinstance(document, dict):
            return None
        value = document.get('benchmark_config') or document.get('evidence_review', {}).get('model')
        if not isinstance(value, dict):
            return None
        return {key: value.get(key) for key in ('provider', 'endpoint', 'name', 'review_mode') if value.get(key) is not None} or None
    old_config, new_config = config(legacy), config(agent)
    if old_config and new_config and old_config != new_config:
        raise ValueError('A/B 模型与审查配置不一致，不能直接比较')
    a = evaluate(gold, legacy, k); b = evaluate(gold, agent, k)
    return dict(kind='ab_comparison', sample_matching='exact sample_id; same gold sample set',
                dataset_version=gold.get('dataset_version') if isinstance(gold,dict) else None,
                comparable_config=bool(old_config and new_config), config=old_config if old_config == new_config else None,
                legacy=a, agent=b)


def compare_many(gold, predictions, k=5):
    """Evaluate fixed context/architecture arms with one gold sample index."""
    if not isinstance(predictions,dict) or not predictions:raise ValueError('实验预测配置不能为空')
    results={name:evaluate(gold,document,k) for name,document in predictions.items()}
    return dict(kind='experiment_comparison',dataset_version=gold.get('dataset_version') if isinstance(gold,dict) else None,
                sample_matching='exact sample_id; missing and failed predictions remain in denominators',
                error_positive_class=list(sorted(ERROR_LABELS)),arms=results)


def write_reports(result, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix('.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    pretty = html.escape(json.dumps(result, ensure_ascii=False, indent=2))
    arms=result.get('arms') or ({'Legacy':result.get('legacy'),'V0.5 Agent':result.get('agent')} if result.get('kind')=='ab_comparison' else {'结果':result})
    cards=[]
    for name,value in arms.items():
        if not isinstance(value,dict):continue
        classification=value.get('classification',{});operations=value.get('operations',{});error=value.get('error_detection',{})
        fmt=lambda number:'暂无' if number is None else str(round(number*100,2))+'%'
        cards.append('<article><h2>'+html.escape(str(name))+'</h2><dl><dt>Accuracy</dt><dd>'+fmt(classification.get('accuracy'))+'</dd><dt>Macro-F1</dt><dd>'+fmt(classification.get('macro_f1'))+'</dd><dt>错误引用 F1</dt><dd>'+fmt(error.get('f1'))+'</dd><dt>完成率</dt><dd>'+fmt(operations.get('completion_rate'))+'</dd><dt>平均 Token</dt><dd>'+html.escape(str(operations.get('average_tokens') if operations.get('average_tokens') is not None else '未记录'))+'</dd></dl></article>')
    output.with_suffix('.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>BackedUp Benchmark</title><style>body{font:15px/1.6 system-ui;max-width:1100px;margin:40px auto;padding:0 24px;color:#1d2937}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}article,pre{background:#f6f8fb;border:1px solid #dfe5ec;border-radius:14px;padding:20px}dl{display:grid;grid-template-columns:1fr auto;gap:8px}dt,dd{margin:0}dd{font-weight:700}pre{white-space:pre-wrap;overflow:auto}</style><h1>BackedUp 人工金标评估</h1><p>缺失预测和技术失败保留在分母；没有对应金标的指标显示为“暂无”。</p><div class="grid">'+''.join(cards)+'</div><details><summary>完整 JSON</summary><pre>'+pretty+'</pre></details></html>', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Offline human-gold benchmark; no model calls')
    parser.add_argument('--gold', required=True)
    parser.add_argument('--legacy', required=True)
    parser.add_argument('--agent')
    parser.add_argument('--output', required=True)
    parser.add_argument('--k', type=int, default=5)
    args = parser.parse_args()
    read = lambda path: json.loads(Path(path).read_text(encoding='utf-8'))
    result = compare(read(args.gold), read(args.legacy), read(args.agent), args.k) if args.agent else evaluate(read(args.gold), read(args.legacy), args.k)
    write_reports(result, args.output)


if __name__ == '__main__':
    main()
