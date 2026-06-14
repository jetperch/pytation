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


import logging
import os
import unittest
from pytation.context import Context
from pytation.test.test_helpers import make_station


_log = logging.getLogger('pytation.test.messages')


def _capture_fn(fn):
    """Wrap a plain function as a pytation test function."""
    fn.DEVICES = []
    return fn


class TestMessageCapture(unittest.TestCase):

    def test_capture_via_teardown_accessor(self):
        holder = {}

        def fn(ctx):
            _log.warning('careful')
            _log.error('boom')
            return 1

        def teardown(ctx):
            holder['failing'] = ctx.messages()
            holder['named'] = ctx.messages('t1')
            return 0
        _capture_fn(fn)
        _capture_fn(teardown)
        station = make_station(
            tests=[{'name': 't1', 'fn': fn, 'config': {}}],
            suite_teardown={'name': 'suite_teardown', 'fn': teardown, 'config': {}},
        )
        ctx = Context(station)
        ctx.station_start()
        ctx.suite_run()
        ctx.station_stop()

        msgs = holder['failing']
        self.assertEqual(holder['named'], msgs)
        levels = [m['level'] for m in msgs]
        self.assertIn('WARNING', levels)
        self.assertIn('ERROR', levels)
        texts = [m['message'] for m in msgs]
        self.assertIn('careful', texts)
        self.assertIn('boom', texts)
        for m in msgs:
            self.assertEqual({'level', 'timestamp', 'name', 'file', 'line', 'message'}, set(m))

    def test_exception_traceback_captured(self):
        holder = {}

        def fn(ctx):
            raise ValueError('kaboom')

        def teardown(ctx):
            holder['msgs'] = ctx.messages('t1')
            return 0
        _capture_fn(fn)
        _capture_fn(teardown)
        station = make_station(
            tests=[{'name': 't1', 'fn': fn, 'config': {}}],
            suite_teardown={'name': 'suite_teardown', 'fn': teardown, 'config': {}},
        )
        ctx = Context(station)
        ctx.station_start()
        ctx.suite_run()
        ctx.station_stop()

        msgs = holder['msgs']
        self.assertTrue(any('Traceback' in m['message'] and 'kaboom' in m['message']
                            for m in msgs))

    def test_passing_test_has_empty_messages(self):
        holder = {}

        def fn(ctx):
            return 0

        def teardown(ctx):
            holder['t1'] = ctx.messages('t1')
            holder['failing'] = ctx.messages()  # no failing test
            return 0
        _capture_fn(fn)
        _capture_fn(teardown)
        station = make_station(
            tests=[{'name': 't1', 'fn': fn, 'config': {}}],
            suite_teardown={'name': 'suite_teardown', 'fn': teardown, 'config': {}},
        )
        ctx = Context(station)
        ctx.station_start()
        ctx.suite_run()
        ctx.station_stop()
        self.assertEqual([], holder['t1'])
        self.assertEqual([], holder['failing'])

    def test_unknown_name_raises(self):
        holder = {}

        def fn(ctx):
            return 0

        def teardown(ctx):
            try:
                ctx.messages('does_not_exist')
            except KeyError:
                holder['raised'] = True
            return 0
        _capture_fn(fn)
        _capture_fn(teardown)
        station = make_station(
            tests=[{'name': 't1', 'fn': fn, 'config': {}}],
            suite_teardown={'name': 'suite_teardown', 'fn': teardown, 'config': {}},
        )
        ctx = Context(station)
        ctx.station_start()
        ctx.suite_run()
        ctx.station_stop()
        self.assertTrue(holder.get('raised'))

    def test_context_log_is_module_logger(self):
        holder = {}

        def fn(ctx):
            holder['name'] = ctx.log.name
            ctx.log.warning('via ctx.log')
            return 1

        def teardown(ctx):
            holder['msgs'] = ctx.messages('t1')
            return 0
        _capture_fn(fn)
        _capture_fn(teardown)
        station = make_station(
            tests=[{'name': 't1', 'fn': fn, 'config': {}}],
            suite_teardown={'name': 'suite_teardown', 'fn': teardown, 'config': {}},
        )
        ctx = Context(station)
        ctx.station_start()
        ctx.suite_run()
        ctx.station_stop()

        # ctx.log is named for the test fn's module, like getLogger(__name__)
        self.assertEqual(fn.__module__, holder['name'])
        # logging through ctx.log is still captured into the test messages
        self.assertIn('via ctx.log', [m['message'] for m in holder['msgs']])
        # ctx.log is reset to the framework logger after each test
        self.assertEqual('pytation', ctx.log.name)

    def test_idle_logging_outside_test_does_not_crash(self):
        station = make_station(tests=[])
        ctx = Context(station)
        ctx.station_start()
        _log.warning('between tests, handler idle')  # records is None
        ctx.station_stop()


