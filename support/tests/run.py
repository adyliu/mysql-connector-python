# MySQL Connector/Python - MySQL driver written in Python.
# Copyright (c) 2013, Oracle and/or its affiliates. All rights reserved.

# MySQL Connector/Python is licensed under the terms of the GPLv2
# <http://www.gnu.org/licenses/old-licenses/gpl-2.0.html>, like most
# MySQL Connectors. There are special exceptions to the terms and
# conditions of the GPLv2 as it is applied to this software, see the
# FLOSS License Exception
# <http://www.mysql.com/about/legal/licensing/foss-exception.html>.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
"""Running tests checking sources and distribution

This script should be executed from the root of the MySQL Connector/Python
source code.
 shell> python support/tests/run.py
"""


import sys

# We only support Python v2.7 or v3.3
_REQUIRED_PYTHON = [(2, 7), (3, 3)]
if sys.version_info[0:2] not in _REQUIRED_PYTHON:
    sys.stderr.write("Python v2.7 or 3.3 is required.")
    sys.exit(1)

import os
import re
import argparse

# This script should run in the root source of MySQL Connector/Python
_CHECK_FILES = [
    os.path.exists('python2'),
    os.path.exists('python3'),
    os.path.exists('support/ssl'),
    os.path.exists('support/MSWindows'),
    os.path.isfile('version.py'),
    os.path.isfile('metasetupinfo.py')]
if not all(_CHECK_FILES):
    sys.stderr.write("This scripts needs to be executed from the root of the "
                    "MySQL Connector/Python source.")

# Add root of source to PYTHONPATH
sys.path.insert(0, os.getcwd())

from support import tests


def parse_version(verstr):
    """Parses the Connector/Python version string

    Returns a tuple, or None.
    """
    # Based on regular expression found in PEP-386
    expr = (r'^(?P<version>\d+\.\d+)(?P<extraversion>(?:\.\d+){1})'
            r'(?:(?P<prerel>[ab])(?P<prerelversion>\d+(?:\.\d+)*))?$')
    re_match = re.match(expr, verstr)

    if not re_match:
        return None

    info = [ int(val) for val in re_match.group('version').split('.') ]
    info.append(int(re_match.group('extraversion').replace('.', '')))
    info.extend([None, 0])
    try:
        info[3] = re_match.group('prerel')
        info[4] = int(re_match.group('prerelversion'))
    except TypeError:
        # It's OK when this information is missing, check happend earlier
        pass
    return tuple(info)

def main():
    """Run tests"""
    argparser = argparse.ArgumentParser(
        description="Run MySQL Connector/Python tests "
                    "checking sources and distribution.")
    argparser.add_argument(
        '--connector-version', type=str,
        dest='connector_version', action='store', required=True,
        help="Current version of MySQL Connector/Python")

    args = argparser.parse_args()
    tests.CONNECTOR_VERSION = parse_version(args.connector_version)
    if not tests.CONNECTOR_VERSION:
        sys.stderr.write("'{ver}' is not a valid version "
                         "for MySQL Connector/Python.\n".format(
                            ver=args.connector_version))
        sys.exit(1)

    tests.run()

if __name__ == '__main__':
    main()

