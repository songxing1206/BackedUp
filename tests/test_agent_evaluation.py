import unittest
from app.agent.review_agent import ReviewAgent
from app.agent.schemas import ReviewInput
from app.evaluation.benchmark import evaluate, compare
from app.evaluation.task_quality import evaluate_task


class AgentEvaluationTests(unittest.TestCase):
    def test_agent_input_and_output(self):
        payload = dict(location_id='L1', sentence='A claim (Smith, 2023).', context='A claim.',
                       sources=[dict(id='S1', sha256='a' * 64, blocks=[dict(id='B1', text='A claim.', physical_page=1)])])
        def fake(prompt, request):
            self.assertEqual(request['sources'][0]['blocks'][0]['id'], 'B1')
            return dict(claims=[dict(id='P1', text='A claim', source_judgments=[dict(source_id='S1', status='支持', reason='direct evidence',
                issue_types=[], evidence=[dict(source_id='S1', block_id='B1', quote='A claim.')])])], combined=dict(status='支持', reason='yes'))
        row = ReviewAgent(fake).execute(payload, dict(provider='fake'), 'rules')
        output = ReviewAgent.output('L1', row, 42, .4)
        self.assertEqual(output.decisions[0].evidence_ids, ('B1',))
        self.assertEqual(output.tokens, 42)
        self.assertFalse(output.decisions[0].requires_human_review)
        with self.assertRaisesRegex(ValueError, '未提供的来源'):
            ReviewAgent(lambda *_: dict(claims=[dict(source_judgments=[dict(source_id='wrong')])])).execute(payload, {}, 'rules')
        with self.assertRaisesRegex(ValueError, '缺少引用'):
            ReviewInput.from_payload({**payload, 'sentence': ''}, {}, 'rules')

    def test_task_quality_separates_identity_semantics_and_location(self):
        task = dict(locations=[dict(id='L1', members=[dict(match=dict(status='matched'))]),
                               dict(id='L2', members=[dict(match=dict(status='unmatched'))])],
                    evidence_review=dict(locations=[dict(location_id='L1', state='complete', claims=[dict(source_judgments=[dict(status='支持', evidence=[dict(validation='text_verified', location_state='unmapped')])])])]))
        job = dict(created_at='2026-01-01T00:00:00+00:00', status='partial', execution_mode='agent',
                   budget_usage=dict(requests=2, actual_tokens=123))
        result = evaluate_task(task, job)
        self.assertEqual(result['counts']['source_unconfirmed'], 1)
        self.assertEqual(result['counts']['localization_failed'], 1)
        self.assertEqual(result['counts']['evidence_unverified'], 0)
        self.assertEqual(result['total_tokens'], 123)

    def test_benchmark_missing_and_unknown_do_not_inflate_accuracy(self):
        gold = dict(samples=[dict(sample_id='a', status='支持', evidence=[dict(id='B1', page_index=0)]),
                             dict(sample_id='b', status='不支持'), dict(sample_id='c', status='无法判断')])
        predictions = dict(predictions=[dict(sample_id='a', status='支持', model_status='completed',
            evidence=[dict(id='B1', page_index=0, validation='verified', location_state='mapped')], tokens=10, requests=1, duration_seconds=2),
            dict(sample_id='b', status='无法判断', model_status='failed')])
        result = evaluate(gold, predictions)
        self.assertEqual(result['classification']['accuracy'], 1 / 3 if 1 / 3 == round(1 / 3, 4) else .3333)
        self.assertEqual(result['counts']['technical_failures'], 2)
        self.assertEqual(result['retrieval']['recall_at_k'], 1)
        self.assertEqual(result['localization']['accuracy'], 1)
        self.assertEqual(result['operations']['usage_samples']['tokens'], 1)
        self.assertEqual(compare(gold, predictions, predictions)['agent']['counts']['samples'], 3)
        with self.assertRaisesRegex(ValueError, '配置不一致'):
            compare(gold, {**predictions, 'benchmark_config': {'name': 'old'}},
                    {**predictions, 'benchmark_config': {'name': 'new'}})

    def test_optional_gold_invalid_labels_and_duplicate_ids(self):
        result = evaluate([dict(sample_id='x', status='bogus'), dict(sample_id='y')], [])
        self.assertEqual(result['counts']['invalid_labels'], 1)
        self.assertIsNone(result['classification']['accuracy'])
        self.assertIsNone(result['retrieval']['recall_at_k'])
        with self.assertRaisesRegex(ValueError, '重复'):
            evaluate([dict(sample_id='x'), dict(sample_id='x')], [])
        abnormal = evaluate([dict(sample_id='x', status='支持')], [dict(sample_id='x', status='bad')])
        self.assertEqual(abnormal['counts']['invalid_prediction_labels'], 1)
        self.assertEqual(abnormal['operations']['completion_rate'], 0)

    def test_old_task_report_adapter(self):
        old = dict(locations=[dict(id='L1', members=[dict(id='M1', match=dict(status='matched', source_id='S1'))])],
                   evidence_review=dict(locations=[dict(location_id='L1', state='complete', claims=[dict(source_judgments=[dict(source_id='S1', status='支持', evidence=[])])])]))
        result = evaluate([dict(sample_id='L1::S1', status='支持')], old)
        self.assertEqual(result['classification']['accuracy'], 1)

    def test_localization_counts_every_gold_evidence(self):
        gold = [dict(sample_id='a', evidence=[dict(id='B1', page_index=0), dict(id='B2', page_index=1)])]
        pred = [dict(sample_id='a', status='支持', evidence=[dict(id='B1', page_index=0,
                 validation='verified', location_state='mapped')])]
        result = evaluate(gold, pred)
        self.assertEqual(result['localization']['eligible'], 2)
        self.assertEqual(result['localization']['accuracy'], .5)
