# Copyright 2021 Jetperch LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import unittest
from unittest.mock import Mock
from pytation.context import Context
from pytation.keywords import PYTATION_RETURN_CODE_SKIP_REMAINING_TESTS
from pytation.test.test_helpers import make_station


def _make_test_fn(return_value=0):
    fn = Mock(return_value=return_value)
    fn.DEVICES = []
    return fn


class TestDoQuit(unittest.TestCase):

    def test_do_quit_during_station_run(self):
        test1 = _make_test_fn()
        def quit_fn(ctx):
            ctx.do_quit = True
            return 0
        quit_fn.DEVICES = []
        station = make_station(tests=[
            {'name': 'quit_test', 'fn': quit_fn, 'config': {}},
            {'name': 'test2', 'fn': test1, 'config': {}},
        ])
        ctx = Context(station)
        ctx.station_run(count=2)
        test1.assert_not_called()

    def test_do_quit_during_suite_run(self):
        test1 = _make_test_fn()
        test2 = _make_test_fn()
        station = make_station(tests=[
            {'name': 'test1', 'fn': test1, 'config': {}},
            {'name': 'test2', 'fn': test2, 'config': {}},
        ])
        ctx = Context(station)
        ctx.station_start()
        ctx.do_quit = True
        result = ctx.suite_run()
        self.assertEqual(1, result)
        test1.assert_not_called()
        test2.assert_not_called()
        ctx.station_stop()


class TestErrorCountHalt(unittest.TestCase):

    def test_halt_on_first_error(self):
        test1 = _make_test_fn(return_value=1)
        test2 = _make_test_fn(return_value=0)
        test3 = _make_test_fn(return_value=0)
        station = make_station(
            env={'error_count_to_halt': 1},
            tests=[
                {'name': 'test1', 'fn': test1, 'config': {}},
                {'name': 'test2', 'fn': test2, 'config': {}},
                {'name': 'test3', 'fn': test3, 'config': {}},
            ],
        )
        ctx = Context(station)
        ctx.station_start()
        result = ctx.suite_run()
        self.assertNotEqual(0, result)
        test2.assert_not_called()
        test3.assert_not_called()
        ctx.station_stop()

    def test_continues_under_high_threshold(self):
        test1 = _make_test_fn(return_value=1)
        test2 = _make_test_fn(return_value=0)
        station = make_station(
            env={'error_count_to_halt': 3},
            tests=[
                {'name': 'test1', 'fn': test1, 'config': {}},
                {'name': 'test2', 'fn': test2, 'config': {}},
            ],
        )
        ctx = Context(station)
        ctx.station_start()
        ctx.suite_run()
        test2.assert_called_once()
        ctx.station_stop()


class TestSkipRemainingTests(unittest.TestCase):

    def test_skip_remaining(self):
        test1 = _make_test_fn(return_value=PYTATION_RETURN_CODE_SKIP_REMAINING_TESTS)
        test2 = _make_test_fn(return_value=0)
        station = make_station(tests=[
            {'name': 'test1', 'fn': test1, 'config': {}},
            {'name': 'test2', 'fn': test2, 'config': {}},
        ])
        ctx = Context(station)
        ctx.station_start()
        result = ctx.suite_run()
        self.assertEqual(0, result)
        test2.assert_not_called()
        ctx.station_stop()


class TestSuiteSetupFailure(unittest.TestCase):

    def test_suite_setup_failure_skips_tests(self):
        setup_fn = _make_test_fn(return_value=1)
        test1 = _make_test_fn(return_value=0)
        station = make_station(
            tests=[{'name': 'test1', 'fn': test1, 'config': {}}],
            suite_setup={'name': 'suite_setup', 'fn': setup_fn, 'config': {}},
        )
        ctx = Context(station)
        ctx.station_start()
        result = ctx.suite_run()
        self.assertNotEqual(0, result)
        test1.assert_not_called()
        ctx.station_stop()


class TestMultipleSuiteRuns(unittest.TestCase):

    def test_count_two(self):
        test1 = _make_test_fn(return_value=0)
        station = make_station(tests=[
            {'name': 'test1', 'fn': test1, 'config': {}},
        ])
        ctx = Context(station)
        ctx.station_run(count=2)
        self.assertEqual(2, test1.call_count)


class TestTestSkip(unittest.TestCase):

    def test_skip_flag(self):
        test1 = _make_test_fn(return_value=0)
        test2 = _make_test_fn(return_value=0)
        station = make_station(tests=[
            {'name': 'test1', 'fn': test1, 'config': {}, 'skip': True},
            {'name': 'test2', 'fn': test2, 'config': {}},
        ])
        ctx = Context(station)
        ctx.station_start()
        ctx.suite_run()
        test1.assert_not_called()
        test2.assert_called_once()
        ctx.station_stop()
