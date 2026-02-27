# Copyright 2021-2022 Jetperch LLC
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

"""The API for packages using this manufacturing test framework."""

from typing import Protocol, runtime_checkable
from collections.abc import Mapping
from pytation.analysis import AnalysisContext


@runtime_checkable
class TestContext(Protocol):
    """The interface available to test functions and device setup.

    This Protocol defines the subset of :class:`pytation.context.Context`
    that tests and devices should use.  The full Context object is passed
    at runtime, but type-hinting with TestContext gives IDEs a focused
    autocomplete list and lets type checkers warn against calling
    orchestration internals.
    """

    env: dict[str, object]
    """The station environment.  Tests may read and modify."""

    config: dict[str, object]
    """The test configuration, populated before each test."""

    fs: object
    """The filesystem instance for use by the test (None between tests)."""

    devices: Mapping[str, object]
    """Read-only mapping of device name to device object."""

    @property
    def state(self) -> str:
        """The current state name."""
        ...

    @state.setter
    def state(self, s: str) -> None: ...

    @property
    def result(self) -> int:
        """The aggregate test result: 0 on success, error code on failure."""
        ...

    def expand_str(self, s: str) -> str:
        """Expand a string substituting environment variables."""
        ...

    def path(self, key: str) -> str:
        """Get a path from the station specification."""
        ...

    def section(self, name: str):
        """Create a new test section as a context manager."""
        ...

    def section_enter(self, name: str) -> None:
        """Enter a test section.  Call section_exit() when done."""
        ...

    def section_exit(self, name: str) -> None:
        """Exit a test section."""
        ...

    def progress(self, progress) -> None:
        """Signal a progress step (float 0.0-1.0 or string event name)."""
        ...

    def wait_for_user(self) -> None:
        """Wait for the user to perform an action."""
        ...

    def prompt(self, prompt_str: str) -> str:
        """Prompt the user for input and return their response."""
        ...


def declare_test(devices: list[str] = None):
    """Manufacturing test decorator to annotate required devices.

    :param devices: The list of expected devices, using the same
        device names used in the station definition.
    :return: The decorated test function(context).
    """
    def decorator_repeat(func):
        if devices:
            func.DEVICES = devices
        return func
    return decorator_repeat


def test_prototype(context: TestContext):
    """The prototype for a test function.

    :param context: The pytation test station context.
        See :class:`TestContext` for the available attributes and methods.

    :return: One of the following:
        * None: test passed
        * result: integer return code with 0=success, anything else=fail
        * result, details: The integer return code along with a dict
          of support details that will be logged.  The details are
          also added to the context.  details must be JSON serializable.
    :raise Exception: Test fails.

    A module with a "run" function that conforms to this prototype
    may also be used as a test.  The module may also provide an
    "analysis" function conforming to the :func:`analysis_prototype`.
    """
    return 0, {}


def analysis_prototype(context: AnalysisContext):
    """The prototype for an analysis function.

    :param context: The pytation test station analysis context.
    :return: 0 or error code.
    :raise Exception: On analysis failure.

    A module with a "run" function may also contain an "analysis" function
    that conforms to this prototype.
    """
    return 0


class Device:
    """A single connected device, instrument, or sensor."""

    NAME = ''
    """The user-meaningful, descriptive test name"""

    def setup(self, context: TestContext):
        """Open and initialize the device.

        :param context: The test station context.
        :raise Exception: on any error.
        """
        raise NotImplementedError("Device.setup")

    def restore(self):
        """Restore default settings for the device.

        This function is called after each test to ensure that the
        next test starts from a known condition.
        """
        raise NotImplementedError("Device.setup")

    def teardown(self):
        """Finalize and close the device."""
        raise NotImplementedError("Device.teardown")
