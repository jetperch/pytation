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
from pytation.progress import parse, lookup, Progress
import numpy as np


TXT1 = """\
0.033,,'__enter__'
0.040,program,'__enter__'
0.043,program,'find_lpc_bootloader'
0.046,program,'program_bootloader'
2.622,program,'wait_for_bootloader'
2.623,program,'program_personality'
2.754,program,'controller_program'
2.757,program.controller,'__enter__'
2.757,program.controller,'load firmware'
2.758,program.controller,'find bootloader'
2.761,program.controller,'open bootloader'
2.765,program.controller.firmware,'__enter__'
4.118,program.controller.firmware,'__exit__'
4.119,program.controller,'launch application'
4.121,program.controller,'__exit__'
4.122,program,'sensor_program'
4.123,program.sensor,'__enter__'
4.124,program.sensor,'load firmware'
4.125,program.sensor,'find Joulescope'
5.641,program.sensor,'open Joulescope'
6.365,program.sensor.firmware,'__enter__'
8.0,program.sensor.firmware,0.1
10.0,program.sensor.firmware,0.2
12.0,program.sensor.firmware,0.4
14.0,program.sensor.firmware,0.6
16.0,program.sensor.firmware,0.8
20.0,program.sensor.firmware,0.9
21.000,program.sensor.firmware,'__exit__'
21.030,program.sensor,'__exit__'
21.033,program,'__exit__'
21.066,,'__exit__'
"""

tbl = parse(TXT1)

TXT2 = """\
0.0,s,'__enter__'
0.1,s.hi,'__enter__'
0.5,s.hi,'hello'
1.0,s.hi,'__wait_enter__ user_input'
5.0,s.hi,'__wait_exit__ user_input'
6.0,s.hi,'world'
9.0,s.hi,'__exit__'
10.0,s,'__exit__'
"""

class TestLookup(unittest.TestCase):

    def test_root(self):
        self.assertLess(lookup(tbl, '', '__enter__'), 0.01)
        self.assertGreater(lookup(tbl, '', '__exit__'), 0.99)

    def test_exact(self):
        np.testing.assert_approx_equal(lookup(tbl, 'program.controller', 'find bootloader'), 0.13092186461596886)

    def test_float(self):
        s_enter = lookup(tbl, 'program.sensor.firmware', '__enter__')
        s_exit = lookup(tbl, 'program.sensor.firmware', '__exit__')
        s_mid = (s_exit + s_enter) / 2
        np.testing.assert_approx_equal(lookup(tbl, 'program.sensor.firmware', 0.0), s_enter)
        np.testing.assert_approx_equal(lookup(tbl, 'program.sensor.firmware', 1.0), s_exit)
        np.testing.assert_approx_equal(lookup(tbl, 'program.sensor.firmware', 0.5), s_mid)

    def test_class(self):
        c = Progress(TXT1)
        self.assertLess(c.lookup('', '__enter__'), 0.01)
        self.assertGreater(c.lookup('', '__exit__'), 0.99)
        
    def test_wait(self):
        tbl = parse(TXT2)
        np.testing.assert_approx_equal(lookup(tbl, 's.hi', 'world'), 1/3)
        
