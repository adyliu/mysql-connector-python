#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

"""Script for running unittests

unittests.py launches all or selected unittests.

Examples:
 Setting the MySQL account for running tests
 shell> python unittests.py -uroot -D dbtests
 
 Executing only the cursor tests
 shell> python unittests.py -t cursor

unittests.py has exit status 0 when tests were ran succesful, 1 otherwise.

"""
import sys
import os
import pkgutil
import time
import tempfile
import threading
import unittest
import logging
from optparse import OptionParser

try:
    from unittest import TextTestResult
except ImportError:
    # Compatibility with Python v2.6
    from unittest import _TextTestResult as TextTestResult

if ((sys.version_info >= (2, 6) and sys.version_info < (3, 0))
    or sys.version_info >= (3, 1)):
    sys.path.insert(0, 'python{0}/'.format(sys.version_info[0]))
    sys.path.insert(0, 'python23/')
else:
    raise RuntimeError("Python v%d.%d is not supported" %\
        sys.version_info[0:2])
    sys.exit(1)

import mysql.connector
import tests
from tests import mysqld

MY_CNF = """
# MySQL option file for MySQL Connector/Python tests
[mysqld-5.6]
innodb_compression_level = 0
innodb_compression_failure_threshold_pct = 0

[mysqld]
basedir = %(mysqld_basedir)s
datadir = %(mysqld_datadir)s
tmpdir = %(mysqld_tmpdir)s
port = %(mysqld_port)d
socket = %(mysqld_socket)s
bind_address = %(mysqld_bind_address)s
pid-file = %(mysqld_pid)s
skip_name_resolve
server_id = 19771406
sql_mode = ""
default_time_zone = +00:00
log-error = myconnpy_mysqld.err
log-bin = myconnpy_bin
general_log = ON
local_infile = 1
innodb_flush_log_at_trx_commit = 2
ssl
"""

# Platform specific configuration
if os.name == 'nt':
    MY_CNF += '\n'.join((
        "ssl-ca = %(ssl_dir)s\\\\tests_CA_cert.pem",
        "ssl-cert = %(ssl_dir)s\\\\tests_server_cert.pem",
        "ssl-key = %(ssl_dir)s\\\\tests_server_key.pem",
        ))
else:
    MY_CNF += '\n'.join((
        "ssl-ca = %(ssl_dir)s/tests_CA_cert.pem",
        "ssl-cert = %(ssl_dir)s/tests_server_cert.pem",
        "ssl-key = %(ssl_dir)s/tests_server_key.pem",
        "innodb_flush_method = O_DIRECT",
        ))

