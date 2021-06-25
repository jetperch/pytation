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


import argparse
import importlib


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


def load(args):
    parts = args.station.split('.')
    def_name = parts[-1]
    module_name = '.'.join(parts[:-1])
    module = importlib.import_module(module_name)
    station = getattr(module, def_name)
    return station
