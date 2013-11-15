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

"""Unittests
"""

import os
import sys
import socket
import errno
import re
import datetime
import logging
import inspect
import platform
import unittest
try:
    from unittest.util import strclass
except ImportError:
    from unittest import _strclass as strclass

SSL_AVAILABLE = True
try:
    import ssl
except ImportError:
    SSL_AVAILABLE = False

# Note that IPv6 support for Python is checked here, but it can be disabled
# when the bind_address of MySQL was not set to '::1'.
IPV6_AVAILABLE = socket.has_ipv6

if os.name == 'nt':
    WINDOWS_VERSION = platform.win32_ver()[1]
    WINDOWS_VERSION_INFO = tuple(
        [int(v) for v in WINDOWS_VERSION.split('.')[0:2]])
else:
    WINDOWS_VERSION = None
    WINDOWS_VERSION_INFO = ()

MYSQL_CONFIG = {
    'host' : '127.0.0.1',
    'port' : 33770,
    'unix_socket' : None,
    'user' : 'root',
    'password' : '',
    'database' : 'myconnpy',
    'connection_timeout': 10,
}

# Following dictionary holds messages which were added by test cases
# but only logged at the end.
MESSAGES = {
    'WARNINGS': [],
    'INFO': [],
}

MYSQL_SERVER = None
MYSQL_VERSION = None
SSL_DIR = os.path.join("support", "ssl")

LOGGER_NAME = "myconnpy_tests"

__all__ = [
    'MySQLConnectorTests',
    'get_test_names','printmsg',
    'active_testcases',
    'LOGGER_NAME',
    'SSL_DIR',
    'MYSQL_VERSION',
]

active_testcases = [
    'tests.test_utils',
    'tests.test_protocol',
    'tests.test_constants',
    'tests.test_conversion',
    'tests.test_connection',
    'tests.test_network',
    'tests.test_cursor',
    'tests.test_pep249',
    'tests.test_bugs',
    'tests.test_examples',
    'tests.test_mysql_datatypes',
    'tests.test_errors',
    'tests.test_errorcode',
    'tests.test_locales',
    'tests.test_setup',
    'tests23.test_pooling',
]

class UTCTimeZone(datetime.tzinfo):
    def utcoffset(self,dt):
        return datetime.timedelta(0)
    def dst(self,dt):
        return datetime.timedelta(0)

class TestTimeZone(datetime.tzinfo):
    def __init__(self, hours=0):
        self._offset = datetime.timedelta(hours=hours)
    def utcoffset(self,dt):
        return self._offset
    def dst(self,dt):
        return datetime.timedelta(0)

class DummySocket(object):
    """Dummy socket class
    
    This class helps to test socket connection without actually making any
    network activity. It is a proxy class using socket.socket.
    """
    def __init__(self, *args):
        self._socket = socket.socket(*args)
        self._server_replies = b''
        self._client_sends = []
        self._raise_socket_error = 0
    
    def __getattr__(self, attr):
        return getattr(self._socket, attr)

    def raise_socket_error(self, err=errno.EPERM):
        self._raise_socket_error = err
    
    def recv(self, bufsize=4096, flags=0):
        if self._raise_socket_error:
            raise socket.error(self._raise_socket_error)
        res = self._server_replies[0:bufsize]
        self._server_replies = self._server_replies[bufsize:]
        return res
    
    def send(self, string, flags=0):
        if self._raise_socket_error:
            raise socket.error(self._raise_socket_error)
        self._client_sends.append(string)
        return len(string)
        
    def sendall(self, string, flags=0):
        self._client_sends.append(string)
        return None
    
    def add_packet(self, packet):
        self._server_replies += packet
        
    def add_packets(self, packets):
        for packet in packets:
            self._server_replies += packet
            
    def reset(self):
        self._raise_socket_error = 0
        self._server_replies = b''
        self._client_sends = []

class MySQLConnectorTests(unittest.TestCase):
    def __str__(self):
        classname = strclass(self.__class__)
        return "{classname}.{method}".format(
            method=self._testMethodName,
            classname=re.sub("tests\d*.test_", "", classname)
            )

    def getMySQLConfig(self):
        return MYSQL_CONFIG.copy()
    
    def getFakeHostname(self):
        return ''.join([ "%02x" % c for c in os.urandom(4)])

    def checkAttr(self, obj, attrname, default):
        cls_name = obj.__class__.__name__
        self.assertTrue(hasattr(obj,attrname),
            "%s object has no '%s' attribute" % (cls_name,attrname))
        self.assertEqual(default,getattr(obj,attrname),
            "%s object's '%s' should default to %s '%s'" % (
                cls_name, attrname, type(default).__name__, default)
            )
    
    def checkMethod(self, obj, method):
        cls_name = obj.__class__.__name__
        self.assertTrue(hasattr(obj,method),
            "%s object has no '%s' method" % (cls_name, method))
        self.assertTrue(inspect.ismethod(getattr(obj,method)),
            "%s object defines %s, but is not a method" % (
                cls_name, method))

    def checkArguments(self, function, supported_arguments):
        argspec = inspect.getargspec(function)
        function_arguments = dict(zip(argspec[0][1:],argspec[3]))
        for argument,default in function_arguments.items():
            try:
                self.assertEqual(supported_arguments[argument],
                                 default,
                                 msg="Argument '{}' has wrong default".format(
                                     argument))
            except KeyError:
                self.fail("Found unsupported or new argument '{}'".format(
                          argument))
        for argument,default in supported_arguments.items():
            if not argument in function_arguments:
                self.fail("Supported argument '{}' fails".format(
                          argument))

    def haveEngine(self, db, engine):
        """Check if the given storage engine is supported"""
        have = False
        engine = engine.lower()
        c = None
        try:
            c = db.cursor()
            # Should use INFORMATION_SCHEMA, but play nice with v4.1
            c.execute("SHOW ENGINES")
            rows = c.fetchall()
            for row in rows:
                if row[0].lower() == engine:
                    if row[1].lower() == 'yes':
                        have=True
                    break
        except:
            raise
        finally:
            try:
                c.close()
            except:
                pass
        return have

    def cmpResult(self, res1, res2):
        """Compare results (list of tuples) comming from MySQL
        
        For certain results, like SHOW VARIABLES or SHOW WARNINGS, the
        order is unpredictable. To check if what is expected in the
        tests, we need to compare each row.
        """
        try:
            if len(res1) != len(res2):
                return False
        
                for row in res1:
                    if row not in res2:
                        return False
        except:
            return False
            
        return True
        
def get_test_names():
    pattern = re.compile('tests\d*.test_')
    return [ pattern.sub('', s) for s in active_testcases ]

def printmsg(msg=None):
    if msg is not None:
        print(msg)



