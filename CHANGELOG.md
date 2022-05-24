
# CHANGELOG

This file contains the list of changes made to pytation.


## 0.2.0

2022 May 24  [in progress]

* Combined "config" into "context" as context.config.
* Moved config['fs'] to context.fs.
* Added AnalysisContext (not just python dict) and improved analysis runner.
* Added pretty_json.
* Improved error handling on device open and GUI exit.


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