def _add_options(p):
    default_topdir = os.path.join(os.path.dirname(
        os.path.abspath(__file__)), 'mysql_myconnpy')
    p.add_option('-t','--test', dest='testcase', metavar='NAME',
        help='Tests to execute, one of %s' % tests.get_test_names())
    p.add_option('-T','--one-test', dest='onetest', metavar='NAME',
        help='Particular test to execute, format: '\
             '<module>[.<class>[.<method>]]. '\
             'For example, to run a particular '\
             'test BugOra13392739.test_reconnect() from the tests.test_bugs '\
             'module, use following value for the -T option: '\
             ' tests.test_bugs.BugOra13392739.test_reconnect')
    p.add_option('-l','--log', dest='logfile', metavar='NAME',
        default=None,
        help='Log file location (if not given, logging is disabled)')
    p.add_option('','--force', dest='force', action="store_true",
        default=False,
        help='Remove previous MySQL test installation.')
    p.add_option('','--keep', dest='keep', action="store_true",
        default=False,
        help='Keep MySQL installation (i.e. for debugging)')
    p.add_option('','--debug', dest='debug', action="store_true",
        default=False,
        help='Show/Log debugging messages')
    p.add_option('','--verbosity', dest='verbosity', metavar='NUMBER',
        default='0', type="int",
        help='Verbosity of unittests (default 0)')

    p.add_option('','--stats', dest='stats',
        default=False, action="store_true",
        help="Show timings of each individual test.")
    p.add_option('','--stats-host', dest='stats_host',
        default=None, metavar='NAME',
        help="MySQL server for saving unittest statistics. Specify this "
             "option to start saving results to a database. "
             "Implies --stats.")
    p.add_option('','--stats-port', dest='stats_port',
        default=3306, metavar='PORT',
        help="TCP/IP port of the MySQL server for saving unittest statistics. "
             "Implies --stats. (default 3306)")
    p.add_option('','--stats-user', dest='stats_user',
        default='root', metavar='NAME',
        help="User for connecting with the MySQL server for saving unittest "
             "statistics. Implies --stats. (default root)")
    p.add_option('','--stats-password', dest='stats_password',
        default='', metavar='PASSWORD',
        help="Password for connecting with the MySQL server for saving "
             "unittest statistics. Implies --stats. (default '')")
    p.add_option('','--stats-db', dest='stats_db',
        default='test', metavar='NAME',
        help="Database name for saving unittest statistics. "
             "Implies --stats. (default test)")

    p.add_option('','--mysql-basedir', dest='mysql_basedir',
        metavar='NAME', default='/usr/local/mysql',
        help='Where MySQL is installed. This is used to bootstrap and '\
         'run a MySQL server which is used for unittesting only.')
    p.add_option('','--mysql-topdir', dest='mysql_topdir',
        metavar='NAME',
        default=default_topdir,
        help='Where to bootstrap the new MySQL instance for testing. '\
         'Defaults to current ./mysql_myconnpy')
    p.add_option('','--bind-address', dest='bind_address', metavar='NAME',
        default='127.0.0.1',
        help='IP address to bind to')

    p.add_option('-H', '--host', dest='host', metavar='NAME',
        default='127.0.0.1',
        help='Hostname or IP address for TCP/IP connections.')
    p.add_option('-P', '--port', dest='port', metavar='NUMBER',
        default=33770, type="int",
        help='Port to use for TCP/IP connections.')
    p.add_option('', '--unix-socket', dest='unix_socket', metavar='NAME',
        default=os.path.join(default_topdir, 'myconnpy_mysql.sock'),
        help='Unix socket location.')

def _set_config(options):
    if options.host:
        tests.MYSQL_CONFIG['host'] = options.host
    if options.port:
        tests.MYSQL_CONFIG['port'] = options.port
    if options.unix_socket:
        tests.MYSQL_CONFIG['unix_socket'] = options.unix_socket
    tests.MYSQL_CONFIG['user'] = 'root'
    tests.MYSQL_CONFIG['password'] = ''
    tests.MYSQL_CONFIG['database'] = 'myconnpy'


def _show_help(msg=None,parser=None,exit=0):
    tests.printmsg(msg)
    if parser is not None:
        parser.print_help()
    if exit > -1:
        sys.exit(exit)

def get_stats_tablename():
    return "myconnpy_{version}".format(
        version='_'.join(map(str, mysql.connector.__version_info__[0:3]))
        )

def get_stats_field(pyver=None, myver=None):
    if not pyver:
        pyver = '.'.join(map(str, sys.version_info[0:2]))
    if not myver:
        myver = '.'.join(map(str, mysql_server.version[0:2]))
    return "py{python}my{mysql}".format(
        python=pyver.replace('.',''), mysql=myver.replace('.', ''))

