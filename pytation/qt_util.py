# Copyright 2019-2021 Jetperch LLC
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


import os
import shutil
import subprocess


def rcc_path():
    import PySide6
    # As of PySide2 5.15.0, the pyside2-rcc executable ignores the --binary flag
    path = os.path.dirname(PySide6.__file__)
    fname = [n for n in os.listdir(path) if n.startswith('rcc')]
    if len(fname) != 1:
        raise ValueError('Could not find rcc executable')
    return os.path.join(path, fname[0])


def convert_rcc(path):
    """Convert Qt resources definitions (qrc) to binary resource files (rcc).

    :param path: The path to walk for qrc files.
    :return: The list of rcc files created, often used to construct
        a .gitignore file.
    """
    targets = []
    cmd = rcc_path()
    for root, d_names, f_names in os.walk(path):
        for source in f_names:
            _, ext = os.path.splitext(source)
            if ext == '.qrc':
                src = os.path.join(root, source)
                target = os.path.join(os.path.dirname(root), source)
                target = os.path.splitext(target)[0] + '.rcc'
                print(f'Generate {target}')
                rc = subprocess.run([cmd, src, '--binary', '--threshold', '33', '-o', target])
                if rc.returncode:
                    raise RuntimeError('failed on .qrc file')
                targets.append(target)
            else:
                continue
    return targets


def convert_ui(path, resource_import=None):
    """Convert Qt UI definitions (ui) to binary files (py).

    :param path: The path to walk for ui files.
    :param resource_import: The desired resource import python code.
    :return: The list of py files created, often used to construct
        a .gitignore file.
    """
    targets = []
    uic_path = shutil.which('pyside6-uic')
    for root, d_names, f_names in os.walk(path):
        for source in f_names:
            source = os.path.join(root, source)
            source_base, ext = os.path.splitext(source)
            if ext == '.ui':
                target = source_base + '.py'
                print(f'Generate {target}')
                rc = subprocess.run([uic_path, source], stdout=subprocess.PIPE)
                s = rc.stdout.replace(b'\r\n', b'\n').decode('utf-8')
                if resource_import is not None:
                    s = s.replace('\nimport resources_rc\n', resource_import)
                with open(target, 'w', encoding='utf-8') as ftarget:
                    ftarget.write(s)
                targets.append(target)
    return targets


def update_inno_iss(iss_path, version):
    """Update an InnoSetup file with the current version.

    :param iss_path: The path to the InnoSetup ".iss" file.
    :param version: The major.minor.patch version string.
    """
    with open(iss_path, 'r', encoding='utf-8') as fv:
        lines = fv.readlines()
    version_underscore = version.replace('.', '_')
    for idx, line in enumerate(lines):
        if line.startswith('#define MyAppVersionUnderscores'):
            lines[idx] = f'#define MyAppVersionUnderscores "{version_underscore}"\n'
        elif line.startswith('#define MyAppVersion'):
            lines[idx] = f'#define MyAppVersion "{version}"\n'
    with open(iss_path, 'w', encoding='utf-8') as fv:
        fv.write(''.join(lines))
