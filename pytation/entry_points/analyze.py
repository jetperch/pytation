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


from pytation.analysis import AnalysisContext
import glob
import os



def parser_config(p):
    """Analyze results from a suite.

    The analysis only works with tests specified as modules.  The module
    must contain a "analyze(context, config, return_code, result)" function.
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
        print(f'File not found: {path}')
        path = os.path.dirname(path)
        if os.path.isdir(path):
            p = os.path.join(path, '*.zip')
            files = glob.glob(p)
        else:
            p = os.path.join(os.path.expanduser('~'), 'pytation')
            files = glob.glob(p)
        available = max(files, key=os.path.getmtime)
        print('Available files:')
        print(available)
        return 1

    context = AnalysisContext(path)
    return context.run(args.test)
