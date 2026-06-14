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


"""Background upload of suite result ZIP files.

This module provides the destination-agnostic orchestration
(:class:`UploadWorker`) plus built-in uploader implementations
(:class:`S3Uploader`, :class:`UrlUploader`).

The worker watches an output directory for ``*.zip`` files and uploads them
oldest-first by delegating each single-file transfer to an ``upload(path)``
callable.  Network outages are tolerated: files accumulate locally and upload
when connectivity returns.  A local file is deleted only after the callable
confirms receipt (returns True), so the remote store is the source of truth
and local disk is a transient buffer.

Built-in uploaders subclass :class:`pytation.api.Uploader`.  A station declares
one like a device::

    from pytation.uploader import S3Uploader

    station = {
        'uploader': {
            'clz': S3Uploader,
            'config': {'bucket': 'my-data', 'prefix': 'stations/st1/'},
        },
    }
"""

import glob
import logging
import os
import threading
import urllib.request

from pytation import api


_log = logging.getLogger('pytation.uploader')


class UploadWorker:
    """Watch a directory and upload ``*.zip`` files oldest-first.

    :param watch_dir: Directory to watch for new ``*.zip`` files.
    :param upload: Callable ``upload(path) -> bool``.  Returns True when the
        file is confirmed uploaded (the worker then deletes it); returns False
        or raises to retain the file and retry after ``retry_interval``.
    :param poll_interval: Seconds between directory scans when healthy.
    :param retry_interval: Seconds to wait before retrying after a failure.
    """

    def __init__(self, watch_dir, upload, poll_interval=10.0, retry_interval=30.0):
        self._watch_dir = watch_dir
        self._upload = upload
        self._poll_interval = float(poll_interval)
        self._retry_interval = float(retry_interval)
        self._stop_event = threading.Event()
        self._thread = None

    @property
    def pending_count(self):
        """The number of ``*.zip`` files remaining in the watch directory."""
        return len(self._pending())

    def start(self):
        """Start the background worker thread."""
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name='upload', daemon=True)
        self._thread.start()

    def stop(self, timeout=30.0):
        """Stop the worker thread and run one final upload pass.

        :param timeout: Maximum seconds to wait for the worker to finish.
        """
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=timeout)
        self._thread = None
        # Final best-effort pass to catch files that arrived during shutdown.
        try:
            self._upload_pending(until_stop=False)
        except Exception:  # pragma: no cover - shutdown best effort
            _log.warning('final upload pass failed', exc_info=True)

    def _pending(self):
        """Return pending ``*.zip`` paths sorted oldest-first by mtime."""
        paths = glob.glob(os.path.join(self._watch_dir, '*.zip'))
        return sorted(paths, key=lambda p: os.path.getmtime(p))

    def _run(self):
        _log.info('upload worker watching %s', self._watch_dir)
        while not self._stop_event.is_set():
            if self._pending():
                ok = self._upload_pending()
                # Back off when a (retryable) failure stopped the batch — most
                # likely a network outage or a credential problem to fix.
                interval = self._poll_interval if ok else self._retry_interval
            else:
                interval = self._poll_interval
            self._stop_event.wait(interval)

    def _upload_pending(self, until_stop=True):
        """Upload each pending file oldest-first; stop on the first failure.

        :param until_stop: When True, abort the batch promptly if a stop has
            been requested.  The shutdown pass sets this False to drain.
        :return: True if the batch drained (or was cleanly interrupted),
            False if a retryable failure stopped it (caller should back off).
        """
        for path in self._pending():
            if until_stop and self._stop_event.is_set():
                return True
            if not self._upload_one(path):
                return False  # leave the rest on disk; retried next pass
        return True

    def _upload_one(self, path):
        """Upload a single file and delete it on confirmed receipt.

        :return: True on success, False on a (retryable) failure.
        """
        try:
            ok = self._upload(path)
        except FileNotFoundError:
            _log.warning('file vanished before upload: %s', path)
            return True  # nothing to do; do not block the queue
        except Exception:
            _log.warning('upload failed, will retry: %s', path, exc_info=True)
            return False
        if not ok:
            _log.warning('upload not confirmed, will retry: %s', path)
            return False
        try:
            os.remove(path)
        except OSError:
            _log.warning('uploaded but could not delete: %s', path,
                         exc_info=True)
        _log.info('uploaded %s', os.path.basename(path))
        return True


class S3Uploader(api.Uploader):
    """Upload result files to an Amazon S3 (or S3-compatible) bucket.

    Config keys: ``bucket`` (required), ``prefix`` (optional key prefix),
    ``region`` (optional), ``endpoint_url`` (optional, for MinIO etc.).

    Requires ``boto3`` (``pip install pytation[s3]``); it is imported lazily
    so it is only needed when an S3 uploader is actually used.
    """

    NAME = 's3'

    def setup(self, context, config):
        import boto3  # lazy: only required when S3 is configured
        self._bucket = config['bucket']
        self._prefix = config.get('prefix', '') or ''
        self._client = boto3.client(
            's3', region_name=config.get('region'),
            endpoint_url=config.get('endpoint_url'))

    def upload(self, path):
        key = self._prefix + os.path.basename(path)
        with open(path, 'rb') as f:
            resp = self._client.put_object(
                Bucket=self._bucket, Key=key, Body=f)
        return bool(resp.get('ETag'))

    def teardown(self):
        self._client = None


class UrlUploader(api.Uploader):
    """Upload result files to an HTTP(S) endpoint using the stdlib.

    Config keys: ``url`` (required; may contain a ``{name}`` placeholder for
    the file basename), ``method`` (default ``'PUT'``), ``headers`` (optional
    dict), ``timeout`` (optional seconds, default 30).

    When the ``PYTATION_URL_UPLOADER_TOKEN`` environment variable is set, a
    ``Authorization: Bearer <token>`` header is sent.  An explicit
    ``Authorization`` entry in ``headers`` takes precedence.

    The upload is confirmed when the server responds with a 2xx status.
    """

    NAME = 'url'
    TOKEN_ENV = 'PYTATION_URL_UPLOADER_TOKEN'

    def setup(self, context, config):
        self._url = config['url']
        self._method = config.get('method', 'PUT')
        self._headers = config.get('headers') or {}
        self._timeout = config.get('timeout', 30.0)
        self._token = os.environ.get(self.TOKEN_ENV)

    def upload(self, path):
        url = self._url.format(name=os.path.basename(path))
        with open(path, 'rb') as f:
            data = f.read()
        headers = {'Content-Type': 'application/zip'}
        if self._token:
            headers['Authorization'] = f'Bearer {self._token}'
        headers.update(self._headers)  # explicit config headers win
        req = urllib.request.Request(
            url, data=data, method=self._method, headers=headers)
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return 200 <= resp.status < 300

    def teardown(self):
        pass
