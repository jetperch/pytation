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


from pytation import time
import argparse
import importlib
import os


_LOG_PATH_DEFAULT = '{base_path}/{station}/log/{station_timestr}_{process_id}.log'
_OUTPUT_PATH_DEFAULT = '{base_path}/{station}/data/{suite_timestr}.zip'
_PROGRESS_PATH_DEFAULT = '{base_path}/{station}/progress.csv'
_DEVICE_LIFECYCLE = ['station', 'suite', 'test', 'manual']  # defaults to 'station'
SETUP_TEARDOWN_FN = [
    'station_setup', 'station_teardown',
    'suite_setup', 'suite_teardown',
    'test_setup', 'test_teardown',
]
ENV_EXCLUDE = ['error_count', 'suite_timestamp', 'suite_timestr', 'suite_isostr']
ENV_DEFAULTS = {
    'error_count_to_halt': 1,
}


def parser_config(p: argparse.ArgumentParser, station=None):
    """Add station definition to an argparse.

    :param p: The argument parser instance, which will be modified
        in place.
    :param station: If provided, use the default station value with
        an optional '--station' override.  None (default) adds the station
        as a fixed position argument.
    """
    if station is not None:
        p.add_argument('--station',
                       default=station,
                       help='The fully-qualified station definition')
    else:
        p.add_argument('station',
                       help='The fully-qualified station definition')
    p.add_argument('--exclude',
                   help='The comma-separated list of tests to exlude.  Defaults to "".')
    p.add_argument('--include',
                   help='The comma-separated list of tests to include.  Defaults to all available tests.')


def _states_validate(states):
    # Shallow copy and set name field
    d = {}
    for name, s in states.items():
        s = dict(s)
        s['name'] = name
        d[name] = s
    return d


def _test_validate(test):
    if test is None:
        return None
    t = dict(test)
    fn = t['fn']
    fn_str = '__unknown__'
    if isinstance(fn, str):
        fn_str = fn
        try:
            fn = importlib.import_module(fn)
        except ModuleNotFoundError:
            parts = fn.split('.')
            fn_name = parts[-1]
            module_name = '.'.join(parts[:-1])
            module = importlib.import_module(module_name)
            fn = getattr(module, fn_name)
        t['fn'] = fn
    t.setdefault('name', getattr(fn, 'NAME', getattr(fn, '__name__', fn_str)))
    t.setdefault('config', {})
    if 'devices' not in t:
        t['devices'] = getattr(fn, 'DEVICES', [])
    return t


def _tests_validate(test_list):
    d = []
    names = {}
    for t in test_list:
        t = _test_validate(t)
        name = t['name']
        if name in names:
            raise ValueError(f'Duplicate test name: {name}')
        d.append(t)
        names[name] = t
    return d


def _devices_validate(devices_list):
    """Convert self._station['devices'] from list of defs to dict name:def."""
    devices_map = {}
    for d in devices_list:
        d = dict(d)
        clz = d['clz']
        if 'name' in d:
            name = d['name']
        elif hasattr(clz, 'NAME'):
            name = clz.NAME
        else:
            name = clz.__name__
        d['name'] = name
        d.setdefault('lifecycle', 'station')
        d.setdefault('config', {})
        if d['lifecycle'] not in _DEVICE_LIFECYCLE:
            raise ValueError(f'invalid device lifecycle {d["lifecycle"]} for {name}')

        if name in devices_map:
            raise ValueError('Duplicate device name: %s', name)
        devices_map[name] = d
    return devices_map


def validate(station):
    """Validate the station and fully populate optional fields.

    :param station: The station data structure.
    :return: The station modified in place.
    """
    s = {}
    s['name'] = station['name']
    s['full_name'] = station.get('full_name', station['name'])

    # Construct the environment
    station_start_time = time.now()
    env = {}
    env_no_override = {
        'station': station['name'],
        'process_id': os.getpid(),
        'error_count': 0,

        'station_timestamp': station_start_time,
        'station_timestr': time.time_to_filename(station_start_time),
        'station_isostr': time.time_to_isostr(station_start_time),

        # updated at the start of each suite
        'suite_timestamp': 0,
        'suite_timestr': time.time_to_filename(0),
        'suite_isostr': time.time_to_isostr(0),
    }
    env.update(station.get('env', {}))
    env.update(env_no_override)
    for key, value in ENV_DEFAULTS.items():
        env.setdefault(key, value)
    s['env'] = env

    # Construct the station
    paths = station.get('paths', {})
    paths.setdefault('base_path', os.path.join(os.path.expanduser('~'), 'pytation'))
    paths.setdefault('log', _LOG_PATH_DEFAULT)
    paths.setdefault('output', _OUTPUT_PATH_DEFAULT)
    paths.setdefault('progress', _PROGRESS_PATH_DEFAULT)
    s['paths'] = paths
    s['states'] = _states_validate(station.get('states', {}))
    s['tests'] = _tests_validate(station['tests'])
    s['devices'] = _devices_validate(station['devices'])
    for k in SETUP_TEARDOWN_FN:
        s[k] = _test_validate(station.get(k, None))
    s['gui_resources'] = station.get('gui_resources', [])
    
    return s


def load(args):
    """Load a station from the command-line arguments.

    :param args: The command-line arguments.
    :return: The station, which is also fully validated.
    :see: parser_config()
    :see: validate()
    """
    parts = args.station.split('.')
    def_name = parts[-1]
    module_name = '.'.join(parts[:-1])
    module = importlib.import_module(module_name)
    station = getattr(module, def_name)
    station = validate(station)

    if args.exclude is not None:
        exclude = args.exclude.split(',')
        tests = []
        for test in station['tests']:
            if test['name'] in exclude:
                exclude.remove(test['name'])
            else:
                tests.append(test)
        if len(exclude):
            raise ValueError(f'Excluded tests not found: {exclude}')
        station['tests'] = tests

    if args.include is not None:
        include = args.include.split(',')
        tests = []
        for test in station['tests']:
            if test['name'] in include:
                include.remove(test['name'])
                tests.append(test)
        if len(include):
            raise ValueError(f'Include tests not found: {include}')
        station['tests'] = tests

    return station
