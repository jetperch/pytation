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


from pytation import Context
import os
import sys


# https://stackoverflow.com/questions/983354/how-to-make-a-script-wait-for-a-pressed-key
def wait_key():
    ''' Wait for a key press on the console and return it. '''
    result = None
    if os.name == 'nt':
        import msvcrt
        ch = msvcrt.getch()
        if ch in [b'\x03', b'\x1b']:
            raise KeyboardInterrupt('user interrupt')
        return ch
    else:
        import termios
        fd = sys.stdin.fileno()

        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)

        try:
            result = sys.stdin.read(1)
        except IOError:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)

    return result



class CliStation:

    def __init__(self, station):
        self._context = Context(station)
        self._context.callback_register('progress', self._on_progress_cbk)
        self._context.callback_register('state', self._on_state_cbk)
        self._context.callback_register('wait_for_user', self._on_wait_for_user_cbk)
        self._context.callback_register('prompt', self._on_prompt_cbk)
        self.wait_for_user = False
        self.prompt_result_str = None

    def _on_progress_cbk(self, progress):
        pass

    def _on_state_cbk(self, state):
        txt = state['html']
        print(f'State => {txt}')

    def _on_wait_for_user_cbk(self):
        print('Press a key...')
        wait_key()

    def _on_prompt_cbk(self, prompt_str):
        return input(prompt_str + '> ')

    def run(self, count=None):
        self._context.station_run(count=count)
        return 0
