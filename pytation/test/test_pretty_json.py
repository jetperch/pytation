# Copyright 2022 Jetperch LLC.  All rights reserved.

"""
Test the pretty JSON module
"""

import unittest
import json
from pytation.pretty_json import dumps


OBJ1 = {'a': [1, 2, 3], 'b': [4, 5, 6]}
OBJ1_EXPECT = """\
{
  "a": [ 1, 2, 3 ],
  "b": [ 4, 5, 6 ]
}\
"""

OBJ2 = {'a': [[1, 2, 3], [4, 5, 6]]}
OBJ2_EXPECT = """\
{
  "a": [
    [ 1, 2, 3 ],
    [ 4, 5, 6 ]
  ]
}\
"""


class TestPrettyJson(unittest.TestCase):

    def test_basic(self):
        d = {'a': 1, 'b': 2}
        s1 = json.dumps(d, indent=2)
        s2 = dumps(d)
        self.assertEqual(s1, s2)

    def test_list(self):
        s2 = dumps(OBJ1)
        self.assertEqual(OBJ1_EXPECT, s2)

    def test_nested_list(self):
        s2 = dumps(OBJ2)
        self.assertEqual(OBJ2_EXPECT, s2)
