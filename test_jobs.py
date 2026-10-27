import unittest

from jobs import InMemoryJobQueue, Job, JobQueueError, JobQueueFull, RedisJobQueue, MAX_JOB_PAYLOAD_BYTES


class FakeStreams:
    def __init__(self):
        self.events = []
        self.next_id = 0

    def xgroup_create(self, stream, group, id='$', mkstream=True):
        self.events.append(('group', stream, group, id, mkstream))

    def xadd(self, stream, fields, **kwargs):
        self.next_id += 1
        self.events.append(('xadd', stream, fields))
        return f'{self.next_id}-0'

    def xack(self, stream, group, stream_id):
        self.events.append(('xack', stream, group, stream_id))
        return 1


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

    def test_retry_configuration_is_positive(self):
        with self.assertRaises(ValueError):
            InMemoryJobQueue(max_attempts=0)
        with self.assertRaises(ValueError):
            RedisJobQueue(client=FakeStreams(), max_attempts=0)

    def test_redis_retry_publishes_before_ack_and_dead_letters_at_limit(self):
        client = FakeStreams()
        queue = RedisJobQueue(client=client, max_attempts=2)
        job = Job('job-1', 'notification.dispatch', {'order_id': 'ord-1'}, attempts=0, stream_id='10-0')
        retried = queue.retry(job)
        self.assertEqual(retried.attempts, 1)
        self.assertEqual([event[0] for event in client.events[-2:]], ['xadd', 'xack'])
        dead = queue.retry(retried)
        self.assertIsNone(dead)
        self.assertEqual(client.events[-2][0], 'xadd')
        self.assertTrue(client.events[-2][1].endswith(':dead'))
        self.assertEqual(client.events[-1][0], 'xack')

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
