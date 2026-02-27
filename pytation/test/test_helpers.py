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


from pytation.loader import validate


def make_station(name='test', tests=None, devices=None, env=None, **overrides):
    """Build a minimal valid station dict and validate it."""
    station = {
        'name': name,
        'full_name': f'Test station {name}',
        'states': {
            'initialize': {}, 'wait_for_dut': {}, 'in_progress': {},
            'pass': {}, 'fail': {}, 'abort': {},
        },
        'tests': tests or [],
        'devices': devices or [],
        'env': env or {},
    }
    station.update(overrides)
    return validate(station)
