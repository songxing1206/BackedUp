"""Adapter from the persistent queue's two fixed review paths to ReviewAgent."""
import time
from .review_agent import ReviewAgent


class AgentRunner:
    def __init__(self, queue):
        self.queue = queue

    def run(self, jid, client, package, location, review_mode):
        before = self.queue.get(jid).get('budget_usage', {})
        started = time.monotonic()
        path = self.queue._review_location if review_mode == 'deep' else self.queue._retrieved_location
        row, reading = path(jid, client, package, location)
        after = self.queue.get(jid).get('budget_usage', {})
        tokens = after.get('actual_tokens', 0) - before.get('actual_tokens', 0) if 'actual_tokens' in after else None
        row['agent_result'] = ReviewAgent.output(location['id'], row, tokens, time.monotonic() - started).as_dict()
        row['agent_result']['requests'] = after.get('requests', 0) - before.get('requests', 0)
        return row, reading
