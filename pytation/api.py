# Copyright 2021 Jetperch LLC
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


from . import Context


def declare_test(devices: list[str] = None):
    """Manufacturing test decorator to annotate required devices.

    :param devices: The list of expected devices, using the same
        device names used in the station definition.
    :return: The decorated test function.
    """
    def decorator_repeat(func):
        if devices:
            func.DEVICES = devices
        return func
    return decorator_repeat


class Device:
    """A single connected device, instrument, or sensor."""

    NAME = ''
    """The user-meaningful, descriptive test name"""

    def setup(self, context: Context, config: dict[str, object]):
        """Open and initialize the device.

        :param context: The test station context.
        :param config: Optional additional device configuration options.
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
