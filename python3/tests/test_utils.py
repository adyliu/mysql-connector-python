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

"""Unittests for mysql.connector.utils
"""

import sys
import struct

import tests
from mysql.connector import utils

class UtilsTests(tests.MySQLConnectorTests):
    """Testing the helper functions in the utils module.
    
    These tests should not make a connection to the database.
    """
    def test_intread(self):
        """Use intread to read from valid strings."""
        try:
            for r in range(4):
                utils.intread(b'a'*(r+1))
        except ValueError as e:
            self.fail("intread failed calling 'int%dread: %s" % \
                (int(r)+1, e))
    
    def test_int1store(self):
        """Use int1store to pack an integer (2^8) as a string."""
        data = 2**(8-1)
        exp = struct.pack('<B',data)
        
        try:
            result = utils.int1store(data)
        except ValueError as e:
            self.fail("int1store failed: %s" % e)
        else:
            if not isinstance(result, bytes):
                self.fail("Wrong result. Expected %s, we got %s" %\
                    (type(exp), type(result)))
            elif exp != result:
                self.fail("Wrong result. Expected %s, we got %s" %\
                    (data, result))
                
    def test_int2store(self):
        """Use int2store to pack an integer (2^16) as a string."""
        data = 2**(16-1)
        exp = struct.pack('<H',data)
        
        try:
            result = utils.int2store(data)
        except ValueError as e:
            self.fail("int2store failed: %s" % e)
        else:
            if not isinstance(result, bytes):
                self.fail("Wrong result. Expected %s, we got %s" %\
                    (type(exp), type(result)))
            elif exp != result:
                self.fail("Wrong result. Expected %s, we got %s" %\
                    (data, result))

    def test_int3store(self):
        """Use int3store to pack an integer (2^24) as a string."""
        data = 2**(24-1)
        exp = struct.pack('<I',data)[0:3]
        
        try:
            result = utils.int3store(data)
        except ValueError as e:
            self.fail("int3store failed: %s" % e)
        else:
            if not isinstance(result, bytes):
                self.fail("Wrong result. Expected %s, we got %s" %\
                    (type(exp), type(result)))
            elif exp != result:
                self.fail("Wrong result. Expected %s, we got %s" %\
                    (data, result))

    def test_int4store(self):
        """Use int4store to pack an integer (2^32) as a string."""
        data = 2**(32-1)
        exp = struct.pack('<I',data)
        
        try:
            result = utils.int4store(data)
        except ValueError as e:
            self.fail("int4store failed: %s" % e)
        else:
            if not isinstance(result, bytes):
                self.fail("Wrong result. Expected %s, we got %s" %\
                    (type(exp), type(result)))
            elif exp != result:
                self.fail("Wrong result. Expected %s, we got %s" %\
                    (data, result))
                    
    def test_int8store(self):
        """Use int8store to pack an integer (2^64) as a string."""
        data = 2**(64-1)
        exp = struct.pack('<Q',data)

        try:
            result = utils.int8store(data)
        except ValueError as e:
            self.fail("int8store failed: %s" % e)
        else:
            if not isinstance(result, bytes):
                self.fail("Wrong result. Expected %s, we got %s" %\
                    (type(exp), type(result)))
            elif exp != result:
                self.fail("Wrong result. Expected %s, we got %s" %\
                    (data, result))
                    
    def test_intstore(self):
        """Use intstore to pack valid integers (2^64 max) as a string."""
        try:
            for i,r in enumerate((8, 16, 24, 32, 64)):
                val = 2**(r-1)
                utils.intstore(val)
        except ValueError as e:
            self.fail("intstore failed with 'int%dstore: %s" %\
                (i,e))
    
    def test_read_bytes(self):
        """Read a number of bytes from a bufffer"""
        buf = b"ABCDEFghijklm"
        readsize = 6
        exp = b"ghijklm"
        expsize = len(exp)
        
        try:
            (result, s) = utils.read_bytes(buf, readsize)
        except:
            self.fail("Failed reading bytes using read_bytes.")
        else:
            if result != exp or len(result) != expsize:
                self.fail("Wrong result. Expected: '%s' / %d, got '%s'/%d" %\
                    (exp, expsize, result, len(result)))
    
    def test_read_lc_string_1(self):
        """Read a length code string from a buffer ( <= 250 bytes)"""
        exp = b"a" * 2**(8-1)
        expsize = len(exp)
        lcs = utils.int1store(expsize) + exp
        
        (rest, result) = utils.read_lc_string(lcs)
        if result != exp or len(result) != expsize:
            self.fail("Wrong result. Expected '%d', got '%d'" %\
                expsize, len(result))

    def test_read_lc_string_2(self):
        """Read a length code string from a buffer ( <= 2^16 bytes)"""
        exp = b"a" * 2**(16-1)
        expsize = len(exp)
        lcs = b'\xfc' + utils.int2store(expsize) + exp

        (rest, result) = utils.read_lc_string(lcs)
        if result != exp or len(result) != expsize:
            self.fail("Wrong result. Expected '%d', got '%d'" %\
                expsize, len(result))

    def test_read_lc_string_3(self):
        """Read a length code string from a buffer ( <= 2^24 bytes)"""
        exp = b"a" * 2**(24-1)
        expsize = len(exp)
        lcs = b'\xfd' + utils.int3store(expsize) + exp

        (rest, result) = utils.read_lc_string(lcs)
        if result != exp or len(result) != expsize:
            self.fail("Wrong result. Expected size'%d', got '%d'" %\
                expsize, len(result))

    def test_read_lc_string_8(self):
        """Read a length code string from a buffer ( <= 2^64 bytes)"""
        exp = b"a" * 2**24
        expsize = len(exp)
        lcs = b'\xfe' + utils.int8store(expsize) + exp

        (rest, result) = utils.read_lc_string(lcs)
        if result != exp or len(result) != expsize:
            self.fail("Wrong result. Expected size '%d', got '%d'" %\
                expsize, len(result))
    
    def test_read_lc_string_5(self):
        """Read a length code string from a buffer which is 'NULL'"""
        exp = b'abc'
        lcs = b'\xfb' + b'abc'
        
        (rest, result) = utils.read_lc_string(lcs)
        if result != None or rest != b'abc':
            self.fail("Wrong result. Expected None.")
    
    def test_read_string_1(self):
        """Read a string from a buffer up until a certain character."""
        buf = b'abcdef\x00ghijklm'
        exp = b'abcdef'
        exprest = b'ghijklm'
        end = b'\x00'
        
        (rest, result) = utils.read_string(buf, end=end)
        if result != exp:
            self.fail("Wrong result. Expected '%s', got '%s'" %\
                exp, result)
        elif rest != exprest:
            self.fail("Wrong result. Expected '%s', got '%s'" %\
                exp, result)
    
    def test_read_string_2(self):
        """Read a string from a buffer up until a certain size."""
        buf = b'abcdefghijklm'
        exp = b'abcdef'
        exprest = b'ghijklm'
        size = 6
        
        (rest, result) = utils.read_string(buf, size=size)
        if result != exp:
            self.fail("Wrong result. Expected '%s', got '%s'" %\
                exp, result)
        elif rest != exprest:
            self.fail("Wrong result. Expected '%s', got '%s'" %\
                exp, result)

    def test_read_int(self):
        """Read an integer from a buffer."""
        buf = b'34581adbkdasdf'

        self.assertEqual(51, utils.read_int(buf,1)[1])
        self.assertEqual(13363, utils.read_int(buf,2)[1])
        self.assertEqual(3486771, utils.read_int(buf,3)[1])
        self.assertEqual(943010867, utils.read_int(buf,4)[1])
        self.assertEqual(7089898577412305971, utils.read_int(buf,8)[1])

    def test_read_lc_int(self):
        """Read a length encoded integer from a buffer."""
        buf = b'\xfb'

        exp = 2**(8-1)
        lcs = utils.intstore(exp)
        self.assertEqual(exp,utils.read_lc_int(lcs)[1],
            "Failed getting length coded int(250)")

        exp = 2**(8-1)
        lcs = utils.intstore(251) + utils.intstore(exp)
        self.assertEqual(None,utils.read_lc_int(lcs)[1],
            "Failed getting length coded int(250)")

        exp = 2**(16-1)
        lcs = utils.intstore(252) + utils.intstore(exp)
        self.assertEqual(exp,utils.read_lc_int(lcs)[1],
            "Failed getting length coded int(2^16-1)")

        exp = 2**(24-1)
        lcs = utils.intstore(253) + utils.intstore(exp)
        self.assertEqual(exp,utils.read_lc_int(lcs)[1],
            "Failed getting length coded int(2^24-1)")

        exp = 12321848580485677055
        lcs = b'\xfe\xff\xff\xff\xff\xff\xff\xff\xaa\xdd\xdd'
        exprest = b'\xdd\xdd'
        self.assertEqual((exprest,exp),utils.read_lc_int(lcs),
            "Failed getting length coded long long")
