
# Python Test Station

Welcome to the pytation project!  This test framework package allows you to 
easily create tests for your custom hardware projects.  Although building
manufacturing test stations is the primary goal of this project, you can
also build repeatable development and validation test stations.
The framework allows you to run tests using a variety of runners including the
graphical PySide6 runner and command line runner.


## Quick Start

You will need Python 3.9 or newer.  You can install this package using pip:

    pip3 install -U pytation

Alternatively, you can clone the repo:

    git clone https://github.com/jetperch/pytation.git
    cd pytation
    pip3 install -U -r requirements.txt
    python3 setup.py qt

You can then run the example:

    python3 -m pytation gui pytation_examples.simple.STATION

On Windows, you may need to use `python` rather than `python3`.



## Terminology

This project uses several terms that can vary between different testing
frameworks.  This section defines the terms used throughout this project.

- **Test**: A single step that produces a pass/fail result along with optional
  detailed data.
- **Suite**: A sequence of **Tests** performed in order.  The **suite** also 
  produces a pass/fail result.  If any **test** fails, 
  then the **suite** fails.
- **Device**: An abstract definition for usually hardware instruments, sensors,
  and the device under test that are used by the **tests** to produce stimulus
  and measure results.  
- **Station**: The combination of **Devices** and a **Suite** of **Tests**.
  For manufacturing test stations, the **station** often runs the **suite**
  using the manufacturing GUI, once for each device under test. 

## License

All mfgr_test code is released under the permissive Apache 2.0 license.
See the [License File](LICENSE.txt) for details.
