# Uploader

Pytation can automatically upload suite result ZIP files to a remote
destination — Amazon S3, an HTTP endpoint, or anything you implement yourself.
Uploads run in the background and tolerate network outages: result files
accumulate locally and upload when connectivity returns, oldest first. A local
file is deleted only after the destination confirms receipt, so the remote
store is the source of truth and local disk is just a transient buffer.

The feature is **opt-in**. If a station has no `uploader`, behavior is
unchanged and result ZIPs simply accumulate in the output directory.


## Declaring an uploader

An uploader is declared like a device — with a `clz` (a class or a
`'module.Class'` string) and a `config` dict:

```python
from pytation.uploader import S3Uploader

station = {
    'name': 'my_station',
    # ... tests, devices, paths, etc. ...
    'uploader': {
        'clz': S3Uploader,                 # class or 'pytation.uploader.S3Uploader'
        'config': {
            'bucket': 'my-production-data',
            'prefix': 'stations/my_station/',
        },
        # 'name': optional; defaults to clz.NAME or the class name
    },
}
```

Only one uploader is supported per station. The uploader lives for the entire
station run.

The uploader watches the directory portion of the station's `output` path. With
the default output template (`{base_path}/{station}/data/{suite_timestr}.zip`),
that directory is `{base_path}/{station}/data/`.


## The `Uploader` API

An uploader is a class derived from `pytation.Uploader` (a.k.a.
`pytation.api.Uploader`) implementing three methods, mirroring the device
lifecycle:

```python
from pytation import Uploader

class MyUploader(Uploader):
    NAME = 'my'

    def setup(self, context, config):
        """Open/initialize. Called once at station start."""

    def upload(self, path) -> bool:
        """Upload one file. Return True when receipt is confirmed (the
        framework then deletes the local file). Return False or raise to
        retain the file and retry after a back-off. Called from a
        background thread."""

    def teardown(self):
        """Finalize/close. Called once at station stop."""
```

The framework owns the orchestration — the background thread, ZIP detection,
oldest-first ordering, retry/back-off, and deletion after confirmed upload. Your
uploader only has to transfer a single file and report success.


## Behavior

- **Oldest-first ordering.** When a backlog exists (for example after an
  outage), files upload in modification-time order so the destination stays
  chronologically complete.
- **Confirmed delete.** A local ZIP is removed only after `upload()` returns
  `True`. If it returns `False` or raises, the file stays on disk and is
  retried.
- **Outage tolerance.** A failed upload stops the current batch and the worker
  backs off, then resumes from the oldest file. Files are never lost to a
  transient network or credential problem.
- **Atomic result files.** Result ZIPs are written to a temporary file and
  atomically renamed into place, so the worker never observes (or uploads) a
  half-written archive.
- **Startup recovery.** At station start, the worker uploads any pre-existing
  ZIPs (left by previous runs, crashes, or outages) before watching for new
  ones.
- **Non-fatal setup.** If `setup()` fails (e.g. bad credentials), the error is
  logged and testing proceeds; result ZIPs accumulate locally rather than
  blocking the line.

The uploader is started and stopped automatically by `context.py` around each
station run (the same lifecycle that opens and closes devices).


## Built-in: `S3Uploader`

