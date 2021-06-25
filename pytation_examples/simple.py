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

import os
import logging
import time
from pytation import Context

MYPATH = os.path.dirname(os.path.abspath(__file__))


class Eq1:
    NAME = 'Equipment Example 1'

    def __init__(self):
        self._log = logging.getLogger(__name__ + '.Eq1')

    def setup(self, context: Context, config=None):
        self._log.info('setup')

    def restore(self):
        self._log.info('restore')

    def teardown(self):
        self._log.info('teardown')


class Dut1:
    NAME = 'Device under Test Example 1'

    def __init__(self):
        self._log = logging.getLogger(__name__ + '.Dut1')

    def setup(self, context: Context, config=None):
        self._log.info('setup')

    def restore(self):
        self._log.info('restore')

    def teardown(self):
        self._log.info('teardown')


def suite_setup(context, config=None):
    context.state = 'wait_for_dut'
    context.wait_for_user()
    context.state = 'in_progress'


def suite_teardown(context, config=None):
    if context.result == 0:
        context.state = 'pass'
    else:
        context.state = 'fail'
    context.wait_for_user()


def enter_serial_number(context, config=None):
    serial_number = context.prompt('Enter serial number')
    context.env['name'] = serial_number
    context.env['serial_number'] = serial_number
    return 0, {'serial_number': serial_number}


def test1(context, config=None):
    config = {} if config is None else config
    _log = logging.getLogger(__name__ + '.test1')
    mode = config.get('mode', 'normal')
    delay = float(config.get('delay', 0.01))
    count = int(config.get('count', 50))
    _log.info('start: mode=%s', mode)
    for i in range(count):
        time.sleep(delay)
        context.progress((i + 1) / count)
    _log.info('stop')
    return 0, {'hello': 'world'}


STATION = {
    'name': 'simple',
    'full_name': 'Simple test station example',
    'env': {},
    'suite_setup': {'fn': suite_setup, 'config': {}},
    'suite_teardown': {'fn': suite_teardown, 'config': {}},
    'states': {
        'initialize': {
            'pixmap': ':/station/initialize.jpg',
            'style': 'QLabel { background-color : yellow; color : black; font-size : 12pt; }',
            'html': '<html><body><h1>Connect Equipment</h1></body></html>',
        },
        'wait_for_dut': {
            'pixmap': ':/station/wait_for_dut.jpg',
            'style': 'QLabel { background-color : #8080ff; color : black; font-size : 12pt; }',
            'html': '<html><body><h1>Connect Device Under Test and press any key</h1></body></html>',
        },
        'in_progress': {
            'pixmap': ':/station/in_progress.jpg',
            'style': 'QLabel { background-color : white; color : black; font-size : 12pt; }',
            'html': '<html><body><h1>Test in Progress</h1></body></html>',
        },
        'pass': {
            'pixmap': ':/station/pass.jpg',
            'style': 'QLabel { background-color : green; color : black; font-size : 12pt; }',
            'html': '<html><body><h1>PASS</h1><p>Disconnect the device and press any key.</p></body></html>',
        },
        'fail': {
            'pixmap': ':/station/fail.jpg',
            'style': 'QLabel { background-color : red; color : black; font-size : 12pt; }',
            'html': '<html><body><h1>FAILED</h1><p>Disconnect the device and press any key.</p></body></html>',
        },
        'abort': {
            'pixmap': ':/station/abort.jpg',
            'style': 'QLabel { background-color : red; color : black; font-size : 12pt; }',
            'html': '<html><body><h1>ABORT</h1><p>Internal error - close & restart</p></body></html>',
        },
    },
    'tests': [
        {'fn': enter_serial_number},
        {'fn': test1},
        {'name': 'long_iter', 'fn': test1, 'config': {'delay': 0.5, 'count': 4}},
    ],
    'devices': [
        {'name': 'eq1', 'clz': Eq1},
        {'name': 'dut', 'clz': Dut1, 'lifecycle': 'suite', 'config': {'mode': 'test'}},
    ],
    'gui_resources': [['pytation_examples', 'pytation_examples.rcc']]  # list of [package, resource]
}
