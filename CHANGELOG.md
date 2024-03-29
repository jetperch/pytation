
# CHANGELOG

This file contains the list of changes made to pytation.


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
