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
from pytation.test.test_helpers import make_station


def _mock_device():
    return Mock(['setup', 'restore', 'teardown'])


class TestDeviceOpen(unittest.TestCase):

    def test_open_with_class(self):
        dev = _mock_device()
        station = make_station(devices=[
            {'name': 'dev1', 'clz': dev, 'config': {'key': 'val'}},
        ])
        ctx = Context(station)
        ctx.device_open('dev1')
        dev.setup.assert_called_once()
        self.assertIn('dev1', ctx.devices)

    def test_open_with_string_class(self):
        station = make_station(devices=[
            {'name': 'tmod', 'clz': 'pytation.test.tmodule_device.Device', 'config': {}},
        ])
        ctx = Context(station)
        ctx.device_open('tmod')
        self.assertIn('tmod', ctx.devices)

    def test_open_invalid_class_raises(self):
        station = make_station(devices=[
            {'name': 'bad', 'clz': 'pytation.test.nonexistent_module.Cls', 'config': {}},
        ])
        ctx = Context(station)
        with self.assertRaises(Exception):
            ctx.device_open('bad')


class TestDeviceClose(unittest.TestCase):

    def test_close_not_found_logs_warning(self):
        station = make_station()
        ctx = Context(station)
        ctx.device_close('nonexistent')

    def test_close_calls_teardown(self):
        dev = _mock_device()
        station = make_station(devices=[
            {'name': 'dev1', 'clz': dev, 'config': {}},
        ])
        ctx = Context(station)
        ctx.device_open('dev1')
        ctx.device_close('dev1')
        dev.teardown.assert_called_once()
        self.assertNotIn('dev1', ctx._devices)


class TestDeviceConfigSwap(unittest.TestCase):

    def test_device_receives_its_config(self):
        captured_config = {}
        dev = Mock(['setup', 'restore', 'teardown'])
        def capture_setup(ctx):
            captured_config.update(ctx.config)
        dev.setup = capture_setup
        station = make_station(devices=[
            {'name': 'dev1', 'clz': dev, 'config': {'mode': 'test'}},
        ])
        ctx = Context(station)
        original_config = {'original': True}
        ctx.config = original_config
        ctx.device_open('dev1')
        self.assertEqual('test', captured_config['mode'])
        self.assertEqual(original_config, ctx.config)


class TestDeviceRestore(unittest.TestCase):

    def test_restore_called_after_test(self):
        dev = _mock_device()
        test_fn = Mock(return_value=0)
        test_fn.DEVICES = []
        station = make_station(
            devices=[{'name': 'dev1', 'clz': dev, 'config': {}}],
            tests=[{'name': 'test1', 'fn': test_fn, 'config': {}}],
        )
        ctx = Context(station)
        ctx.device_open('dev1')
        ctx.test_run(station['tests'][0])
        dev.restore.assert_called()

    def test_restore_exception_does_not_prevent_others(self):
        dev1 = _mock_device()
        dev1.restore.side_effect = RuntimeError('restore failed')
        dev2 = _mock_device()
        test_fn = Mock(return_value=0)
        test_fn.DEVICES = []
        station = make_station(
            devices=[
                {'name': 'dev1', 'clz': dev1, 'config': {}},
                {'name': 'dev2', 'clz': dev2, 'config': {}},
            ],
            tests=[{'name': 'test1', 'fn': test_fn, 'config': {}}],
        )
        ctx = Context(station)
        ctx.device_open('dev1')
        ctx.device_open('dev2')
        ctx.test_run(station['tests'][0])
        dev2.restore.assert_called()


class TestMixedLifecycles(unittest.TestCase):

    def test_station_device_persists_suite_device_reopened(self):
        station_dev = _mock_device()
        suite_dev = _mock_device()
        test_fn = Mock(return_value=0)
        test_fn.DEVICES = []
        station = make_station(
            devices=[
                {'name': 'station_dev', 'clz': station_dev, 'config': {}},
                {'name': 'suite_dev', 'clz': suite_dev, 'lifecycle': 'suite', 'config': {}},
            ],
            tests=[{'name': 'test1', 'fn': test_fn, 'config': {}}],
        )
        ctx = Context(station)
        ctx.station_run(count=2)
        self.assertEqual(1, station_dev.setup.call_count)
        self.assertEqual(2, suite_dev.setup.call_count)
        self.assertEqual(1, station_dev.teardown.call_count)
        self.assertEqual(2, suite_dev.teardown.call_count)
