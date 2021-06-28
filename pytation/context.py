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


"""
Handle test context.
"""

from pytation import time, __version__
from pytation.progress import Progress
from pytation.loader import SETUP_TEARDOWN_FN, ENV_EXCLUDE
from fs.zipfs import WriteZipFS
import collections
import importlib
import zipfile
import json
import os
import logging


_FILE_FMT = "%(levelname)s:%(asctime)s:%(filename)s:%(lineno)d:%(name)s:%(message)s"
_VALID_CHARS = \
    '-_. ' \
    + ''.join([chr(ord('a') + a) for a in range(26)]) \
    + ''.join([chr(ord('a') + a) for a in range(26)]) \
    + ''.join([chr(ord('0') + a) for a in range(10)])


def sanitize_filename(s):
    s = ''.join(c for c in s if c in _VALID_CHARS)
    s = s.replace(' ', '_')  # spaces to underscore
    s = s[:64]  # truncate as needed
    return s


def _time_finalize(d):
    time_end = time.now()
    time_start = time.str_to_time(d['start'])
    duration = (time_end - time_start).total_seconds()
    d['end'] = time_end.isoformat()
    d['duration'] = str(duration)
    return d


def _json_default(obj):
    return '__pyobject__'


class DictReadOnlyWrapper(collections.Mapping):

    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)


