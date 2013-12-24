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
"""Testing version information"""


import os
import re

from support import tests
import version


class VersionTest(tests.SupportTests):
    """Testing the version of Connector/Python"""
    def test_version(self):
        """Test validity of version"""
        ver = version.VERSION
        self.assertTrue(all(
            [isinstance(ver[0], int),
            isinstance(ver[1], int),
            isinstance(ver[2], int),
            (isinstance(ver[3], str) or (ver[3] == None)),
            isinstance(ver[4], int)]))

    def test_current_version(self):
        """Test current version"""
        self.assertEqual(tests.CONNECTOR_VERSION,
                         version.VERSION)

    def test_changelog(self):
        """Check version entry in changelog"""
        ver = '.'.join([ str(val) for val in tests.CONNECTOR_VERSION[0:3]])
        if tests.CONNECTOR_VERSION[3]:
            ver += ''.join(
                [ str(val) for val in tests.CONNECTOR_VERSION[3:]])
        found = False
        line = None
        with open('ChangeLog', 'r') as log:
            for line in log.readlines():
                if line.startswith(ver):
                    found = True
                    break

        if not found:
            self.fail("Version '{version}' not found in ChangeLog".format(
                version=ver))

        date = line.strip().split(' ', 1)[1]
        re_match = re.match(r'\((\d{4}-\d{2}-\d{2})\)', date)
        if not re_match:
            self.fail("Date for {version} is not set "
                      "correctly in ChangeLog".format(version=ver))

    def test_files_mentioning_version(self):
        """Check for version number important files

        Test whether the current version is being mentioned in some
        important files like README or the license files.
        """
        files = [
            'LICENSE_com.txt',
            'README',
            'README_com.txt',
            os.path.join('support', 'MSWindows', 'upgrade_codes.json'),
            os.path.join('support', 'OSX', 'Welcome.rtf'),
        ]
        ver = '.'.join([ str(val) for val in tests.CONNECTOR_VERSION[0:2]])

        for afile in files:
            with open(afile, 'r') as fp:
                content = fp.read()
            if ver not in content:
                self.fail("Version {ver} not mentioned in file {afile}".format(
                    ver=ver, afile=afile))

