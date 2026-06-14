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

import os
import sys
import tempfile
import time
import unittest
import urllib.error
import zipfile
from unittest.mock import MagicMock, patch

from pytation import api, loader
from pytation.context import Context
from pytation.uploader import UploadWorker, S3Uploader, UrlUploader


def _write_zip(directory, name, mtime=None):
    path = os.path.join(directory, name)
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('data.txt', name)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _fake_boto3(client):
    module = MagicMock(name='boto3')
    module.client.return_value = client
    return module


def _wait_gone(path, timeout=5.0):
    deadline = time.time() + timeout
    while os.path.exists(path) and time.time() < deadline:
        time.sleep(0.02)


class _Recorder:
    """A fake transport callable that records uploads and can fail."""

    def __init__(self, result=True):
        self.result = result          # bool or Exception to raise
        self.calls = []

    def __call__(self, path):
        self.calls.append(path)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class TestUploadWorker(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='uptest_')
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_upload_and_delete(self):
        path = _write_zip(self.dir, 'a.zip')
        rec = _Recorder(True)
        UploadWorker(self.dir, rec)._upload_pending()
        self.assertEqual([path], rec.calls)
        self.assertFalse(os.path.exists(path))

    def test_failure_retains_file(self):
        path = _write_zip(self.dir, 'a.zip')
        rec = _Recorder(ConnectionError('down'))
        UploadWorker(self.dir, rec)._upload_pending()
        self.assertTrue(os.path.exists(path))

    def test_not_confirmed_retains_file(self):
        path = _write_zip(self.dir, 'a.zip')
        rec = _Recorder(False)
        UploadWorker(self.dir, rec)._upload_pending()
        self.assertTrue(os.path.exists(path))

    def test_oldest_first_order(self):
        base = 1_000_000.0
        _write_zip(self.dir, 'new.zip', mtime=base + 100)
        _write_zip(self.dir, 'old.zip', mtime=base)
        _write_zip(self.dir, 'mid.zip', mtime=base + 50)
        rec = _Recorder(True)
        UploadWorker(self.dir, rec)._upload_pending()
        names = [os.path.basename(p) for p in rec.calls]
        self.assertEqual(['old.zip', 'mid.zip', 'new.zip'], names)

    def test_failure_stops_batch(self):
        _write_zip(self.dir, 'a.zip', mtime=1.0)
        _write_zip(self.dir, 'b.zip', mtime=2.0)
        rec = _Recorder(ConnectionError('down'))
        UploadWorker(self.dir, rec)._upload_pending()
        self.assertEqual(1, len(rec.calls))

    def test_pending_count(self):
        _write_zip(self.dir, 'a.zip')
        _write_zip(self.dir, 'b.zip')
        self.assertEqual(2, UploadWorker(self.dir, _Recorder()).pending_count)

    def test_start_drains_then_stop(self):
        path = _write_zip(self.dir, 'a.zip')
        worker = UploadWorker(self.dir, _Recorder(True), poll_interval=0.05)
        worker.start()
        _wait_gone(path)
        worker.stop(timeout=5.0)
        self.assertFalse(os.path.exists(path))


class TestS3Uploader(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='s3test_')
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _setup(self, client, config):
        up = S3Uploader()
        with patch.dict(sys.modules, {'boto3': _fake_boto3(client)}):
            up.setup(None, config)
        return up

    def test_upload_confirmed(self):
        client = MagicMock()
        client.put_object.return_value = {'ETag': '"abc"'}
        up = self._setup(client, {'bucket': 'b', 'prefix': 'p/'})
        path = _write_zip(self.dir, 'a.zip')
        self.assertTrue(up.upload(path))
        kwargs = client.put_object.call_args.kwargs
        self.assertEqual('b', kwargs['Bucket'])
        self.assertEqual('p/a.zip', kwargs['Key'])

    def test_upload_no_etag(self):
        client = MagicMock()
        client.put_object.return_value = {}
        up = self._setup(client, {'bucket': 'b'})
        self.assertFalse(up.upload(_write_zip(self.dir, 'a.zip')))


