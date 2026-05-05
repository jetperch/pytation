<!--
# SPDX-FileCopyrightText: Copyright 2021-2026 Jetperch LLC
# SPDX-License-Identifier: Apache-2.0
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
-->


# CHANGELOG

This file contains the list of changes made to pytation.


## 0.5.0

2026 May 5

* Added untimed sections
* Added timing analysis of log files


## 0.4.0

2026 Apr 22

* Removed dependency on the unmaintained `fs` (PyFilesystem2) package,
  which relied on the deprecated `pkg_resources` API.
* Added `pytation.zipfs` module with `ZipWriteFS` and `ZipReadFS`,
  backed by the Python standard library (`zipfile` + `tempfile`),
  replacing the previous use of `fs.zipfs.WriteZipFS` / `ReadZipFS`.
  The write path stages to a temporary directory so that `log.txt`
  and `progress.csv` can remain open for the duration of a suite,
  matching the previous behavior.
* Preserved the public `context.fs.open(name, mode)` API so existing
  test and analysis modules continue to work without modification.


## 0.3.1

2026 Mar 5

* Fixed GitHub actions.


## 0.3.0

2026 Mar 4

* Fixed issues raised by design review.


## 0.2.4

2022 Nov 30

* Fixed dependencies for pip installation.


## 0.2.3

2022 Nov 4

* Fixed pypiwin32 dependency -> pywin32.
* Added sphinx documentation.
* Added GitHub workflow to build documentation and publish to GitHub Pages.
* Restructured example.


## 0.2.2

2022 Oct 4

* Added "handlers".
* Added support for "qt_keypress" handler.
* Added PYTATION_RETURN_CODE_SKIP_REMAINING_TESTS feature.


## 0.2.1

2022 Sep 15

* Fixed tests.json not being cleared on successive tests.


## 0.2.0

2022 Jul 15

* Combined "config" into "context" as context.config.
* Moved config['fs'] to context.fs.
* Added AnalysisContext (not just python dict) and improved analysis runner.
* Added pretty_json.
* Improved error handling on device open and GUI exit.
* Changed from deprecated collections.Mapping to from collections.abc.Mapping.


## 0.1.2

2022 Feb 4

* Added API documentation for a test.
* Added support for modules with "run" function as tests.
* Added analyze entry point.
* Added missing "fs" dependency in setup.py.


## 0.1.1

2021 Jul 1

*   Improved CLI to only run one iteration by default.
*   Fixed main description and logging environment variable.
*   Fixed pytation console_script.


## 0.1.0

2021 June 28

*   Refactored and improved station validate.
*   Added test "--include" and "--exclude" command-line options.
*   Implemented command line interface (CLI) runner.


## 0.0.2

2021 June 25

*   Fixed installation dependencies.


## 0.0.1

2021 June 25

*   Initial public release.
