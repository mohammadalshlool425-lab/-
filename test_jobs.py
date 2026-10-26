import unittest

from jobs import InMemoryJobQueue, JobQueueError, JobQueueFull, MAX_JOB_PAYLOAD_BYTES


class JobQueueTests(unittest.TestCase):
    def test_enqueue_reserve_retry_and_dead_letter(self):
        queue = InMemoryJobQueue(max_jobs=10, max_attempts=2)
        queued = queue.enqueue('notification.dispatch', {'channel': 'sms', 'order_id': 'ord-1'})
        self.assertIsNotNone(queued)
        job = queue.reserve()[0]
        self.assertEqual(job.attempts, 1)
        queue.retry(job)
        retried = queue.reserve()[0]
        self.assertEqual(retried.attempts, 2)
        queue.retry(retried)
        self.assertEqual(len(queue.dead_letters()), 1)
        self.assertEqual(queue.dead_letters()[0].job_id, queued.job_id)

    def test_dedupe_and_capacity_are_bounded(self):
        queue = InMemoryJobQueue(max_jobs=1)
        first = queue.enqueue('payment.capture', {'order_id': 'ord-1'}, dedupe_key='payment:ord-1')
        self.assertIsNotNone(first)
        self.assertIsNone(queue.enqueue('payment.capture', {'order_id': 'ord-1'}, dedupe_key='payment:ord-1'))
        with self.assertRaises(JobQueueFull):
            queue.enqueue('payment.capture', {'order_id': 'ord-2'})

    def test_payload_and_kind_are_validated(self):
        queue = InMemoryJobQueue()
        with self.assertRaises(JobQueueError):
            queue.enqueue('Not valid', {})
        with self.assertRaises(JobQueueError):
            queue.enqueue('notification.dispatch', {'data': 'x' * MAX_JOB_PAYLOAD_BYTES})
        with self.assertRaises(JobQueueError):
            queue.enqueue('notification.dispatch', {'data': object()})


if __name__ == '__main__':
    unittest.main(verbosity=2)