class StatsTestResult(TextTestResult):
    separator1 = '=' * 78
    separator2 = '-' * 78

    def __init__(self, stream, descriptions, verbosity, dbcnx=None):
        super(StatsTestResult, self).__init__(stream, descriptions, verbosity)
        self.stream = stream
        self.showAll = 0
        self.dots = 0
        self.descriptions = descriptions
        self._start_time = None
        self._stop_time = None
        self.elapsed_time = None
        self._dbcnx = dbcnx
        self._name = None

    def get_description(self, test):
        return "{0:.<60s} ".format(str(test)[0:58])

    def startTest(self, test):
        super(StatsTestResult, self).startTest(test)
        self.stream.write(self.get_description(test))
        self.stream.flush()
        self._start_time = time.time()

    def addSuccess(self, test):
        super(StatsTestResult, self).addSuccess(test)
        self._stop_time = time.time()
        self.elapsed_time = self._stop_time - self._start_time
        fmt = "{timing:>8.3f}s {state:<20s}"
        self.stream.writeln(fmt.format(state="ok", timing=self.elapsed_time))
        if self._dbcnx:
            cur = self._dbcnx.cursor()
            stmt = (
                "INSERT INTO {table} (test_case, {field}) "
                "VALUES (%s, %s) ON DUPLICATE KEY UPDATE {field} = %s"
                ).format(table=get_stats_tablename(),
                         field=get_stats_field())
            cur.execute(stmt,
                (str(test), self.elapsed_time, self.elapsed_time)
                )
            cur.close()

    def _save_not_ok(self, test):
        cur = self._dbcnx.cursor()
        stmt = (
            "INSERT INTO {table} (test_case, {field}) "
            "VALUES (%s, %s) ON DUPLICATE KEY UPDATE {field} = %s"
            ).format(table=get_stats_tablename(),
                     field=get_stats_field())
        cur.execute(stmt, (str(test), -1, -1))
        cur.close()

    def addError(self, test, err):
        super(StatsTestResult, self).addError(test, err)
        self.stream.writeln("ERROR")
        if self._dbcnx:
            self._save_not_ok(test)

    def addFailure(self, test, err):
        super(StatsTestResult, self).addFailure(test, err)
        self.stream.writeln("FAIL")
        if self._dbcnx:
            self._save_not_ok(test)

    def addSkip(self, test, reason):
        super(StatsTestResult, self).addSkip(test, reason)
        self.stream.writeln("skipped")
        if self._dbcnx:
            self._save_not_ok(test)

    def addExpectedFailure(self, test, err):
        super(StatsTestResult, self).addExpectedFailure(test, err)
        self.stream.writeln("expected failure")
        if self._dbcnx:
            self._save_not_ok(test)

    def addUnexpectedSuccess(self, test):
        super(StatsTestResult, self).addUnexpectedSuccess(test)
        self.stream.writeln("unexpected success")
        if self._dbcnx:
            self._save_not_ok(test)


class StatsTestRunner(unittest.TextTestRunner):
    resultclass = StatsTestResult

    def __init__(self, stream=sys.stderr, descriptions=True, verbosity=1,
                 failfast=False, buffer=False, resultclass=None, dbcnx=None):
        try:
            super(StatsTestRunner, self).__init__(
                stream=sys.stderr, descriptions=True, verbosity=1,
                failfast=False, buffer=False)
        except TypeError:
            # Compatibility with Python v2.6
            super(StatsTestRunner, self).__init__(
                stream=sys.stderr, descriptions=True, verbosity=1)            
        self._dbcnx = dbcnx

    def _makeResult(self):
        return self.resultclass(self.stream, self.descriptions,
                                self.verbosity, dbcnx=self._dbcnx)

    def run(self, test):
        result = super(StatsTestRunner, self).run(test)
        if self._dbcnx:
            self._dbcnx.commit()
        return result

def setup_stats_db(cnx):
    cur = cnx.cursor()

    supported_python = ('2.6', '2.7', '3.1', '3.2', '3.3', '3.4')
    supported_mysql = ('5.1', '5.5', '5.6', '5.7')

    columns = []
    for py in supported_python:
        for my in supported_mysql:
            columns.append(
                " {field} DECIMAL(8,4) DEFAULT -1".format(
                    field=get_stats_field(py, my))
                )

    create_table = (
        "CREATE TABLE {table} ( "
        " test_case VARCHAR(100) NOT NULL,"
        " {pymycols}, "
        " PRIMARY KEY (test_case)"
        ") ENGINE=InnoDB"
        ).format(table=get_stats_tablename(),
                 pymycols=', '.join(columns))

    try:
        cur.execute(create_table)
    except mysql.connector.ProgrammingError as err:
        if err.errno != 1050:
            raise
        logger.info("Using exists table '{0}' for saving statistics".format(
            get_stats_tablename()))
    else:
        logger.info("Created table '{0}' for saving statistics".format(
            get_stats_tablename()))
    cur.close()