Uploads to Amazon S3 or any S3-compatible store (e.g. MinIO). Depends on
[`boto3`](https://boto3.amazonaws.com/), an optional extra:

```
pip install pytation[s3]
```

`boto3` is imported lazily inside `setup()`, so it is only required when the S3
uploader is actually used.

`config` keys:

| Key | Required | Description |
|-----|----------|-------------|
| `bucket` | yes | Destination S3 bucket name. |
| `prefix` | no | Key prefix prepended to each object (e.g. `stations/st1/`). |
| `region` | no | AWS region. When omitted, boto3's default resolution applies. |
| `endpoint_url` | no | Custom S3 endpoint. Set this for MinIO or other S3-compatible stores. |

Each result ZIP is uploaded to the key `{prefix}{filename}` and confirmed via
the `ETag` in the `put_object` response.

### AWS S3 setup

#### 1. Create the bucket

In the S3 console (or CLI), create a bucket — for example
`download-joulescope-com`. Block public access; the uploader only needs
programmatic credentials. Choose a region and use it for the `region` config.

#### 2. Create an IAM policy

The uploader needs `s3:PutObject` to upload (`s3:GetObject` is convenient for
verification). List permission may be scoped to just the prefix the station
writes to. The uploader does **not** require `s3:HeadBucket` or unconditional
`s3:ListBucket`, so a prefix-scoped policy like the following is sufficient:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadWriteJoulescopeInstallObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::download-joulescope-com/joulescope_install/*"
    },
    {
      "Sid": "ListJoulescopeInstallPrefixOnly",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::download-joulescope-com",
      "Condition": {
        "StringLike": { "s3:prefix": "joulescope_install/*" }
      }
    }
  ]
}
```

Adjust the bucket name (`download-joulescope-com`) and prefix
(`joulescope_install/`) to match your `bucket` and `prefix` settings. The
object-level `Resource` must end in `/*`; the `ListBucket` statement targets the
bucket ARN (no `/*`).

#### 3. Create credentials

Create an IAM user (or role) and attach the policy. boto3 resolves credentials
from its
[default chain](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html):

- Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and
  optionally `AWS_DEFAULT_REGION`.
- A shared credentials file at `~/.aws/credentials`.
- An attached IAM role when running on EC2 / ECS.

### S3-compatible stores (MinIO)

Set `endpoint_url` to the service URL and provide that service's access key and
secret via the standard boto3 mechanisms:

```python
'uploader': {
    'clz': S3Uploader,
    'config': {
        'bucket': 'test-results',
        'endpoint_url': 'http://localhost:9000',
        'region': 'us-east-1',
    },
}
```

This is also the recommended way to test the integration locally before
pointing a station at production S3.


## Built-in: `UrlUploader`

Uploads each file to an HTTP(S) endpoint using the standard library (no extra
dependency). The upload is confirmed when the server responds with a 2xx status.

```python
from pytation.uploader import UrlUploader

'uploader': {
    'clz': UrlUploader,
    'config': {
        'url': 'https://host/upload/{name}',   # {name} = file basename
        'method': 'PUT',                        # optional, default 'PUT'
        'headers': {'Authorization': '...'},    # optional
        'timeout': 30.0,                        # optional, seconds
    },
}
```

`config` keys:

| Key | Required | Description |
|-----|----------|-------------|
| `url` | yes | Endpoint URL. May contain a `{name}` placeholder for the file basename. |
| `method` | no | HTTP method (default `PUT`). |
| `headers` | no | Extra request headers. `Content-Type: application/zip` is sent by default. |
| `timeout` | no | Per-request timeout in seconds (default 30). |

### Bearer authentication

If the `PYTATION_URL_UPLOADER_TOKEN` environment variable is set, the uploader
adds an `Authorization: Bearer <token>` header to every request. This keeps the
secret out of the station definition:

```bash
export PYTATION_URL_UPLOADER_TOKEN="my-secret-token"
```

An explicit `Authorization` entry in the `headers` config takes precedence over
the environment token.


## Writing a custom uploader

Subclass `pytation.Uploader` and implement the three methods. One-time setup
(sessions, clients, credentials) belongs in `setup()`; release it in
`teardown()`:

```python
import requests
from pytation import Uploader

class HttpPostUploader(Uploader):
    NAME = 'http_post'

    def setup(self, context, config):
        self._url = config['url']
        self._session = requests.Session()

    def upload(self, path):
        with open(path, 'rb') as f:
            r = self._session.post(self._url, files={'file': f})
        return r.ok          # True -> file deleted; False/raise -> retried

    def teardown(self):
        self._session.close()
```

Reference it from the station the same way as a built-in:

```python
'uploader': {'clz': HttpPostUploader, 'config': {'url': 'https://host/upload'}}
```
