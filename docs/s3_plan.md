# S3 Upload Feature Plan

## Goal

Automatically upload suite result ZIP files to S3. Tolerate network outages
gracefully — files accumulate locally and upload when connectivity returns,
oldest first. Delete local files after confirmed upload.


## Design Decisions

- **Watchdog-based file watcher**, not a queue coupled to the context.
  The uploader is a fully independent component that monitors the output
  directory for new ZIP files. It has no import dependency on
  `pytation.context` and no direct coupling to the test lifecycle.
- **Atomic ZIP creation**: ZIPs are written to a temp directory, then
  moved to the output directory. The move triggers the watchdog event.
  This eliminates partial-write uploads and also closes the "non-atomic
  ZIP write" risk from the design review.
- **Oldest-first ordering** ensures chronological completeness on the
  server side. If the line produces faster than upload bandwidth allows,
  the backlog drains in order.
- **S3 is the source of truth**. Local files are deleted only after S3
  confirms receipt (ETag from `put_object` response). Local disk is a
  transient buffer, not long-term storage.
- **Dependencies**: `boto3`, `watchdog`. Both are well-maintained,
  widely deployed packages.


## Architecture

```
context.py                              s3_upload.py
──────────                              ────────────
_suite_file_open()                      S3Uploader
  writes ZIP to temp dir                  │
_suite_stop()                             ├─ watchdog Observer
  closes ZIP                              │    watches output_dir for
  moves ZIP: temp → output_dir ─────────► │    FileCreatedEvent (*.zip)
                                          │         │
                                          │         ▼
                                          ├─ _upload_pending()
                                          │    sort by mtime (oldest first)
                                          │    for each .zip:
                                          │      put_object to S3
                                          │      verify ETag
                                          │      delete local file
                                          │
                                          ├─ start()
                                          │    scan for existing ZIPs
                                          │    start Observer
                                          │
                                          └─ stop()
                                               stop Observer
                                               final upload pass
```

The uploader watches a directory. The context writes files to that
directory. They share no objects, no queues, no callbacks.


## Components

### 1. `pytation/s3_upload.py` — New module

#### `S3Uploader` class

```python
class S3Uploader:
    def __init__(self, watch_dir, bucket, prefix='', region=None,
                 retry_interval=30.0, endpoint_url=None):
        """
        :param watch_dir: Directory to watch for new .zip files.
        :param bucket: S3 bucket name.
        :param prefix: Key prefix (e.g. 'stations/station_name/').
        :param region: AWS region. None uses boto3 default chain.
        :param retry_interval: Seconds to wait before retrying after
            a network failure.
        :param endpoint_url: Optional custom endpoint (for MinIO, etc.).
        """
```

**Public methods**:

- `start()` — Start the watchdog Observer. Run an initial scan of
  `watch_dir` for existing ZIPs (from previous runs, crashes, or
  network outages) and upload them oldest-first.
- `stop(timeout=30.0)` — Stop the Observer. Run one final upload
  pass to catch any files that arrived after the last event.
  Blocks up to `timeout` seconds.
- `pending_count` — Property returning the number of `.zip` files
  remaining in `watch_dir` (for logging/monitoring).

**Internal methods**:

- `_on_created(event)` — Watchdog `FileCreatedEvent` handler.
  Filters for `*.zip` files, then calls `_upload_pending()`.
- `_upload_pending()` — Glob `watch_dir` for `*.zip`, sort by mtime
  (oldest first), attempt to upload each. Stops on the first network
  failure and schedules a retry after `retry_interval`.
- `_upload_one(path)` — Upload a single file. Uses `put_object` with
  file content. Verifies the response contains an ETag. S3 key is
  `{prefix}{filename}`. Returns True on success.
- `_is_connected()` — `head_bucket` call with a short socket timeout.
  Called before starting an upload batch to avoid hammering S3 during
  an outage.
- `_schedule_retry()` — Uses `threading.Timer` to call
  `_upload_pending()` after `retry_interval` seconds. Only one retry
  timer is active at a time.

#### Watchdog handler

```python
class _ZipCreatedHandler(FileSystemEventHandler):
    def __init__(self, uploader):
        self._uploader = uploader

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.zip'):
            self._uploader._upload_pending()

    def on_moved(self, event):
        if not event.is_directory and event.dest_path.endswith('.zip'):
            self._uploader._upload_pending()
```

Handles both `on_created` and `on_moved` because the atomic write
pattern (write to temp, move to output) generates a move event on
some platforms and a create event on others.

