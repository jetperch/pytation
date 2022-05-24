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

"""
Test the Context class.
"""

import unittest
from unittest.mock import Mock
from pytation import Context, declare_test
from pytation.loader import validate


@declare_test(['eq2'])
def needs_eq2(context, config):
    return 0


def call_wait_for_user(context):
    context.wait_for_user()


def call_prompt(context):
    s = context.prompt('Hello?')
    return 0, {'user_data': s}


def state_in_progress(context):
    context.state = 'in_progress'


class TestContext(unittest.TestCase):

    def _station1(self, name, skip_validate=False):
        self.test1 = Mock()
        self.test1.return_value = 0
        self.test1.DEVICES = ['dut', 'eq1']
        self.test2 = Mock()
        self.test2.return_value = 0
        self.test2.DEVICES = ['dut', 'eq1']
        self.eq1 = Mock(['setup', 'restore', 'teardown'])
        self.dut = Mock(['setup', 'restore', 'teardown'])
        station = {
            'name': name,
            'full_name': 'Station 1 for unit test',
            'states': {
                'initialize': {},
                'wait_for_dut': {},
                'in_progress': {},
                'pass': {},
                'fail': {},
                'abort': {},
            },
            'tests': [
                {'name': 'test1', 'fn': self.test1, 'config': {}},
                {'name': 'test2', 'fn': self.test2, 'config': {}},
            ],
            'devices': [
                {'name': 'eq1', 'clz': self.eq1, 'config': {}},
                {'name': 'dut', 'clz': self.dut, 'lifecycle': 'suite', 'config': {'mode': 'test'}},
            ],
        }
        if skip_validate:
            return station
        return validate(station)

    def test_station_start_and_stop(self):
        context = Context(self._station1('test_station_start_and_stop'))
        context.station_start()
        self.eq1.setup.assert_called_once()
        context.station_stop()
        self.eq1.teardown.assert_called_once()

    def test_station_once(self):
        context = Context(self._station1('test_station_once'))
        context.station_run(count=1)
        self.eq1.setup.assert_called_once()
        self.dut.setup.assert_called_once()
        self.test1.assert_called_once()
        self.test2.assert_called_once()
        self.dut.teardown.assert_called_once()
        self.eq1.teardown.assert_called_once()

    def test_station_manual(self):
        context = Context(self._station1('test_station_manual'))
        context.station_start()
        self.assertEqual(0, context.suite_run())
        context.station_stop()

    def test_station_failure(self):
        context = Context(self._station1('test_station_failure'))
        self.test1.return_value = 1
        context.station_start()
        self.assertEqual(1, context.suite_run())
        context.station_stop()

    def test_return_values(self):
        context = Context(self._station1('test_return_values'))
        self.test1.return_value = None
        self.test2.return_value = 0, {'hello': 'world'}
        context.station_start()
        self.assertEqual(0, context.suite_run())
        context.station_stop()

    def test_with_required_device_not_present(self):
        station = self._station1('test_with_required_device_not_present', skip_validate=True)
        station['tests'][0]['fn'] = needs_eq2
        station = validate(station)
        context = Context(station)
        context.station_start()
        self.assertEqual(-1, context.suite_run())
        context.station_stop()

    def test_wait_for_user_callback(self):
        cbk = Mock()
        station = self._station1('test_wait_for_user_callback')
        station['tests'][0]['fn'] = call_wait_for_user
        context = Context(station)
        context.callback_register('wait_for_user', cbk)
        context.station_run(count=1)
        cbk.assert_called_once()

    def test_prompt(self):
        cbk = Mock()
        cbk.return_value = 'yes!'
        station = self._station1('test_wait_for_user_callback')
        station['tests'][0]['fn'] = call_prompt
        context = Context(station)
        context.callback_register('prompt', cbk)
        context.station_run(count=1)
        cbk.assert_called_once()

    def test_state(self):
        cbk = Mock()
        station = self._station1('test_state')
        station['tests'][0]['fn'] = state_in_progress
        context = Context(station)
        context.callback_register('state', cbk)
        context.station_run(count=1)
        cbk.assert_called_once()
