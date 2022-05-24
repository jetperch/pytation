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


"""
Handle analysis context.
"""

from fs.zipfs import ReadZipFS
import glob
import importlib
import json
import os


class AnalysisContext():
    """Perform an analysis of a previous suite execution.

    :param path: The path to the test's output ".zip" file.
    :param tests: The list of test names to analyze.
        None or empty list analyzes all.
    """

    def __init__(self, path):
        self.env: dict[str: object] = {}  #: The station environment
        self.test_config: dict[str: object] = {}  #: The test configuration.
        self.result = None   # 0 or test error code
        self.details = None  # The arbitrary test details
        if not os.path.isfile(path):
            raise ValueError(f'path not found: {path}')
        self._fs = ReadZipFS(file=path)  #: The filesystem for the test
        with self._fs.open('tests.json', 'rt') as f:
            self.tests = json.load(f)
        with self._fs.open('station.json', 'rt') as f:
            self._station = json.load(f)
        self.env = self._station.get('env', {})

    def expand_str(self, s):
        return s.format(**self.env)

    def path(self, key):
        value = self._station['paths'][key]
        return value.format(**self._station['paths'], **self.env)

    def run(self, tests=None):
        rc = 0
        names = [t['name'] for t in self.tests]
        if tests is not None and len(tests):
            missing = []
            for t in tests:
                if t not in names:
                    missing.append(t)
            if len(missing):
                missing = "\n  ".join(missing)
                available = "\n  ".join(names)
                msg = f'Tests not found:\n  {missing}\nTests available:\n  {available}\n'
                print(msg)
                raise KeyError(msg)
        else:
            tests = names

        for t in self.tests:
            if t['name'] not in tests:
                continue
            try:
                m = importlib.import_module(t['name'])
            except ModuleNotFoundError:
                continue
            if not hasattr(m, 'analyze'):
                continue
            self.fs = self._fs.opendir(t['name'])
            try:
                self.result = t['result']
                self.details = t['detail']
                self.config = t['config']
                print(f'\n### {t["name"]} ###')
                rc = m.analyze(self)
                if rc:
                    break
            finally:
                self.result = None
                self.details = None
                self.config = None
                self.fs.close()
                self.fs = None
        return rc
