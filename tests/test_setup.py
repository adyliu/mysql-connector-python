# MySQL Connector/Python - MySQL driver written in Python.
# Copyright (c) 2013, Oracle and/or its affiliates. All rights reserved.

# MySQL Connector/Python is licensed under the terms of the GPLv2
# <http://www.gnu.org/licenses/old-licenses/gpl-2.0.html>, like most
# MySQL Connectors. There are special exceptions to the terms and
# conditions of the GPLv2 as it is applied to this software, see the
# FOSS License Exception
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

"""Unit tests for the setup script of Connector/Python
"""

import sys
import os
import tests
import imp

import version


class VersionTests(tests.MySQLConnectorTests):

    """Testing the version of Connector/Python"""

    def test_version(self):
        """Test validity of version"""
        vs = version.VERSION
        self.assertTrue(all(
            [isinstance(vs[0], int),
             isinstance(vs[1], int),
             isinstance(vs[2], int),
             isinstance(vs[3], str),
             isinstance(vs[4], int)]))

    def test___version__(self):
        """Test module __version__ and __version_info__"""
        import mysql.connector
        self.assertTrue(hasattr(mysql.connector, '__version__'))
        self.assertTrue(hasattr(mysql.connector, '__version_info__'))
        self.assertTrue(isinstance(mysql.connector.__version__, str))
        self.assertTrue(isinstance(mysql.connector.__version_info__, tuple))
        self.assertEqual(version.VERSION_TEXT, mysql.connector.__version__)
        self.assertEqual(version.VERSION, mysql.connector.__version_info__)


class MetaSetupInfoTests(tests.MySQLConnectorTests):

    """Testing meta setup information

    We are importing the metasetupinfo module insite the unit tests
    to be able to actually do tests.
    """

    def test_name(self):
        """Test the name of Connector/Python"""
        import metasetupinfo
        self.assertEqual('mysql-connector-python', metasetupinfo.name)

    def test_dev_statuses(self):
        """Test the development statuses"""
        import metasetupinfo
        exp = {
            'a': '3 - Alpha',
            'b': '4 - Beta',
            '': '5 - Production/Stable'
        }
        self.assertEqual(exp, metasetupinfo.DEVELOPMENT_STATUSES)

    def test_sys_path(self):
        """Test if sys.path has been updated"""
        # Following import is not used, but it does set the sys.path
        import metasetupinfo
        exp = 'python' + str(sys.version_info[0]) + '/'
        self.assertEqual(exp, sys.path[0])

    def test_package_dir(self):
        """Test the package directory"""
        import metasetupinfo
        exp = {
            '': 'python' + str(sys.version_info[0]),
            'mysql.connector.django': os.path.join('python23', 'django'),
            'mysql.connector.fabric': os.path.join('python23', 'fabric'),
        }
        self.assertEqual(exp, metasetupinfo.package_dir)

    def test_unsupported_python(self):
        """Test if old Python version are unsupported"""
        import metasetupinfo
        tmp = sys.version_info
        sys.version_info = (3, 0, 0, 'final', 0)
        try:
            imp.reload(metasetupinfo)
        except RuntimeError:
            pass
        else:
            self.fail("RuntimeError not raised with unsupported Python")
        sys.version_info = tmp

    def test_version(self):
        """Test the imported version information"""
        import metasetupinfo
        ver = metasetupinfo.VERSION
        exp = '{0}.{1}.{2}'.format(*ver[0:3])
        self.assertEqual(exp, metasetupinfo.version)

    def test_misc_meta(self):
        """Test miscellaneous data such as URLs"""
        import metasetupinfo
        self.assertEqual(
            'http://dev.mysql.com/doc/connector-python/en/index.html',
            metasetupinfo.url)
        self.assertEqual(
            'http://dev.mysql.com/downloads/connector/python/',
            metasetupinfo.download_url)

    def test_classifiers(self):
        """Test Trove classifiers"""
        import metasetupinfo
        for clsfr in metasetupinfo.classifiers:
            if 'Programming Language :: Python' in clsfr:
                ver = clsfr.replace('Programming Language :: Python :: ', '')
                if ver not in ('2.6', '2.7', '3', '3.1', '3.2', '3.3'):
                    self.fail('Unsupported version in classifiers')
            if 'Development Status ::' in clsfr:
                status = clsfr.replace('Development Status :: ', '')
                self.assertEqual(
                    metasetupinfo.DEVELOPMENT_STATUSES[version.VERSION[3]],
                    status)
