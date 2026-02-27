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
from pytation.context import Context
from pytation.test.test_helpers import make_station


class TestSections(unittest.TestCase):

    def setUp(self):
        self.station = make_station()
        self.ctx = Context(self.station)

    def test_section_enter_exit(self):
        self.ctx.section_enter('a')
        self.assertEqual('a', self.ctx.section_name)
        self.ctx.section_exit('a')
        self.assertEqual('', self.ctx.section_name)

    def test_nested_sections(self):
        self.ctx.section_enter('s')
        self.assertEqual('s', self.ctx.section_name)
        self.ctx.section_enter('a')
        self.assertEqual('s.a', self.ctx.section_name)
        self.ctx.section_enter('b')
        self.assertEqual('s.a.b', self.ctx.section_name)
        self.ctx.section_exit('b')
        self.assertEqual('s.a', self.ctx.section_name)
        self.ctx.section_exit('a')
        self.assertEqual('s', self.ctx.section_name)
        self.ctx.section_exit('s')
        self.assertEqual('', self.ctx.section_name)

    def test_section_exit_name_mismatch(self):
        self.ctx.section_enter('a')
        with self.assertRaises(RuntimeError):
            self.ctx.section_exit('wrong')

    def test_section_exit_no_sections(self):
        with self.assertRaises(RuntimeError):
            self.ctx.section_exit('a')

    def test_section_context_manager(self):
        with self.ctx.section('outer'):
            self.assertEqual('outer', self.ctx.section_name)
            with self.ctx.section('inner'):
                self.assertEqual('outer.inner', self.ctx.section_name)
            self.assertEqual('outer', self.ctx.section_name)
        self.assertEqual('', self.ctx.section_name)

    def test_exception_inside_section(self):
        with self.assertRaises(ValueError):
            with self.ctx.section('cleanup_test'):
                raise ValueError('test error')
        self.assertEqual('', self.ctx.section_name)

    def test_section_name_property_empty(self):
        self.assertEqual('', self.ctx.section_name)
