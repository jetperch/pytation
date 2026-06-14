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
from pytation.context import sanitize_filename, DictReadOnlyWrapper, Context
from pytation.test.test_helpers import make_station


def sample_keymap_fn(context):
    """Module-level function used to test string-based keymap fn resolution."""
    return 'sample'


class TestSanitizeFilename(unittest.TestCase):

    def test_valid_chars_preserved(self):
        self.assertEqual('hello_world', sanitize_filename('hello_world'))

    def test_invalid_chars_stripped(self):
        self.assertEqual('helloworld', sanitize_filename('hello@world!'))

    def test_spaces_to_underscores(self):
        self.assertEqual('hello_world', sanitize_filename('hello world'))

    def test_truncation_at_64(self):
        long = 'a' * 100
        self.assertEqual(64, len(sanitize_filename(long)))
        self.assertEqual('a' * 64, sanitize_filename(long))

    def test_empty_string(self):
        self.assertEqual('', sanitize_filename(''))

    def test_uppercase_preserved(self):
        self.assertEqual('Hello_World', sanitize_filename('Hello World'))

    def test_digits_preserved(self):
        self.assertEqual('test123', sanitize_filename('test123'))

    def test_dots_and_hyphens_preserved(self):
        self.assertEqual('file-name.txt', sanitize_filename('file-name.txt'))


class TestDictReadOnlyWrapper(unittest.TestCase):

    def setUp(self):
        self.data = {'a': 1, 'b': 2, 'c': 3}
        self.wrapper = DictReadOnlyWrapper(self.data)

    def test_getitem(self):
        self.assertEqual(1, self.wrapper['a'])
        self.assertEqual(2, self.wrapper['b'])

    def test_len(self):
        self.assertEqual(3, len(self.wrapper))

    def test_iter(self):
        self.assertEqual(set('abc'), set(iter(self.wrapper)))

    def test_in_operator(self):
        self.assertIn('a', self.wrapper)
        self.assertNotIn('z', self.wrapper)

    def test_keys_values_items(self):
        self.assertEqual(set('abc'), set(self.wrapper.keys()))
        self.assertEqual({1, 2, 3}, set(self.wrapper.values()))
        self.assertEqual({('a', 1), ('b', 2), ('c', 3)}, set(self.wrapper.items()))

    def test_no_setitem(self):
        with self.assertRaises(TypeError):
            self.wrapper['a'] = 10

    def test_keyerror_on_missing(self):
        with self.assertRaises(KeyError):
            _ = self.wrapper['missing']


class TestExpandStr(unittest.TestCase):

    def test_single_var(self):
        station = make_station(env={'greeting': 'hello'})
        ctx = Context(station)
        self.assertEqual('hello', ctx.expand_str('{greeting}'))

    def test_multiple_vars(self):
        station = make_station(env={'a': 'X', 'b': 'Y'})
        ctx = Context(station)
        self.assertEqual('X-Y', ctx.expand_str('{a}-{b}'))

    def test_missing_var_raises(self):
        station = make_station()
        ctx = Context(station)
        with self.assertRaises(KeyError):
            ctx.expand_str('{nonexistent}')

    def test_no_placeholders(self):
        station = make_station()
        ctx = Context(station)
        self.assertEqual('plain text', ctx.expand_str('plain text'))


class TestResultStr(unittest.TestCase):

    def test_no_tests(self):
        station = make_station()
        ctx = Context(station)
        result = ctx.result_str()
        self.assertIn('*** PASS ***', result)

    def test_single_pass(self):
        station = make_station()
        ctx = Context(station)
        ctx._tests.append({'name': 'test1', 'result': 0})
        result = ctx.result_str()
        self.assertIn('test1: 0', result)
        self.assertIn('*** PASS ***', result)

    def test_single_fail(self):
        station = make_station()
        ctx = Context(station)
        ctx._tests.append({'name': 'test1', 'result': 1})
        result = ctx.result_str()
        self.assertIn('test1: 1', result)
        self.assertIn('*** FAIL ***', result)

    def test_mixed_results(self):
        station = make_station()
        ctx = Context(station)
        ctx._tests.append({'name': 'test1', 'result': 0})
        ctx._tests.append({'name': 'test2', 'result': 2})
        ctx._tests.append({'name': 'test3', 'result': 0})
        result = ctx.result_str()
        self.assertIn('*** FAIL ***', result)


class TestHandler(unittest.TestCase):

    def test_existing_handler(self):
        fn = lambda ctx: None
        station = make_station(handlers={'my_handler': fn})
        ctx = Context(station)
        self.assertIs(fn, ctx.handler('my_handler'))

    def test_missing_handler(self):
        station = make_station(handlers={'other': lambda ctx: None})
        ctx = Context(station)
        self.assertIsNone(ctx.handler('nonexistent'))

    def test_no_handlers_dict(self):
        station = make_station()
        ctx = Context(station)
        self.assertIsNone(ctx.handler('anything'))


class TestKeymapHandler(unittest.TestCase):

    def test_callable_fn_preserved(self):
        fn = lambda ctx: None
        keymap = {'R': {'name': 'Reprint', 'description': 'desc', 'fn': fn}}
        station = make_station(handlers={'qt_keypress': keymap})
        resolved = station['handlers']['qt_keypress']
        self.assertIs(fn, resolved['R']['fn'])
        self.assertEqual('Reprint', resolved['R']['name'])

    def test_string_fn_resolved(self):
        keymap = {'S': {'name': 'Sample', 'description': 'desc',
                        'fn': 'pytation.test.test_context_utils.sample_keymap_fn'}}
        station = make_station(handlers={'qt_keypress': keymap})
        resolved = station['handlers']['qt_keypress']
        self.assertIs(sample_keymap_fn, resolved['S']['fn'])

    def test_missing_field_raises(self):
        keymap = {'R': {'name': 'Reprint', 'fn': lambda ctx: None}}  # no description
        with self.assertRaises(ValueError):
            make_station(handlers={'qt_keypress': keymap})

    def test_uncallable_fn_raises(self):
        keymap = {'R': {'name': 'Reprint', 'description': 'desc', 'fn': 42}}
        with self.assertRaises(ValueError):
            make_station(handlers={'qt_keypress': keymap})

    def test_callable_handler_still_supported(self):
        fn = lambda ctx, event: True
        station = make_station(handlers={'qt_keypress': fn})
        self.assertIs(fn, station['handlers']['qt_keypress'])


class TestPath(unittest.TestCase):

    def test_simple_lookup(self):
        station = make_station()
        ctx = Context(station)
        path = ctx.path('base_path')
        self.assertIsInstance(path, str)
        self.assertTrue(len(path) > 0)

    def test_env_expansion(self):
        station = make_station()
        ctx = Context(station)
        path = ctx.path('log')
        self.assertIn(station['name'], path)

    def test_cross_reference(self):
        station = make_station()
        ctx = Context(station)
        path = ctx.path('output')
        base = ctx.path('base_path')
        self.assertTrue(path.startswith('{base_path}') or base in path or 'pytation' in path)

    def test_missing_key(self):
        station = make_station()
        ctx = Context(station)
        with self.assertRaises(KeyError):
            ctx.path('nonexistent_path')
