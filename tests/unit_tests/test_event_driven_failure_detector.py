import unittest
import time
from unittest.mock import Mock, MagicMock, call
from resolve.resolver import Resolver
from modules.event_driven_fd.module import EventDrivenFDModule
from modules.constants import K_ADMISSIBILITY_THRESHOLD as K
from resolve.enums import MessageType
from copy import deepcopy

N = 6
F = 1

class TestEventDrivenFailureDetector(unittest.TestCase):
    def setUp(self):
        self.resolver = Resolver(testing=True)
        self.module = EventDrivenFDModule(0, self.resolver, 6, 1)
    
    def build_msg(self, sender, token, owner):
        return {
            "type": MessageType.EVENT_DRIVEN_FD_MESSAGE,
            "sender": sender,
            "data": {
                "token": token,
                "owner_id": owner
            }
        }
    
    def test_run(self):
        self.module.broadcast = MagicMock()
        ts = time.time()
        self.module.token = ts

        # inject valid counters, module should run through and set last_correct_processors
        # and increment counter
        self.module.counters = {n_id: K for n_id in range(1, N)}
        self.module.run(True)
        self.assertCountEqual({
            "token": ts,
            "correct_processors": [i for i in range(1, N)]
        }, self.module.last_correct_processors)
        self.assertEqual(self.module.counters, {n_id: 0 for n_id in range(1, N)})
        self.assertGreater(self.module.token, ts)
    
    def test_on_msg_recv(self):
        self.module.send_token = MagicMock()
        ts = time.time()
        self.module.token = ts

        # counter for sender should be incremented when receiving current token
        self.assertEqual(self.module.counters[3], 0)
        msg = self.build_msg(3, ts, 0)
        self.module.on_msg_recv(msg)
        self.assertEqual(self.module.counters[3], 1)
        # should send token back to sender
        self.assertEqual(self.module.send_token.call_count, 1)

        # counter for sender should stay the same when sending invalid token
        self.assertEqual(self.module.counters[3], 1)
        msg = self.build_msg(3, time.time(), 0)
        self.module.on_msg_recv(msg)
        self.assertEqual(self.module.counters[3], 1)
        # should not send token back due to invalid token, call_count should be the same
        self.assertEqual(self.module.send_token.call_count, 1)

        # no counter should change when current processor is not owner
        old_counters = deepcopy(self.module.counters)
        msg = self.build_msg(3, ts, 1)
        self.module.on_msg_recv(msg)
        self.assertEqual(old_counters, self.module.counters)
        # token should be sent back
        self.assertEqual(self.module.send_token.call_count, 2)
    
    def test_send_token(self):
        self.resolver.send_to_node = MagicMock()
        self.module.send_token(0, 1, 2)
        msg = self.build_msg(0, 1, 2)
        self.resolver.send_to_node.assert_called_once_with(0, msg, True)

    def test_get_correct_processors(self):
        # should return [self.id] for 0 correct processors
        self.assertEqual(self.module.get_correct_processors(), [0])

        # inject two correct processors and one faulty, get_correct_processors should return the correct IDs
        self.module.counters[1] = K
        self.module.counters[2] = K + 1
        self.module.counters[3] = K - 1
        self.assertCountEqual(self.module.get_correct_processors(), [0,1,2,3])
    
    def test_correct_processors_have_replied(self):
        # should be False since no processors have yet replied
        self.assertFalse(self.module.correct_processors_have_replied())

        # force n-2f processors to have acked K times, should now return true
        self.module.counters = {i: K for i in range(N - 2*F)}
        self.assertTrue(self.module.correct_processors_have_replied())
    
    def test_get_last_correct_processors(self):
        # should be empty at first
        self.assertCountEqual(self.module.get_last_correct_processors(), [])

        # inject last_correct_processor set of N-1 processors
        self.module.last_correct_processors = {
            "token": 1,
            "correct_processors": [i for i in range(N-1)]
        }
        # should return their IDs
        self.assertCountEqual(self.module.get_last_correct_processors(), [
            i for i in range(N-1)
        ])
    