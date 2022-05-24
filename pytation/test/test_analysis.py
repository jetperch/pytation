# Copyright 2022 Jetperch LLC
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
Test the Analysis module.
"""

import unittest
import os
from unittest.mock import Mock
from pytation import Context, AnalysisContext
from pytation.loader import validate


STATION = {
    'name': 'test_analysis',
    'full_name': 'Unit test analysis',
    'env': {'env_key': 'env_value'},
    'states': {
        'initialize': {},
        'wait_for_dut': {},
        'in_progress': {},
        'pass': {},
        'fail': {},
        'abort': {},
    },
    'tests': [
        {'fn': 'pytation.test.test_01', 'config': {'override': 'their_override'}},
    ],
    'devices': [],
}

class TestAnalysis(unittest.TestCase):
    PATH = None

    @classmethod
    def setUpClass(cls):
        context = Context(validate(STATION))
        context.station_run(count=1)
        TestAnalysis.path = context.path('output')

    def test_basic(self):
        a = AnalysisContext(TestAnalysis.path)
        self.assertEqual(42, a.run())

    def test_analyze_single(self):
        a = AnalysisContext(TestAnalysis.path)
        self.assertEqual(42, a.run(['pytation.test.test_01']))

    def test_analyze_invalid(self):
        a = AnalysisContext(TestAnalysis.path)
        with self.assertRaises(KeyError):
            a.run(['invalid'])
