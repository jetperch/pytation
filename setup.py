#!/usr/bin/env python3
# Copyright 2018-2022 Jetperch LLC
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

"""
Python Test Station framework for hardware validation and production.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
import setuptools
import setuptools.dist
from setuptools.command.sdist import sdist
import distutils.cmd
from distutils.errors import DistutilsExecError
import os
import sys
from pytation import qt_util


MYPATH = os.path.dirname(os.path.abspath(__file__))
VERSION_PATH = os.path.join(MYPATH, 'pytation', 'version.py')


about = {}
with open(VERSION_PATH, 'r', encoding='utf-8') as f:
    exec(f.read(), about)


# Get the long description from the README file
with open(os.path.join(MYPATH, 'README.md'), 'r', encoding='utf-8') as f:
    long_description = f.read()


def _version_get():
    return about['__version__']


def _build_qt():
    paths = [
        os.path.join(MYPATH, 'pytation'),
        os.path.join(MYPATH, 'pytation_examples'),
    ]
    for path in paths:
        targets = qt_util.convert_rcc(path)
        targets = [os.path.relpath(t, path).replace('\\', '/') for t in targets]


class CustomBuildQt(distutils.cmd.Command):
    """Custom command to build Qt resource file and Qt user interface modules."""

    description = 'Build Qt resource file and Qt user interface modules.'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        _build_qt()


class CustomSdistCommand(sdist):
    def run(self):
        _build_qt()
        sdist.run(self)


class CustomBuildDocs(distutils.cmd.Command):
    """Custom command to build docs locally."""

    description = 'Build docs.'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # sphinx-build -b html docs build\docs_html
        # defer import so not all setups require sphinx
        from sphinx.application import Sphinx
        from sphinx.util.console import nocolor, color_terminal
        nocolor()
        source_dir = os.path.join(MYPATH, 'docs')
        target_dir = os.path.join(MYPATH, 'build', 'docs_html')
        doctree_dir = os.path.join(target_dir, '.doctree')
        app = Sphinx(source_dir, source_dir, target_dir, doctree_dir, 'html')
        app.build()
        if app.statuscode:
            raise DistutilsExecError(
                'caused by %s builder.' % app.builder.name)


setuptools.setup(
    name=about['__title__'],
    version=about['__version__'],
    description=about['__description__'],
    long_description=long_description,
    long_description_content_type='text/markdown',
    url=about['__url__'],
    author=about['__author__'],
    author_email=about['__author_email__'],
    license=about['__license__'],

    cmdclass={
        'docs': CustomBuildDocs,
        'qt': CustomBuildQt,
        'sdist': CustomSdistCommand,
    },

    # Classifiers help users find your project by categorizing it.
    #
    # For a list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[  # Optional
        'Development Status :: 5 - Production/Stable',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Manufacturing',

        # Pick your license as you wish
        'License :: OSI Approved :: Apache Software License',

        # Operating systems
        'Operating System :: Microsoft :: Windows :: Windows 10',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX :: Linux',

        # Supported Python versions
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: Implementation :: CPython',

        # Language
        'Natural Language :: English',
        
        # Topics
        'Topic :: Scientific/Engineering',
        'Topic :: Software Development :: Embedded Systems',
        'Topic :: Software Development :: Testing',
        'Topic :: System :: Hardware',
        'Topic :: Utilities',
    ],

    keywords='hardware validation manufacturing test station',

    packages=setuptools.find_packages(exclude=['native', 'docs', 'test', 'dist', 'build']),
    include_package_data=True,
    include_dirs=[],
    
    # See https://packaging.python.org/guides/distributing-packages-using-setuptools/#python-requires
    python_requires='~=3.9',

    # See https://packaging.python.org/en/latest/requirements.html
    # https://numpy.org/neps/nep-0029-deprecation_policy.html
    install_requires=[
        'fs',
        "pywin32; platform_system=='Windows'",
        'PySide6',
    ],

    entry_points={
        'console_scripts': [
            'pytation=pytation.__main__:run',
        ],
    },
    
    project_urls={
        'Bug Reports': 'https://github.com/jetperch/pytation/issues',
        'Source': 'https://github.com/jetperch/pytation',
    },
)