def main():
    global mysql_server
    global logger
    usage = 'usage: %prog [options]'
    parser = OptionParser()
    _add_options(parser)

    # Set options
    (options, args) = parser.parse_args()
    option_file = os.path.join(options.mysql_topdir,'myconnpy_my.cnf')
    _set_config(options)

    # Enabling logging
    formatter = logging.Formatter("%(asctime)s [%(name)s:%(levelname)s] %(message)s")
    logger = logging.getLogger(tests.LOGGER_NAME)
    fh = None
    if options.logfile is not None:
        fh = logging.FileHandler(options.logfile)
    else:
        fh = logging.StreamHandler()
    fh.setFormatter(formatter)
    if options.debug is True:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logger.addHandler(fh)
    logger.info(
            "MySQL Connector/Python unittest "
            "started using Python v{0}".format(
                '.'.join([ str(v) for v in sys.version_info[0:3]])))

    # Init the MySQL Server object
    mysql_server = mysqld.MySQLInit(
        options.mysql_basedir,
        options.mysql_topdir,
        MY_CNF,
        option_file,
        options.bind_address,
        options.port,
        options.unix_socket,
        os.path.abspath(tests.SSL_DIR),
        os.path.join(options.mysql_topdir, 'myconnpy_mysqld.pid'))
    mysql_server._debug = options.debug
    tests.MYSQL_VERSION = mysql_server.version
    tests.MYSQL_SERVER = mysql_server  # Tests can control the server

    have_to_bootstrap = True
    if options.force:
        # Force removal of previous test data
        if mysql_server.check_running():
            mysql_server.stop()
            if not mysql_server.wait_down():
                logger.error("Failed shutting down the MySQL server")
                sys.exit(1)
        mysql_server.remove()
    else:
        if mysql_server.check_running():
            logger.info("Reusing previously bootstrapped MySQL server")
            have_to_bootstrap = False
        elif not options.keep:
            logger.error(
                "Can not connect to previously bootstrapped MySQL Server; "
                "use --force option or --keep")
            sys.exit(1)

    # Check if we can test IPv6
    if options.bind_address.strip() != '::':
        tests.IPV6_AVAILABLE = False

    # Which tests cases to run
    if options.testcase is not None:
        if options.testcase in tests.get_test_names():
            modfile = os.path.join(
                'python23', 'tests23', 'test_{}.py'.format(options.testcase))
            if os.path.exists(modfile):
                testcases = [ 'tests23.test_%s' % options.testcase ]
            else:
                testcases = [ 'tests.test_%s' % options.testcase ]
        else:
            msg = "Test case is not one of %s" % tests.get_test_names()
            _show_help(msg=msg,parser=parser,exit=1)
        testsuite = unittest.TestLoader().loadTestsFromNames(testcases)
    elif options.onetest is not None:
        testsuite = unittest.TestLoader().loadTestsFromName(options.onetest)
    else:
        testcases = tests.active_testcases
        testsuite = unittest.TestLoader().loadTestsFromNames(testcases)
    
    # Bootstrap and start a MySQL server
    if have_to_bootstrap:
        logger.info("Bootstrapping a MySQL server")
        mysql_server.bootstrap()
        logger.info("Starting a MySQL server")
        mysql_server.start()
        if not mysql_server.wait_up():
            logger.error("Failed to start the MySQL server. Check error log.")
            sys.exit(1)

    logger.info(
        "Using MySQL server version {0}".format(
            '.'.join([ str(v) for v in mysql_server.version[0:3]])))

    logger.info("Starting unit tests")
    was_successful = False
    try:
        # Run test cases
        if options.stats:
            if options.stats_host:
                stats_db_info = {
                    'host': options.stats_host,
                    'port': options.stats_port,
                    'user': options.stats_user,
                    'password': options.stats_password,
                    'database': options.stats_db,
                    }
                cnxstats = mysql.connector.connect(**stats_db_info)
                setup_stats_db(cnxstats)
            else:
                cnxstats = None
            result = StatsTestRunner(
                verbosity=options.verbosity, dbcnx=cnxstats).run(
                    testsuite)
        else:
            result = unittest.TextTestRunner(verbosity=options.verbosity).run(
                testsuite)
        was_successful = result.wasSuccessful()
    except KeyboardInterrupt:
        logger.info("Unittesting was interrupted")
        was_successful = False

    # Log messages added by test cases
    for msg in tests.MESSAGES['WARNINGS']:
        logger.warning(msg)
    for msg in tests.MESSAGES['INFO']:
        logger.info(msg)

    # Clean up
    if not options.keep:
        mysql_server.stop()
        mysql_server.remove()
        logger.info("MySQL server stopped and cleaned up")
    else:
        logger.info("MySQL server kept running on %s:%d" %
                             (options.bind_address, options.port))

    txt = ""
    if not was_successful:
        txt = "not "
    logger.info("MySQL Connector/Python unittests were %ssuccessful" % txt)

    # Return result of tests as exit code
    sys.exit(not was_successful)
    
if __name__ == '__main__':
    main()

