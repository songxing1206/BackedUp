import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.evaluation.benchmark import compare_many
from app.evidence_selection import select_units, select_units_with_neighbors
from app.experiments import ExperimentStore
from app.retrieval import Retriever
from app.tasks import TaskStore
from test_evidence_http import HttpTests
import server


class FakeSettings:
    def public(self):
        return {'provider': 'fake', 'model': 'fixture', 'base_url': 'https://example.invalid', 'has_key': True}


class FakeChecks:
    def __init__(self):
        self.jobs = {}
        self.calls = []

    def start(self, text, source_ids, **options):
        job_id = f'{len(self.calls)+1:032x}'
        job = {'id': job_id, 'status': 'queued', 'completed': 0, 'total': 0, 'trace': [], **options}
        self.jobs[job_id] = job
        self.calls.append((text, source_ids, options))
        return job

    def _update(self, job_id, **fields):
        self.jobs[job_id].update(fields)
        return self.jobs[job_id]

    def get(self, job_id):
        return self.jobs[job_id]


class ExperimentCenterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tasks = TaskStore(self.root / 'tasks')
        source = {'id': 'a' * 32, 'title': 'Study', 'authors': 'Smith', 'year': '2023',
                  'metadata_verified': True, 'attachment_status': 'available'}
        self.task = self.tasks.create('A claim (Smith, 2023).', [source])
        self.checks = FakeChecks()
        self.store = ExperimentStore(self.root / 'experiments', self.tasks, None, self.checks, FakeSettings())

    def tearDown(self):
        self.temp.cleanup()

    def test_paid_run_requires_confirmation_and_preserves_fixed_arms(self):
        request = {'task_id': self.task['id'], 'dataset_version': 'gold-v2', 'scope': '3',
                   'configurations': [
                       {'label': 'Legacy', 'execution_mode': 'legacy', 'context_mode': 'bm25'},
                       {'label': 'Agent neighbor', 'execution_mode': 'agent', 'context_mode': 'bm25_neighbor'},
                       {'label': 'Agent deep', 'execution_mode': 'agent', 'context_mode': 'deep'}]}
        with self.assertRaisesRegex(ValueError, '确认'):
            self.store.create(request)
        record = self.store.create({**request, 'confirmed_paid_calls': True})
        self.assertEqual(len(record['arms']), 3)
        self.assertEqual([call[2]['context_mode'] for call in self.checks.calls], ['bm25', 'bm25_neighbor', 'deep'])
        self.assertEqual(self.checks.calls[-1][2]['review_mode'], 'deep')
        self.assertNotIn('api_key', record['model'])

    def test_imported_results_and_multi_arm_gold_keep_failures(self):
        gold = {'dataset_version': 'set-1', 'samples': [
            {'sample_id': 'one', 'status': '支持'}, {'sample_id': 'two', 'status': '不支持'}]}
        predictions = {
            'A': {'predictions': [{'sample_id': 'one', 'status': '支持', 'model_status': 'completed'}]},
            'B': {'predictions': [{'sample_id': 'one', 'status': '支持', 'model_status': 'completed'},
                                  {'sample_id': 'two', 'status': '不支持', 'model_status': 'completed'}]}}
        result = compare_many(gold, predictions)
        self.assertEqual(result['arms']['A']['counts']['technical_failures'], 1)
        self.assertEqual(result['arms']['B']['classification']['accuracy'], 1)
        imported = self.store.import_document({'name': 'Imported', 'gold': gold, 'predictions': predictions})
        self.assertEqual(imported['kind'], 'imported')
        self.assertIn('A', imported['result']['arms'])

    def test_neighbor_context_is_a_real_superset_with_original_ids(self):
        blocks=[]
        for number in range(24):
            text = f'Complete paragraph sentence {number}.'
            if number == 10:text = 'Unique zephyr evidence for the claim.'
            blocks.append({'id': f'b{number}', 'text': text})
        index={'sha256': 'f'*64, 'pages': [{'physical_page': 1, 'blocks': blocks}]}
        retriever=Retriever(self.root/'retrieval');path=retriever.build(index)
        base=select_units(path,'zephyr');neighbor=select_units_with_neighbors(path,'zephyr')
        base_ids={block['id'] for unit in base for block in unit['blocks']}
        neighbor_ids={block['id'] for unit in neighbor for block in unit['blocks']}
        self.assertTrue(base_ids < neighbor_ids)
        self.assertIn('b10',neighbor_ids)
        self.assertTrue(all(unit.get('neighbor_context') for unit in neighbor))


if __name__ == '__main__':
    unittest.main()


class ExperimentHttpTests(HttpTests):
    def test_architecture_page_and_metadata_are_served(self):
        status, body = self.request('GET', '/experiments')
        self.assertEqual(status, 200)
        self.assertIn('架构与实验'.encode('utf-8'), body)
        status, body = self.request('GET', '/api/architecture')
        value = __import__('json').loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(value['pipeline'][4]['id'], 'agent')
        self.assertEqual(set(value['context_configs']), {'bm25', 'bm25_neighbor', 'deep'})

    def test_user_guide_is_served(self):
        status, body = self.request('GET', '/guide')
        self.assertEqual(status, 200)
        self.assertIn('上传文件，然后开始核查'.encode('utf-8'), body)

    def test_experiment_post_passes_confirmation_to_store(self):
        class Store:
            def create(_, data):
                if data.get('confirmed_paid_calls') is not True:raise ValueError('确认')
                return {'id': 'e'*32, 'status': 'running'}
        with patch('server.experiments', Store()):
            status, _ = self.request('POST', '/api/experiments', {'confirmed_paid_calls': False})
            self.assertEqual(status, 400)
            status, body = self.request('POST', '/api/experiments', {'confirmed_paid_calls': True})
            self.assertEqual(status, 200)
            self.assertEqual(__import__('json').loads(body)['status'], 'running')
