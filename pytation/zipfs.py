# Copyright 2026 Jetperch LLC
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


"""Stdlib-backed ZIP filesystem shim.

Replaces the narrow subset of PyFilesystem2 that pytation (and its consumers)
actually use: ``.open(name, mode)`` as a context manager, ``.makedir(name)``
/ ``.opendir(name)`` returning a subfilesystem, and ``.close()``.

The write side stages to a temporary directory so that multiple files may be
kept open simultaneously (pytation keeps ``log.txt`` and ``progress.csv`` open
for the entire suite). On ``close()``, the staged tree is packed into the
destination ZIP archive.
"""

import io
import os
import tempfile
import zipfile


_TEXT_ENCODING = 'utf-8'


def _parse_mode(mode):
    """Normalize a mode string to (write, binary).

    Accepts ``''``, ``'r'``, ``'rt'``, ``'rb'``, ``'w'``, ``'wt'``, ``'wb'``.
    """
    if mode == '' or mode is None:
        return False, False
    write = 'w' in mode
    read = 'r' in mode
    binary = 'b' in mode
    if write and read:
        raise ValueError(f'unsupported mode: {mode!r}')
    if not write and not read:
        read = True
    return write, binary


class ZipWriteFS:
    """Write-side ZIP filesystem backed by a staging temp directory."""

    def __init__(self, path, compression=zipfile.ZIP_STORED, _root=None, _prefix=''):
        self._prefix = _prefix  # forward-slash, no leading slash, '' or 'sub/'
        if _root is None:
            self._path = path
            self._compression = compression
            self._tempdir = tempfile.TemporaryDirectory(prefix='pytation_')
            self._staging = self._tempdir.name
            self._root = self
        else:
            self._root = _root
            self._staging = _root._staging

    def _staged_path(self, name):
        rel = (self._prefix + name).replace('/', os.sep)
        return os.path.join(self._staging, rel)

    def open(self, name, mode='r'):
        write, binary = _parse_mode(mode)
        path = self._staged_path(name)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if binary:
            return open(path, 'wb' if write else 'rb')
        return open(path, 'wt' if write else 'rt', encoding=_TEXT_ENCODING)

    def makedir(self, name):
        prefix = self._prefix + name.rstrip('/') + '/'
        os.makedirs(os.path.join(self._staging, prefix.replace('/', os.sep)),
                    exist_ok=True)
        return ZipWriteFS(None, _root=self._root, _prefix=prefix)

    def close(self):
        if self._root is not self:
            return
        try:
            with zipfile.ZipFile(self._path, 'w', compression=self._compression) as zf:
                for dirpath, _dirnames, filenames in os.walk(self._staging):
                    for fname in filenames:
                        abs_path = os.path.join(dirpath, fname)
                        rel = os.path.relpath(abs_path, self._staging)
                        arcname = rel.replace(os.sep, '/')
                        zf.write(abs_path, arcname)
        finally:
            self._tempdir.cleanup()


class ZipReadFS:
    """Read-side ZIP filesystem backed by ``zipfile.ZipFile``."""

    def __init__(self, file, _root=None, _prefix=''):
        self._prefix = _prefix
        if _root is None:
            self._zf = zipfile.ZipFile(file, 'r')
            self._root = self
        else:
            self._root = _root
            self._zf = _root._zf

    def open(self, name, mode='r'):
        _write, binary = _parse_mode(mode)
        arcname = self._prefix + name
        raw = self._zf.open(arcname, 'r')
        if binary:
            return raw
        return io.TextIOWrapper(raw, encoding=_TEXT_ENCODING)

    def opendir(self, name):
        prefix = self._prefix + name.rstrip('/') + '/'
        return ZipReadFS(None, _root=self._root, _prefix=prefix)

    def close(self):
        if self._root is self:
            self._zf.close()