class Context:
    """Context for a test station.

    :param station: The Station definition, which should already be validated
        using pytation.loader.validate.
    :ivar env: The environment, which is initialized when the station starts.
        The suite and tests may modify the environment to convey information,
        but the environment is reinitialized to the station defaults at the
        start of every suite.
    :ivar do_quit: A boolean value to indicate that the station should quit.
    """

    def __init__(self, station):
        self._log = logging.getLogger('pytation')
        self._log.setLevel(logging.DEBUG)
        self._env = {}  # cache station init to restore after each suite
        self.env: dict[str: object] = station['env']
        self._station = station

        self._progress: Progress = None
        self._devices: dict[str, object] = {}  #: string to device object
        self.devices: dict[str, object] = DictReadOnlyWrapper(self._devices)  #: dict[str, object]
        self._fs = None
        self._cbk = {'progress': [], 'state': [], 'wait_for_user': [], 'prompt': []}
        self._progress_data = []
        self._progress_file = None
        self._progress_cbk = None
        self._station_log_handler = None
        self._suite_logfile = None
        self._suite_log_file_handler = None
        self._tests = []     # The list of test outputs
        self._sections = []  # list of [name, start_time]
        self._state = None
        self.do_quit: bool = False  #: Set to True to quit, thread safe quit mechanism

    def __repr__(self):
        return 'Context(name=%s)' % self._station['name']

    @property
    def state(self):
        """The current state"""
        return self._state

    @state.setter
    def state(self, s):
        """Update the state and notify all callbacks."""
        if s not in self._station['states']:
            raise RuntimeError(f'undefined state: {s}')
        self._log.info('Enter state %s', s)
        self._state = s
        state_info = self._station['states'][s]
        for fn in self._cbk['state']:
            try:
                fn(state_info)
            except Exception:
                self._log.exception('during state callback')

    def _create_file_path_as_needed(self, path):
        dirpath = os.path.dirname(path)
        if not os.path.exists(dirpath):
            self._log.info('Creating path %s', dirpath)
            os.makedirs(dirpath, exist_ok=True)

    def expand_str(self, s):
        """Expand a string substituting environment variables.

        :param s: A string suitable for python's format with {varname}.
        :return: The string "s" with all {varname} replaced using this
            context's environment variables.
        """
        return s.format(**self.env)

    def _station_log_open(self):
        path = os.path.normpath(self.path('log'))
        self._create_file_path_as_needed(path)
        file_fmt = logging.Formatter(_FILE_FMT)
        file_hnd = logging.FileHandler(filename=path)
        file_hnd.setFormatter(file_fmt)
        file_hnd.setLevel(logging.DEBUG)
        self._station_log_handler = file_hnd
        logging.getLogger().addHandler(file_hnd)

    def _station_log_close(self):
        if self._station_log_handler is not None:
            logging.getLogger().removeHandler(self._station_log_handler)
            self._station_log_handler.close()
            self._station_log_handler = None

    def path(self, key):
        value = self._station['paths'][key]
        return value.format(**self._station['paths'], **self.env)

    def device_open(self, name):
        self._log.info('device_open(%s)', name)
        d = self._station['devices'][name]
        clz = d['clz']
        if isinstance(clz, str):
            parts = clz.split('.')
            class_name = parts[-1]
            module_name = '.'.join(parts[:-1])
            module = importlib.import_module(module_name)
            clz = getattr(module, class_name)
        if isinstance(clz, type):
            device = clz()
        elif hasattr(clz, 'setup'):
            device = clz
        else:
            raise RuntimeError(f'Invalid device clz for {name}')
        device.setup(self, d['config'])
        self._devices[name] = device
        return device

    def device_close(self, name):
        self._log.info('device_close(%s)', name)
        try:
            device = self._devices.pop(name)
        except KeyError:
            self._log.warning('device_close(%s), but not found', name)
            return
        try:
            device.teardown()
        except Exception:
            self._log.exception('device_close(%s)', name)

    def _devices_open(self, lifecycle, device_list=None):
        if device_list is None:
            return
        elif device_list is True:
            device_list = list(self._station['devices'].keys())
        for name, d in self._station['devices'].items():
            if d['lifecycle'] == lifecycle and name in device_list:
                self.device_open(name)

    def _devices_close(self, lifecycle):
        for name, d in self._station['devices'].items():
            if d['lifecycle'] == lifecycle and name in self._devices:
                self.device_close(name)

    def test_run(self, d):
        """Run a test.

        :param d: The test configuration.  The following keys are used:
            - name: The name used by the suite to save data (optional)
            - fn: The test function required.
            - config: The config dict to pass to fn (optional)
        :return: 0 on success or error code.
        """
        if d is None:
            return
        result = -1
        detail = {}
        fn = d['fn']
        if 'name' in d:
            name = d['name']
        elif hasattr(fn, 'NAME'):
            name = fn.NAME
        else:
            name = fn.__name__
        d['name'] = name
        config = d.get('config', {})
        fname = sanitize_filename(name)
        self._log.info('--- TEST START %s --- ', name)

        try:
            self._devices_open('test', d['devices'])

            if self._fs is not None and name not in SETUP_TEARDOWN_FN:
                config['fs'] = self._fs.makedir(fname)

            for d in d['devices']:
                if d not in self._devices:
                    raise RuntimeError(f'required device {d} not found')

            with self.section(name):
                result = fn(self, config)
                if result is None:
                    result = 0
                elif not isinstance(result, int):
                    result, detail = result
        except Exception:
            self._log.exception(f'While running test {name}')
        finally:
            self._devices_close('test')
            self._log.info('--- TEST DONE %s with status %s --- ', name, result)
            test = {
                'name': name,
                'result': result,
                'detail': detail
            }
            self._tests.append(test)

        for device_name, device in self._devices.items():
            try:
                device.restore()
            except Exception:
                self._log.exception('Device restore for %s', device_name)
        return result

    def _progress_exists(self):
        path = os.path.normpath(self.path('progress'))
        return os.path.isfile(path)

    def _progress_open(self):
        path = os.path.normpath(self.path('progress'))
        self._create_file_path_as_needed(path)
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                self._progress = Progress(f.read())

    def _progress_save(self):
        path = os.path.normpath(self.path('progress'))
        self._create_file_path_as_needed(path)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(''.join(self._progress_data))
        self._progress = None  # trigger reload

    def station_start(self):
        """Start the test station.

        :see: station_run()
        :note: Included in station_run().
        """
        self._station_log_open()
        self._log.info('pytation version = %s', __version__)
        self._devices_open('station', True)
        self.test_run(self._station.get('station_setup'))
        self._env = dict(self.env)

    def station_stop(self):
        """Stop the test station.

        :see: station_run()
        :note: Included in station_run().
        """
        self.test_run(self._station.get('station_teardown'))
        self._devices_close('station')
        self._station_log_close()

    def station_run(self, count=None):
        """Run the test suite using this station.

        :param count: The number of times to run the test suite.
            None (default) runs indefinitely.
        """
        self.station_start()
        c = 0
        try:
            while count is None or c < count:
                if self.do_quit:
                    break
                self.suite_run()
                c += 1
        except KeyboardInterrupt:
            self._log.info('KeyboardInterrupt stopped station')
        finally:
            self.station_stop()

    def _suite_time_update(self):
        t = time.now()
        self.env['suite_timestamp'] = t
        self.env['suite_timestr'] = time.time_to_filename(t)
        self.env['suite_isostr'] = time.time_to_isostr(t)

    def _suite_file_open(self):
        path = os.path.normpath(self.path('output'))
        self._log.info('suite file path = %s', path)
        self._create_file_path_as_needed(path)
        self._fs = WriteZipFS(file=path,
                              compression=zipfile.ZIP_STORED,
                              temp_fs='temp://pytation')
        self._station['env'] = dict([(key, value) for key, value in self.env.items() if key not in ENV_EXCLUDE])
        with self._fs.open('station.json', 'wt') as f:
            json.dump(self._station, f, indent=2, default=_json_default)
        self._station['env'] = {}

        # configure logging to ZIP file
        self._suite_logfile = self._fs.open('log.txt', 'wt')
        ch = logging.StreamHandler(self._suite_logfile)
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
        ch.setFormatter(formatter)
        logging.getLogger().addHandler(ch)
        self._suite_log_file_handler = ch

    def _suite_start(self):
        self.env = dict(self._env)  # restore environment
        self._progress_update(0.0)
        rc = self.test_run(self._station.get('suite_setup'))  # exclude from "progress" and logging
        if rc:
            return rc
        self._suite_time_update()
        self._progress_data = []
        if self._progress is None:
            self._progress_open()
        self._suite_file_open()
        self._devices_open('suite', True)
        self._progress_file = self._fs.open('progress.csv', 'wt')
        self.section_enter('s')
        return 0

    def _progress_file_close(self):
        if self._progress_file:
            self._progress_file.close()
            self._progress_file = None
        if self._progress is None:
            self._progress_save()

    def _suite_stop(self):
        # Progress complete at this stage
        self.section_exit('s')
        self._progress_file_close()
        self._devices_close('suite')
        self._progress_update(1.0)
        self.test_run(self._station.get('suite_teardown'))
        self._log.info('*** %s ***', 'FAIL' if self.result else 'PASS')
        with self._fs.open('tests.json', 'wt') as f:
            json.dump(self._tests, f, indent=2, default=_json_default)
        if self._suite_log_file_handler:
            logging.getLogger().removeHandler(self._suite_log_file_handler)
            self._suite_log_file_handler.close()
            self._suite_log_file_handler = None
        if self._suite_logfile:
            self._suite_logfile.close()
            self._suite_logfile = None

        self._log.info('Writing zip file (may take a while)')
        self._fs.close()
        self._fs = None

    def suite_run(self):
        rc = self._suite_start()
        if rc:
            return rc
        try:
            for d in self._station['tests']:
                if self.do_quit:
                    test = {'name': 'quit', 'result': 1, 'detail': {}}
                    self._tests.append(test)
                    return 1
                self.test_run(self._station.get('test_setup'))
                result = self.test_run(d)
                self.test_run(self._station.get('test_teardown'))
                if result:
                    self.env['error_count'] += 1
                    if self.env['error_count'] >= self.env['error_count_to_halt']:
                        self._log.info('Halting due to %d errors', self.env['error_count'])
                        break
        finally:
            self._suite_stop()
        return self.result

    @property
    def result(self):
        """Get the test result.

        :return: 0 on success or error code on failure.
        """
        for test in self._tests:
            if test['result']:
                return test['result']
        return 0

    def result_str(self):
        s = []
        rv = 0
        s.append('Test results:')
        for test in self._tests:
            s.append('    %s: %s' % (test['name'], test['result']))
            if test['result'] and rv == 0:
                rv = test['result']
        s.append('*** FAIL ***' if rv else '*** PASS ***')
        return '\n'.join(s)

    def section(self, name):
        """Create a new test section as a context manager.

        :param name: The name for the subsection.
        :return: The new subsection for use in a "with" statement

        Example:

            with self.section('firmware_update'):
                do_firmware_update()
        """
        return Section(self, name)

    @property
    def section_name(self):
        return '.'.join([x[0] for x in self._sections])

    def section_enter(self, name):
        """Create a new test section.

        :param name: The name for the subsection.
        :see: section()

        Call section_exit() when done.  Alternatively, consider using
        section().
        """
        t_start = time.now()
        self._sections.append([name, t_start])
        self._log.info('%s start', self.section_name)
        self.progress('__enter__')

    def section_exit(self, name=None):
        self.progress('__exit__')
        if not len(self._sections):
            raise RuntimeError('section_stop with no section')
        section_name = self.section_name
        s_name, start_time = self._sections.pop()
        if name is not None and s_name != name:
            raise RuntimeError(f'section_stop name mismatch: {name} != {s_name}')
        stop_time = time.now()
        duration = stop_time - start_time
        self._log.info('%s: done, duration=%.3f seconds', section_name, duration)

    def _progress_update(self, progress):
        """Inform callbacks about total suite progress.

        :param progress: The total suite progress as a fract from
            0.0 (starting) and 1.0 (done).
        """
        for fn in self._cbk['progress']:
            try:
                fn(progress)
            except Exception:
                self._log.exception('during callback')

    def progress(self, progress):
        """Signal a progress step.

        :param progress: The progress which is one of:
            * A fractional floating point value between 0.0 (starting) and 1.0 (done)
            * An arbitrary string event name
        """
        if self._progress_file is None:
            return
        t = time.now() - self.env['suite_timestamp']
        section_name = self.section_name
        s = '%.3f,%s,%r\n' % (t, section_name, progress)
        self._progress_data.append(s)
        self._progress_file.write(s)
        self._log.debug('%s: %s', section_name, progress)
        if self._progress is not None:
            progress_total = self._progress.lookup(section_name, progress)
            if isinstance(progress_total, float):
                self._progress_update(progress_total)

    def wait_for_user(self):
        self.progress('__wait_enter__ wait_for_user')
        try:
            for fn in self._cbk['wait_for_user']:
                if self.do_quit:
                    raise KeyboardInterrupt('do_quit signaled')
                fn()
        finally:
            self.progress('__wait_exit__ wait_for_user')

    def prompt(self, prompt_str):
        prompt_str = str(prompt_str)
        p = f'prompt({prompt_str})'
        self.progress('__wait_enter__ ' + p)
        try:
            while True:
                for fn in self._cbk['prompt']:
                    if self.do_quit:
                        raise KeyboardInterrupt('do_quit signaled')
                    result_str = fn(prompt_str)
                    if result_str is not None:
                        self._log.info('prompt(%s) -> %s', prompt_str, result_str)
                        return result_str
        finally:
            self.progress('__wait_exit__ ' + p)

    def callback_register(self, name, cbk):
        """Register a function to call on an event.

        :param name: The callback type name, which is one of:
            [progress, state, wait_for_user]
        :param cbk: The function to call as needed.  The exact function
            prototype depends upon the name:

            - progress(progress) -> ignored:
              - progress: The progress value which is either a float
                fraction from 0.0 (start) to 1.0 (complete).
            - state(state_info) -> ignored
              - state_info: dict containing the state information from the
                station definition.  Use state_info['name'] to get the
                new state name.
            - wait_for_user() -> None
              This callback may block, but in multithreaded implementations
              it should periodically check self.do_quit.  If do_quit is
              signalled, then the callback should raise KeyboardInterrupt.
              The recommended polling interval is 10 milliseconds to
              keep the thread responsive to quit.
            - prompt(prompt_str) -> str
              - prompt_str: The string to display to the user
              - returns the string entered by the user or None on error.
        :raise KeyError: if name is not valid
        """
        self._cbk[name].append(cbk)

    def callback_unregister(self, name, cbk):
        """Remove a previously registered callback function.

         :param name: The callback type name.
         :param cbk: The function previous registered using callback_register().
         :raise KeyError: if name is not valid.
         """
        self._cbk[name] = [fn for fn in self._cbk[name] if fn != cbk]


class Section:

    def __init__(self, context, name):
        self._context = context
        self._name = name

    def __str__(self):
        return f'Section({self._name})'

    def __enter__(self):
        self._context.section_enter(self._name)
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self._context.section_exit(self._name)

    def section(self, name):
        """Create a new test subsection.

        :param name: The name for the subsection.
        :return: The new subsection for use in a "with" statement
        """
        return self._context.section(name)

    def progress(self, progress):
        """Signal a progress step.

        :param progress: The progress which is one of:
            * A fractional floating point value between 0.0 (starting) and 1.0 (done)
            * An arbitrary string event name
        """
        return self._parent.progress(progress)
