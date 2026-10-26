import unittest

from jobs import InMemoryJobQueue
from worker import JobWorker


class WorkerTests(unittest.TestCase):
    def test_successful_handler_is_acknowledged(self):
        queue = InMemoryJobQueue()
        seen = []
        queue.enqueue('notification.dispatch', {'order_id': 'ord-1'})
        worker = JobWorker(queue, {'notification.dispatch': lambda payload: seen.append(payload['order_id'])}, 'worker-1')
        stats = worker.process_once()
        self.assertEqual(stats.processed, 1)
        self.assertEqual(seen, ['ord-1'])
        self.assertEqual(queue.reserve(), [])

    def test_failed_handler_is_retried_then_dead_lettered(self):
        queue = InMemoryJobQueue(max_attempts=2)
        queue.enqueue('payment.capture', {'order_id': 'ord-2'})
        worker = JobWorker(queue, {'payment.capture': lambda payload: (_ for _ in ()).throw(RuntimeError('provider unavailable'))}, 'worker-2')
        first = worker.process_once()
        second = worker.process_once()
        self.assertEqual(first.retried, 1)
        self.assertEqual(first.failed, 1)
        self.assertEqual(second.dead_lettered, 1)
        self.assertEqual(len(queue.dead_letters()), 1)

    def test_missing_handler_is_not_acknowledged_as_success(self):
        queue = InMemoryJobQueue(max_attempts=1)
        queue.enqueue('unknown.job', {})
        worker = JobWorker(queue, {'known.job': lambda payload: None}, 'worker-3')
        stats = worker.process_once()
        self.assertEqual(stats.failed, 1)
        self.assertEqual(stats.dead_lettered, 1)
        self.assertEqual(len(queue.dead_letters()), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