class TestUrlUploader(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='urltest_')
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _urlopen(self, status):
        cm = MagicMock()
        cm.__enter__.return_value.status = status
        m = MagicMock(return_value=cm)
        return m

    def test_2xx_confirmed(self):
        up = UrlUploader()
        up.setup(None, {'url': 'http://host/{name}'})
        path = _write_zip(self.dir, 'a.zip')
        m = self._urlopen(200)
        with patch('urllib.request.urlopen', m):
            self.assertTrue(up.upload(path))
        self.assertEqual('http://host/a.zip', m.call_args.args[0].full_url)

    def test_bearer_token_from_env(self):
        up = UrlUploader()
        with patch.dict(os.environ, {'PYTATION_URL_UPLOADER_TOKEN': 'secret'}):
            up.setup(None, {'url': 'http://host/{name}'})
        m = self._urlopen(200)
        with patch('urllib.request.urlopen', m):
            up.upload(_write_zip(self.dir, 'a.zip'))
        req = m.call_args.args[0]
        # urllib normalizes header keys to title-case
        self.assertEqual('Bearer secret', req.get_header('Authorization'))

    def test_no_token_no_auth_header(self):
        up = UrlUploader()
        env = {k: v for k, v in os.environ.items()
               if k != 'PYTATION_URL_UPLOADER_TOKEN'}
        with patch.dict(os.environ, env, clear=True):
            up.setup(None, {'url': 'http://host/{name}'})
        m = self._urlopen(200)
        with patch('urllib.request.urlopen', m):
            up.upload(_write_zip(self.dir, 'a.zip'))
        self.assertIsNone(m.call_args.args[0].get_header('Authorization'))

    def test_config_header_overrides_token(self):
        up = UrlUploader()
        with patch.dict(os.environ, {'PYTATION_URL_UPLOADER_TOKEN': 'secret'}):
            up.setup(None, {'url': 'http://host/{name}',
                            'headers': {'Authorization': 'Bearer explicit'}})
        m = self._urlopen(200)
        with patch('urllib.request.urlopen', m):
            up.upload(_write_zip(self.dir, 'a.zip'))
        self.assertEqual('Bearer explicit',
                         m.call_args.args[0].get_header('Authorization'))

    def test_non_2xx_not_confirmed(self):
        up = UrlUploader()
        up.setup(None, {'url': 'http://host/{name}'})
        with patch('urllib.request.urlopen', self._urlopen(500)):
            self.assertFalse(up.upload(_write_zip(self.dir, 'a.zip')))

    def test_network_error_raises(self):
        up = UrlUploader()
        up.setup(None, {'url': 'http://host/{name}'})
        m = MagicMock(side_effect=urllib.error.URLError('down'))
        with patch('urllib.request.urlopen', m):
            with self.assertRaises(urllib.error.URLError):
                up.upload(_write_zip(self.dir, 'a.zip'))


class TestLoaderUploader(unittest.TestCase):

    def test_none_when_absent(self):
        self.assertIsNone(loader._uploader_validate(None))

    def test_name_from_class(self):
        u = loader._uploader_validate({'clz': S3Uploader, 'config': {'bucket': 'b'}})
        self.assertEqual('s3', u['name'])  # from S3Uploader.NAME
        self.assertEqual({'bucket': 'b'}, u['config'])

    def test_name_from_string(self):
        u = loader._uploader_validate({'clz': 'pkg.mod.MyUploader'})
        self.assertEqual('MyUploader', u['name'])
        self.assertEqual({}, u['config'])  # default

    def test_validate_passthrough(self):
        station = {
            'name': 'st',
            'tests': [],
            'devices': [],
            'uploader': {'clz': S3Uploader, 'config': {'bucket': 'b'}},
        }
        s = loader.validate(station)
        self.assertEqual('s3', s['uploader']['name'])


class _DummyUploader(api.Uploader):
    NAME = 'dummy'
    events = None  # set per-test to a list

    def setup(self, context, config):
        _DummyUploader.events.append(('setup', config))

    def upload(self, path):
        _DummyUploader.events.append(('upload', os.path.basename(path)))
        return True

    def teardown(self):
        _DummyUploader.events.append(('teardown', None))


class TestContextUploader(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='ctxtest_')
        self.dir = self._tmp.name
        _DummyUploader.events = []

    def tearDown(self):
        self._tmp.cleanup()

    def _station(self):
        out = os.path.join(self.dir, '{suite_timestr}.zip').replace('\\', '/')
        return loader.validate({
            'name': 'st',
            'tests': [],
            'devices': [],
            'paths': {'base_path': self.dir, 'output': out},
            'uploader': {'clz': _DummyUploader, 'config': {'k': 'v'}},
        })

    def test_lifecycle_start_upload_stop(self):
        ctx = Context(self._station())
        ctx._upload_worker = None
        path = _write_zip(self.dir, 'result.zip')
        ctx._uploader_start()
        _wait_gone(path)
        ctx._uploader_stop()
        kinds = [e[0] for e in _DummyUploader.events]
        self.assertEqual('setup', kinds[0])
        self.assertEqual(('setup', {'k': 'v'}), _DummyUploader.events[0])
        self.assertIn('upload', kinds)
        self.assertEqual('teardown', kinds[-1])
        self.assertFalse(os.path.exists(path))


class TestZipfsAtomicWrite(unittest.TestCase):

    def test_replace_leaves_no_tmp(self):
        from pytation.zipfs import ZipWriteFS
        with tempfile.TemporaryDirectory(prefix='zipatomic_') as d:
            path = os.path.join(d, 'out.zip')
            fs = ZipWriteFS(path)
            with fs.open('hello.txt', 'wt') as f:
                f.write('world')
            fs.close()
            self.assertTrue(os.path.exists(path))
            self.assertFalse(os.path.exists(path + '.tmp'))
            with zipfile.ZipFile(path, 'r') as zf:
                self.assertEqual(b'world', zf.read('hello.txt'))


if __name__ == '__main__':
    unittest.main()
