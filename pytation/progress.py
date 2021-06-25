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


import logging


def parse_lines(txt):
    """Parse the text into the line fields

    :param txt: The text to parse.
    :return: The list with an entry for each valid line, which
        is also a list of [time, identifier, value].
    """
    offset = 0.0
    wait_start = None

    lines = []
    line = ''
    try:
        for idx, line in enumerate(txt.split('\n')):
            if not len(line) or line.startswith('#'):
                continue
            t, identifier, value = line.split(',', 2)
            t = float(t) - offset
            if value[0] == "'":
                value = value[1:-1]
                if value.startswith('__wait_enter__'):
                    wait_start = t
                elif value.startswith('__wait_exit__') and wait_start is not None:
                    t, offset = wait_start, t - wait_start
                    wait_start = None
            else:
                value = float(value)
            if wait_start is not None:
                t = wait_start
            lines.append([t, identifier, value])
    except Exception:
        logging.getLogger(__name__).error('parse failed on line %d: %s', idx + 1, line)
        raise
    return lines


def parse(txt):
    """Parse the progress log to a lookup table.

    :param txt: The text to parse.
    :return: The dict mapping 'identifier.value' to the fraction done.
    """
    lines = parse_lines(txt)
    tbl = {}
    time_end = lines[-1][0]
    for idx in range(len(lines)):
        t, identifier, value = lines[idx]
        tbl['%s.%s' % (identifier, value)] = t / time_end
    return tbl


def lookup(tbl, identifier, value):
    if isinstance(value, float):
        s_enter = tbl.get(identifier + '.__enter__')
        s_exit = tbl.get(identifier + '.__exit__')
        if s_enter is not None and s_exit is not None:
            return (s_exit - s_enter) * value + s_enter
    else:
        s = '%s.%s' % (identifier, value)
        return tbl.get(s)


class Progress:

    def __init__(self, txt):
        self.tbl = parse(txt)

    def lookup(self, identifier, value):
        return lookup(self.tbl, identifier, value)