#### Error handling

- **Network errors** (ConnectionError, EndpointConnectionError,
  ClientError): log warning, schedule retry. Files stay on disk.
- **File not found** (deleted externally): log warning, skip.
- **Permission / credential errors**: log error, schedule retry.
  The operator must fix credentials; the uploader keeps retrying.
- **Corrupted ZIP**: not our concern — upload it anyway. Server-side
  validation can flag it.
- **Concurrent access**: `_upload_pending` acquires a `threading.Lock`
  so watchdog events and retry timers don't overlap.

#### Thread lifecycle

- The watchdog `Observer` runs its own daemon thread.
- `threading.Timer` for retries is also a daemon thread.
- Both exit automatically if the process crashes.
- `stop()` joins the Observer and cancels any pending retry timer.


### 2. Atomic ZIP creation in `context.py`

#### Current behavior

```python
# _suite_file_open writes directly to the output path
self._fs = WriteZipFS(file=output_path, ...)

# _suite_stop closes in place
self._fs.close()
```

#### New behavior

```python
# _suite_file_open writes to a temp path alongside the output dir
self._fs_temp_path = output_path + '.tmp'
self._fs = WriteZipFS(file=self._fs_temp_path, ...)

# _suite_stop closes, then atomically moves to the final path
self._fs.close()
os.replace(self._fs_temp_path, self._fs_path)  # atomic on same filesystem
```

`os.replace` is atomic on POSIX and atomic on Windows when source and
destination are on the same volume (which they are — same directory).
This is the only change to `context.py`. No import of `s3_upload`,
no coupling.


### 3. Station definition

```python
station = {
    ...
    's3': {
        'bucket': 'my-production-data',
        'prefix': 'stations/{station}/',
        'region': 'us-east-1',            # optional
        'retry_interval': 30.0,           # optional, seconds
        'endpoint_url': None,             # optional, for MinIO etc.
    },
}
```

The `s3` key is optional. If absent, no uploader is created and
behavior is unchanged (ZIPs accumulate locally as before).


### 4. Integration point — `__main__.py` or entry points

The uploader is started in the CLI/GUI entry points, not in
`context.py`:

```python
# entry_points/cli.py
def on_cmd(args):
    station = loader.load(args)
    s3_cfg = station.get('s3')
    uploader = None
    if s3_cfg:
        watch_dir = os.path.dirname(
            station['paths']['output'].format(
                **station['paths'], **station['env']))
        uploader = S3Uploader(watch_dir=watch_dir, **s3_cfg)
        uploader.start()
    try:
        obj = cli_runner.CliStation(station)
        obj.run(count=iterations)
    finally:
        if uploader:
            uploader.stop()
```

This keeps `context.py` completely unaware of S3.


## File changes

| File | Change |
|------|--------|
| `pytation/s3_upload.py` | **New** — `S3Uploader` class + watchdog handler |
| `pytation/context.py` | Write ZIP to `.tmp`, `os.replace` to final path |
| `pytation/entry_points/cli.py` | Create/start/stop uploader around station run |
| `pytation/entry_points/gui.py` | Same pattern as cli.py |
| `pytation/loader.py` | Pass through `s3` config in `validate()` |
| `pyproject.toml` | Add `boto3` and `watchdog` to optional dependencies |
| `pytation/test/test_s3_upload.py` | **New** — Unit tests with mocked boto3 |


## Testing strategy

- **Unit tests** (`test_s3_upload.py`): Mock `boto3.client`. Test:
  - File appears in watch dir, uploaded and deleted
  - Network failure causes retry after interval, file not deleted
  - Startup scan finds and uploads existing files in oldest-first order
  - `stop()` runs final upload pass
  - Move event (atomic write pattern) triggers upload
  - Concurrent events don't cause duplicate uploads (lock)
- **Context atomic write test**: Verify `os.replace` is called and
  `.tmp` file does not remain after `_suite_stop`.
- **Integration test** (manual): Use MinIO in a Docker container as
  the S3 endpoint. Run a station, verify ZIPs appear in MinIO,
  verify local files are deleted. Kill the station mid-suite, restart,
  verify leftover ZIPs are uploaded.


## Rollout

1. Implement atomic ZIP write in `context.py` (standalone improvement,
   no S3 dependency). Ship and verify.
2. Implement `S3Uploader` with unit tests.
3. Integrate in entry points.
4. Test with MinIO locally.
5. Deploy to a single station with production S3. Monitor for a few days.
6. Roll out to remaining stations.
