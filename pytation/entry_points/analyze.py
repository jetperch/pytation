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


from fs.zipfs import ReadZipFS
import glob
import importlib
import json
import os


def parser_config(p):
    """Analyze results from a suite.

    The analysis only works with tests specified as modules.  The module
    must contain a "analyze(context)" function.
    """
    p.add_argument('--test', '-t',
                   action='append',
                   help='Analyze the specified test.  If none specified, analyze all.')
    p.add_argument('path',
                   help='The path to the results.  Alternatively, provide the station name '
                        'which will analyze the most recent run.')
    return on_cmd


def on_cmd(args):
    path = args.path
    if not os.path.isfile(path):
        p = os.path.join(os.path.expanduser('~'), 'pytation', path, 'data', '*.zip')
        files = glob.glob(p)
        path = max(files, key=os.path.getmtime)
        print(path)

    fs = ReadZipFS(file=path)
    with fs.open('tests.json', 'r') as f:
        tests = json.load(f)

    names = [t['name'] for t in tests]
    if args.test is not None:
        for t in args.test:
            if t not in names:
                print(f'Test {t} not found')
                print('\nAvailable tests:')
                print('\n'.join(names))
                return 1

    for t in tests:
        if args.test is not None and t['name'] not in args.test:
            continue
        try:
            m = importlib.import_module(t['name'])
        except ModuleNotFoundError:
            continue
        if not hasattr(m, 'analyze'):
            continue
        t['fs']  = fs.opendir(t['name'])
        print(f'\n### {t["name"]} ###')
        m.analyze(t)
