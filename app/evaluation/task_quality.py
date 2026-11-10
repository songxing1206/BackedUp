"""Per-run completeness and provenance checks; no semantic accuracy claim."""
from datetime import datetime, timezone


def evaluate_task(task, job):
    ordered = [l['id'] for l in task.get('locations', []) if not job.get('location_ids') or l['id'] in job['location_ids']]
    selected = set(ordered[:job['location_limit']] if job.get('location_limit') else ordered)
    locations = {l['id']: l for l in task.get('locations', []) if l['id'] in selected}
    reviews = {r['location_id']: r for r in task.get('evidence_review', {}).get('locations', []) if r.get('location_id') in locations}
    counts = dict(required=len(locations), completed=0, source_unconfirmed=0, model_failed=0,
                  no_evidence=0, evidence_unverified=0, localization_failed=0, human_review=0)
    details = []
    for lid, loc in locations.items():
        review = reviews.get(lid, {})
        identity = any(m.get('match', {}).get('status') != 'matched' for m in loc.get('members', []))
        judgments = [j for c in review.get('claims', []) for j in c.get('source_judgments', [])]
        completed = review.get('state') == 'complete' and bool(judgments)
        model_failed = review.get('agent_result', {}).get('model_status') == 'incomplete' if isinstance(review.get('agent_result'), dict) else False
        model_failed = model_failed or any(str(error).startswith(lid + '：') for error in job.get('errors', [])) or any(j.get('verification_error') for j in judgments)
        no_evidence = any(j.get('status') in {'支持', '部分支持', '存在矛盾'} and not j.get('evidence') for j in judgments)
        evidence_unverified = any(e.get('validation') not in {'verified', 'text_verified'} for j in judgments for e in j.get('evidence', []))
        localization_failed = any(e.get('location_state') != 'mapped' for j in judgments for e in j.get('evidence', []))
        human = identity or not completed or no_evidence or evidence_unverified or localization_failed or any(j.get('status') != '支持' for j in judgments)
        for key, value in [('completed', completed), ('source_unconfirmed', identity), ('model_failed', model_failed),
                           ('no_evidence', no_evidence), ('evidence_unverified', evidence_unverified),
                           ('localization_failed', localization_failed), ('human_review', human)]:
            counts[key] += bool(value)
        details.append(dict(location_id=lid, complete=completed, source_unconfirmed=identity,
                            model_failed=model_failed, no_evidence=no_evidence,
                            evidence_unverified=evidence_unverified, localization_failed=localization_failed,
                            human_review=human))
    try:
        duration = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(job['created_at'])).total_seconds())
    except (KeyError, ValueError, TypeError):
        duration = None
    usage = job.get('budget_usage', {})
    return dict(kind='task_quality', execution_mode=job.get('execution_mode', 'legacy'), review_mode=job.get('review_mode'), context_mode=job.get('context_mode', 'deep' if job.get('review_mode') == 'deep' else 'bm25'),
                counts=counts, model_requests=usage.get('requests', 0), total_tokens=usage.get('actual_tokens'),
                reserved_tokens=usage.get('reserved_tokens'), duration_seconds=round(duration, 2) if duration is not None else None,
                job_status=job.get('status'), details=details,
                note='仅检查完成度与证据可追溯性，不衡量语义判断准确率。')
