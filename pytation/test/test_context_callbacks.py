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


class TestCallbacks(unittest.TestCase):

    def setUp(self):
        self.station = make_station()
        self.ctx = Context(self.station)

    def test_register_non_callable_raises(self):
        with self.assertRaises(ValueError):
            self.ctx.callback_register('progress', 'not_callable')

    def test_unregister(self):
        cbk = Mock()
        self.ctx.callback_register('progress', cbk)
        self.ctx.callback_unregister('progress', cbk)
        self.ctx._progress_update(0.5)
        cbk.assert_not_called()

    def test_unregister_not_registered(self):
        cbk = Mock()
        self.ctx.callback_unregister('progress', cbk)

    def test_duplicate_registration(self):
        cbk = Mock()
        self.ctx.callback_register('progress', cbk)
        self.ctx.callback_register('progress', cbk)
        self.ctx._progress_update(0.5)
        self.assertEqual(2, cbk.call_count)

    def test_progress_callback_invoked(self):
        cbk = Mock()
        self.ctx.callback_register('progress', cbk)
        self.ctx._progress_update(0.25)
        cbk.assert_called_once_with(0.25)
        self.ctx._progress_update(0.75)
        cbk.assert_called_with(0.75)

    def test_progress_callback_exception_logged(self):
        bad_cbk = Mock(side_effect=RuntimeError('boom'))
        good_cbk = Mock()
        self.ctx.callback_register('progress', bad_cbk)
        self.ctx.callback_register('progress', good_cbk)
        self.ctx._progress_update(0.5)
        bad_cbk.assert_called_once_with(0.5)
        good_cbk.assert_called_once_with(0.5)

    def test_state_callback_exception_logged(self):
        bad_cbk = Mock(side_effect=RuntimeError('boom'))
        good_cbk = Mock()
        self.ctx.callback_register('state', bad_cbk)
        self.ctx.callback_register('state', good_cbk)
        self.ctx.state = 'in_progress'
        self.assertEqual(1, bad_cbk.call_count)
        self.assertEqual(1, good_cbk.call_count)

    def test_state_invalid_raises(self):
        with self.assertRaises(RuntimeError):
            self.ctx.state = 'nonexistent_state'
