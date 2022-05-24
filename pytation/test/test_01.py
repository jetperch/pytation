# Copyright 2021-2022 Jetperch LLC
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


EXPECT = {
    'update': 'my_update',
    'default': 'my_default',
    'override': 'their_override',
}


def analyze(context):
    c = context.config
    for key, value in EXPECT.items():
        if c[key] != value:
            return 1
    if context.result != 42:
        return 1
    if context.details != 'my_details':
        return 1
    return context.result

def run(context):
    c = context.config
    c.setdefault('default', 'my_default')
    c.setdefault('override', 'override')
    c['update'] = 'my_update'
    return 42, 'my_details'
