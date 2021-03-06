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

"""Define the time operations for this package."""


import datetime
import time


def now():
    """Get the current time as seconds since the POSIX epoch (UTC)."""
    return time.time()


def time_to_filename(t=None):
    if t is None:
        t = now()
    dt = datetime.datetime.utcfromtimestamp(t)
    return dt.strftime('%Y%m%d_%H%M%S_%f')


def filename_to_time(s):
    s = s + '+00:00'
    dt = datetime.datetime.strptime(s, '%Y%m%d_%H%M%S_%f%z')
    return dt.timestamp()


def time_to_isostr(t=None):
    if t is None:
        t = now()
    dt = datetime.datetime.utcfromtimestamp(t)
    dt = dt.isoformat() + 'Z'
    return dt


def isostr_to_time(s):
    if s[-1] == 'Z':
        s = s[:-1] + '+00:00'
    dt = datetime.datetime.fromisoformat(s)
    return dt.timestamp()