class TestSuiteStopCleanup(unittest.TestCase):
    """The staging dir + log.txt must be released even on interrupted teardown."""

    def test_teardown_interrupt_releases_staging(self):
        holder = {}

        def fn(ctx):
            holder['staging'] = ctx._fs._staging  # capture while the suite is open
            return 0

        def teardown(ctx):
            # Simulates do_quit during a suite_teardown wait_for_user(), which
            # raises KeyboardInterrupt (e.g. operator closes the window).
            raise KeyboardInterrupt('simulated quit')
        _capture_fn(fn)
        _capture_fn(teardown)
        station = make_station(
            tests=[{'name': 't1', 'fn': fn, 'config': {}}],
            suite_teardown={'name': 'suite_teardown', 'fn': teardown, 'config': {}},
        )
        ctx = Context(station)
        ctx.station_start()
        with self.assertRaises(KeyboardInterrupt):
            ctx.suite_run()

        # Despite the interrupted teardown, the fs is closed and the staging
        # temp dir (which held the open log.txt) is removed.
        self.assertIsNone(ctx._fs)
        self.assertFalse(os.path.exists(holder['staging']))
        ctx.station_stop()


class _ListHandler(logging.Handler):
    """Capture every emitted record into a list."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


class TestCallableLog(unittest.TestCase):
    """``context.log`` is a standard Logger that is also directly callable."""

    def _capture(self):
        handler = _ListHandler()
        root = logging.getLogger()
        root.addHandler(handler)
        self.addCleanup(root.removeHandler, handler)
        return handler

    def test_call_logs_at_info(self):
        ctx = Context(make_station())
        handler = self._capture()
        ctx.log('hello %s', 'world')  # printf-style args forwarded
        matches = [r for r in handler.records if r.getMessage() == 'hello world']
        self.assertEqual(1, len(matches))
        self.assertEqual(logging.INFO, matches[0].levelno)

    def test_call_reports_caller_location(self):
        # stacklevel=2 means the record points at this test, not context.py.
        ctx = Context(make_station())
        handler = self._capture()
        ctx.log('locate me')
        matches = [r for r in handler.records if r.getMessage() == 'locate me']
        self.assertEqual(1, len(matches))
        self.assertTrue(matches[0].filename.endswith('test_context_messages.py'))

    def test_logger_interface_preserved(self):
        ctx = Context(make_station())
        self.assertTrue(callable(ctx.log))
        self.assertEqual('pytation', ctx.log.name)
        handler = self._capture()
        ctx.log.warning('attr style')  # .info/.warning/etc still work
        msgs = [r.getMessage() for r in handler.records]
        self.assertIn('attr style', msgs)

    def test_callable_during_test_with_module_logger(self):
        holder = {}

        def fn(ctx):
            holder['callable'] = callable(ctx.log)
            holder['name'] = ctx.log.name  # per-test module logger
            ctx.log('info via call')       # must not raise
            ctx.log.warning('warn via attr')
            return 1

        def teardown(ctx):
            holder['msgs'] = ctx.messages('t1')
            return 0
        _capture_fn(fn)
        _capture_fn(teardown)
        station = make_station(
            tests=[{'name': 't1', 'fn': fn, 'config': {}}],
            suite_teardown={'name': 'suite_teardown', 'fn': teardown, 'config': {}},
        )
        ctx = Context(station)
        ctx.station_start()
        ctx.suite_run()
        ctx.station_stop()

        self.assertTrue(holder['callable'])
        self.assertEqual(fn.__module__, holder['name'])
        self.assertIn('warn via attr', [m['message'] for m in holder['msgs']])
        # still callable after reset to the framework logger
        self.assertTrue(callable(ctx.log))


if __name__ == '__main__':
    unittest.main()
