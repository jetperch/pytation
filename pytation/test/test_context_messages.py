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

    def test_idle_logging_outside_test_does_not_crash(self):
        station = make_station(tests=[])
        ctx = Context(station)
        ctx.station_start()
        _log.warning('between tests, handler idle')  # records is None
        ctx.station_stop()


if __name__ == '__main__':
    unittest.main()
