# -*- coding: utf-8 -*-
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

"""Unit tests for bugs specific to Python v3
"""

import os
import tests

from mysql.connector import connection, errors


class BugOra14843456(tests.MySQLConnectorTests):

    """BUG#14843456: UNICODE USERNAME AND/OR PASSWORD FAILS
    """

    def setUp(self):
        config = tests.get_mysql_config()
        self.cnx = connection.MySQLConnection(**config)
        self.cursor = self.cnx.cursor()

        if config['unix_socket'] and os.name != 'nt':
            self.host = 'localhost'
        else:
            self.host = config['host']

        grant = "CREATE USER '{user}'@'{host}' IDENTIFIED BY '{password}'"

        self._credentials = [
            ('Herne', 'Herne'),
            ('\u0141owicz', '\u0141owicz'),
        ]
        for user, password in self._credentials:
            self.cursor.execute(grant.format(
                user=user, host=self.host, password=password))

    def tearDown(self):
        for user, password in self._credentials:
            self.cursor.execute("DROP USER '{user}'@'{host}'".format(
                user=user, host=self.host))

    def test_unicode_credentials(self):
        config = tests.get_mysql_config()
        for user, password in self._credentials:
            config['user'] = user
            config['password'] = password
            config['database'] = None
            try:
                cnx = connection.MySQLConnection(**config)
            except (UnicodeDecodeError, errors.InterfaceError):
                self.fail('Failed using unicode username or password')
            else:
                cnx.close()


class Bug499410(tests.MySQLConnectorTests):

    def test_use_unicode(self):
        """lp:499410 Disabling unicode does not work"""
        config = tests.get_mysql_config()
        config['use_unicode'] = False
        cnx = connection.MySQLConnection(**config)

        self.assertEqual(False, cnx._use_unicode)
        cnx.close()

    def test_charset(self):
        config = tests.get_mysql_config()
        config['use_unicode'] = False
        charset = 'greek'
        config['charset'] = charset
        cnx = connection.MySQLConnection(**config)

        data = [b'\xe1\xed\xf4\xdf\xef']  # Bye in Greek
        exp_unicode = [('\u03b1\u03bd\u03c4\u03af\u03bf',), ]
        exp_nonunicode = [(data[0],)]

        cur = cnx.cursor()

        tbl = '{0}test'.format(charset)
        try:
            cur.execute('DROP TABLE IF EXISTS {0}'.format(tbl))
            cur.execute(
                'CREATE TABLE {0} (c1 VARCHAR(60)) charset={1}'.format(
                    tbl, charset))
        except:
            self.fail("Failed creating test table.")

        try:
            stmt = 'INSERT INTO {0} VALUES (%s)'.format(tbl)
            for line in data:
                cur.execute(stmt, (line.strip(),))
        except:
            self.fail("Failed populating test table.")

        cur.execute("SELECT * FROM {0}".format(tbl))
        res_nonunicode = cur.fetchall()
        cnx.set_unicode(True)
        cur.execute("SELECT * FROM {0}".format(tbl))
        res_unicode = cur.fetchall()

        try:
            cur.execute('DROP TABLE IF EXISTS {0}'.format(tbl))
        except:
            self.fail("Failed cleaning up test table.")

        cnx.close()

        self.assertEqual(exp_nonunicode, res_nonunicode)
        self.assertEqual(exp_unicode, res_unicode)


class BugOra17079344Extra(object):

    """Extras for test case test_bugs.BugOra17079344"""

    data_gbk = ['赵孟頫', '赵\孟\頫\\', '遜',]
    data_sjis = ['\u005c']
    data_big5 = ['\u5C62']
