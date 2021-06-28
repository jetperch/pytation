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

from pytation import loader
from pytation import cli_runner


def parser_config(p):
    """Graphical user interface runner."""
    loader.parser_config(p)
    return on_cmd


def on_cmd(args):
    station = loader.load(args)
    obj = cli_runner.CliStation(station)
    return obj.run()
