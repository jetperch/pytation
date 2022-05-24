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
from pytation import time as pt
import datetime


class TestTime(unittest.TestCase):

    def test_filename(self):
        now = pt.now()
        fname = pt.time_to_filename(now)
        now2 = pt.filename_to_time(fname)
        self.assertAlmostEqual(now, now2, places=6)

    def test_iso_str(self):
        now = pt.now()
        iso = pt.time_to_isostr(now)
        now2 = pt.isostr_to_time(iso)
        self.assertAlmostEqual(now, now2, places=6)
