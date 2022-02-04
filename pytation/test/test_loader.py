# Copyright 2019-2021 Jetperch LLC
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
from pytation import loader
from pytation import declare_test, Context
import argparse


@declare_test(['dut'])
def test2(context: Context, config: dict[str, object]):
    return 0


class DutEmpty:
    def setup(self, context: Context, config=None):
        pass

    def restore(self):
        pass

    def teardown(self):
        pass


class TestLoader(unittest.TestCase):

    def _parser(self):
        p = argparse.ArgumentParser()
        loader.parser_config(p)
        return p

    def test_simple_normal(self):
        args = self._parser().parse_args(['pytation_examples.simple.STATION'])
        s = loader.load(args)
        tests = s['tests']
        self.assertEqual(3, len(tests))
        self.assertEqual(['enter_serial_number', 'test1', 'long_iter'], [t['name'] for t in tests])

    def test_exclude_one(self):
        args = self._parser().parse_args(['pytation_examples.simple.STATION', '--exclude', 'test1'])
        s = loader.load(args)
        tests = s['tests']
        self.assertEqual(['enter_serial_number', 'long_iter'], [t['name'] for t in tests])

    def test_exclude_multiple(self):
        args = self._parser().parse_args(['pytation_examples.simple.STATION', '--exclude', 'test1,enter_serial_number'])
        s = loader.load(args)
        tests = s['tests']
        self.assertEqual(['long_iter'], [t['name'] for t in tests])

    def test_exclude_invalid(self):
        args = self._parser().parse_args(['pytation_examples.simple.STATION', '--exclude', '__invalid__'])
        with self.assertRaises(ValueError):
            loader.load(args)

    def test_include_one(self):
        args = self._parser().parse_args(['pytation_examples.simple.STATION', '--include', 'test1'])
        s = loader.load(args)
        tests = s['tests']
        self.assertEqual(['test1'], [t['name'] for t in tests])

    def test_include_multiple(self):
        args = self._parser().parse_args(['pytation_examples.simple.STATION', '--include', 'test1,enter_serial_number'])
        s = loader.load(args)
        tests = s['tests']
        self.assertEqual(['enter_serial_number', 'test1'], [t['name'] for t in tests])


class TestValidator(unittest.TestCase):

    def setUp(self):
        self.test1 = Mock()
        self.test1.NAME = 'test1'
        self.test1.return_value = 0
        self.test1.DEVICES = ['dut', 'eq1']
        self.eq1 = Mock(['setup', 'restore', 'teardown'])
        self.dut = Mock(['setup', 'restore', 'teardown'])
        self.dut.NAME = 'dut'

    def test_validate_basics(self):
        station = {
            'name': 'station1',
            'tests': [
                {'fn': self.test1},
                {'fn': test2},
                {'name': 'test3', 'fn': test2},
            ],
            'devices': [
                {'name': 'eq1', 'clz': self.eq1, 'config': {}},
                {'clz': self.dut, 'lifecycle': 'suite', 'config': {'mode': 'test'}},
            ],
        }
        station = loader.validate(station)
        tests = station['tests']
        self.assertEqual('test1', tests[0]['name'])
        self.assertEqual(['dut', 'eq1'], tests[0]['devices'])
        self.assertEqual({}, tests[0]['config'])
        self.assertEqual('test2', tests[1]['name'])
        self.assertEqual('test3', tests[2]['name'])

    def test_duplicate_test_name(self):
        station = {
            'name': 'station1',
            'tests': [{'fn': test2}, {'fn': test2}],
            'devices': [{'clz': self.dut, 'lifecycle': 'suite', 'config': {'mode': 'test'}}],
        }
        with self.assertRaises(ValueError):
            loader.validate(station)

    def test_duplicate_device_name(self):
        station = {
            'name': 'station1',
            'tests': [{'fn': test2}],
            'devices': [{'clz': self.dut}, {'clz': self.dut}],
        }
        with self.assertRaises(ValueError):
            loader.validate(station)

    def test_invalid_device_lifecycle(self):
        station = {
            'name': 'station1',
            'tests': [{'fn': test2}],
            'devices': [{'clz': self.dut, 'lifecycle': 'invalid'}],
        }
        with self.assertRaises(ValueError):
            loader.validate(station)

    def test_device_name(self):
        dut2 = Mock(['setup', 'restore', 'teardown'])
        station = {
            'name': 'station1',
            'tests': [{'fn': test2}],
            'devices': [{'clz': self.dut}, {'name': 'dut2', 'clz': dut2}, {'clz': DutEmpty}],
        }
        station = loader.validate(station)
        names = [d['name'] for d in station['devices'].values()]
        self.assertEqual(['dut', 'dut2', 'DutEmpty'], names)

    def test_module_name_as_test(self):
        station = {
            'name': 'station1',
            'tests': [{'fn': 'pytation.test.tmodule'}],
            'devices': [],
        }
        station = loader.validate(station)
