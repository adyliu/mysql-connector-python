# MySQL Connector/Python - MySQL driver written in Python.
# Copyright (c) 2009, 2013, Oracle and/or its affiliates. All rights reserved.

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
"""Testing license and copyright in files"""

import os
import time
import re
import tempfile
import filecmp
import difflib
from datetime import datetime
from distutils.errors import DistutilsError

import support.tests
from support.distribution import commercial

GPL_NOTICE = """
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
"""

class SourceCheckTests(support.tests.SupportTests):
    """Test source files"""
    def _check_gpl_presence(self, file_):
        if not os.path.getsize(file_):
            return
        data = open(file_, 'r').read()
        for line in GPL_NOTICE.split('\n'):
            if line not in data:
                self.fail("Problem with GPL notice in '{0}',"
                    " line: {1}".format(file_, line))
                break

    def _check_gpl_absence(self, file_):
        if not os.path.getsize(file_):
            return
        data = open(file_, 'r').read()
        self.assertFalse(
            GPL_NOTICE.split('\n')[1] in data,
            "Found GPL notice where there should not be one in {0}".format(
                file_)
        )

    def test_for_gpl_notice(self):
        """Check for the GPL notice in Python source files"""
        source_dirs = ['python2', 'python3']
        for source_dir in source_dirs:
            for base, dirs, files in os.walk(source_dir):
                if 'django' in dirs:
                    dirs.remove('django')
                for filename in files:
                    if filename.endswith('.py'):
                        pyfile = os.path.join(base, filename)
                        self._check_gpl_presence(pyfile)
        
        # check other files
        cwd = os.getcwd()
        addn_files = [
            'setup.py',
        ]
        for pyfile in addn_files:
            self._check_gpl_presence(os.path.join(cwd, pyfile))

    def _check_copyright_presence(self, path, year=None):
        p = re.compile(r'(\d{4}),')
        copyright_notice = 'Copyright ' + '(c)'  # Prevent false positive
        for line in open(path, 'rb'):
            if not year:
                year = time.localtime(os.path.getmtime(path)).tm_year
            if copyright_notice in line:
                years = p.findall(line)
                self.assertTrue(
                    str(year) in years,
                    "Check year(s) in '{file}'".format(file=path))
                return

        self.fail("No copyright notice found in "
                  "file '{file}'".format(file=path))

    def _check_copyright_absence(self, path):
        copyright_notice = 'Copyright ' + '(c)'  # Prevent false positive
        for line in open(path, 'rb'):
            self.assertFalse(
                copyright_notice in line,
                "Found copyright where there should not be one in {0}".format(
                    path)
            )
    
    def test_copyright_notice(self):
        """Test if copyright is available and has correct years."""
        source_dirs = ['python2', 'python3']
        for source_dir in source_dirs:
            for base, dirs, files in os.walk(source_dir):
                if 'django' in dirs:
                    dirs.remove('django')
                for filename in files:
                    if filename.endswith('.py'):
                        pyfile = os.path.join(base, filename)
                        if os.path.getsize(pyfile) > 10:
                            self._check_copyright_presence(pyfile)
        
        # check other files
        cwd = os.getcwd()
        addn_files = [
            'setup.py',
        ]
        for pyfile in addn_files:
            self._check_copyright_presence(os.path.join(cwd, pyfile))

        # Files which need always the current year
        curr_year = datetime.now().year
        release_files = [
            'README', 'README_com.txt', 'LICENSE_com.txt',
        ]
        for afile in release_files:
            self._check_copyright_presence(os.path.join(cwd, afile), curr_year)

    def test_django_sources(self):
        db_backend_files = [
            'base.py', 'client.py', 'compiler.py', 'creation.py',
            'introspection.py', 'validation.py'
        ]
        django_dir = os.path.join('python2', 'mysql', 'connector', 'django')
        for base, dirs, files in os.walk(django_dir):
            for file_ in files:
                if file_.endswith('.py'):
                    pyfile = os.path.join(base, file_)
                    if os.path.getsize(pyfile) > 10:
                        self._check_copyright_absence(pyfile)
                        self._check_gpl_absence(pyfile)


class DebianTests(support.tests.SupportTests):
    """Test Debian packaging"""
    def test_changelog_version(self):
        ver = self.get_connector_version(no_suffix=True)
        debian_folders = ['commercial', 'gpl']
        for debian_folder in debian_folders:
            changelog = os.path.join('support', 'Debian', debian_folder,
                                     'changelog')
            content = open(changelog, 'r').read()
            self.assertTrue(ver in content,
                            "Version %s not found in %s" % (ver, changelog))

        
class CommercialTests(support.tests.SupportTests):
    """Test functionality regarding commercial releases"""
    def test_remove_gpl(self):
        pyfile = 'python2/mysql/connector/connection.py'

        # Succesfully remove GPL
        tmpfile = tempfile.NamedTemporaryFile(mode='w+')
        tmpfile.write(open(pyfile, 'r').read())
        commercial.remove_gpl(tmpfile.name)
        tmpfile.seek(0)
        data = tmpfile.read()
        self.assertTrue('# Following empty comments are intentional.' in data)
        self.assertTrue('# End empty comments.' in data)
        self.assertFalse('GPLv2' in data)
        self.assertFalse('Free Software' in data)
        tmpfile.close()
        
        # Fail removing GPL
        tmpfile = tempfile.NamedTemporaryFile(mode='w+')
        tmpfile.write("# No content.")
        self.assertRaises(DistutilsError, commercial.remove_gpl, tmpfile.name)
        tmpfile.close()
        
        # Test dry run
        tmpfile = tempfile.NamedTemporaryFile(mode='w+', delete=False)
        exp = open(pyfile, 'r').read()
        tmpfile.write(exp)
        commercial.remove_gpl(tmpfile.name, dry_run=1)
        self.assertTrue(exp, open(tmpfile.name, 'r').read())

