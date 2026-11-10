"""Boundaries between retrieval, semantic review and verified PDF evidence."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewInput:
    location_id: str
    sentence: str
    context: str
    sources: tuple
    model: dict
    rules: str
    phase: str = 'review'

    @classmethod
    def from_payload(cls, payload, model, rules):
        if not isinstance(payload, dict) or not isinstance(payload.get('location_id'), str) or not payload['location_id']:
            raise ValueError('Agent 输入缺少引用 ID')
        if not isinstance(payload.get('sentence'), str) or not payload['sentence'].strip():
            raise ValueError('Agent 输入缺少引用原句')
        if not isinstance(payload.get('context'), str):
            raise ValueError('Agent 输入缺少引用上下文')
        sources = payload.get('sources', [])
        if not sources and payload.get('source_ids'):
            sources = [dict(id=sid, sha256='verified_candidate', blocks=[]) for sid in payload.get('source_ids', [])]
        if not isinstance(sources, list) or any(not isinstance(s, dict) or not s.get('id') or not s.get('sha256') or not isinstance(s.get('blocks'), list) for s in sources):
            raise ValueError('Agent 来源身份或证据格式无效')
        for source in sources:
            if any(not isinstance(b, dict) or not b.get('id') or not isinstance(b.get('text'), str) for b in source['blocks']):
                raise ValueError('Agent 候选证据缺少 ID 或原文')
        if not isinstance(model, dict) or not isinstance(rules, str):
            raise ValueError('Agent 模型配置或规则无效')
        return cls(payload['location_id'], payload['sentence'], payload['context'], tuple(sources), dict(model), rules, payload.get('phase', 'review'))


@dataclass(frozen=True)
class SourceDecision:
    location_id: str
    source_id: str
    status: str
    reason: str
    issue_types: tuple
    evidence_ids: tuple
    requires_human_review: bool
    model_status: str


@dataclass(frozen=True)
class ReviewOutput:
    location_id: str
    decisions: tuple
    combined_status: str
    model_status: str
    tokens: int | None
    elapsed_seconds: float

    def as_dict(self):
        return dict(location_id=self.location_id, combined_status=self.combined_status,
                    model_status=self.model_status, tokens=self.tokens,
                    elapsed_seconds=self.elapsed_seconds,
                    decisions=[dict(location_id=d.location_id, source_id=d.source_id,
                                    status=d.status, reason=d.reason, issue_types=list(d.issue_types),
                                    evidence_ids=list(d.evidence_ids),
                                    requires_human_review=d.requires_human_review,
                                    model_status=d.model_status) for d in self.decisions])
