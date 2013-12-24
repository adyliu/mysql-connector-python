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

unittests.py launches all or selected unit tests. For more information and
options, simply do:
 shell> python unittests.py --help

The unittest.py script will check for tests in Python source files prefixed
with 'test_' in the folder tests/. Tests and other data specific to a
Python major version are stored in tests/py2 and tests/py3.

Examples:
 Running unit tests using MySQL installed under /opt
 shell> python unittests.py --with-mysql=/opt/mysql/mysql-5.7

 Executing unit tests for cursor module
 shell> python unittests.py -t cursor

 Keep the MySQL server(s) running; speeds up multiple runs:
 shell> python unittests.py --keep

 Force shutting down of still running MySQL servers, and bootstrap again:
 shell> python unittests.py --force

 Show a more verbose and comprehensive output of tests (see --help to safe
 information to a database):
 shell> python unittests.py --keep --stats

 Run tests using IPv6:
 shell> python unittests.py --ipv6

unittests.py has exit status 0 when tests were ran successfully, 1 otherwise.

"""
import sys
import os
import time
import unittest
import logging
try:
    from argparse import ArgumentParser
except:
    from optparse import OptionParser

try:
    from unittest import TextTestResult
except ImportError:
    # Compatibility with Python v2.6
    from unittest import _TextTestResult as TextTestResult

import tests
from tests import mysqld

_TOPDIR = os.path.dirname(os.path.realpath(__file__))
LOGGER = logging.getLogger(tests.LOGGER_NAME)
tests.setup_logger(LOGGER)

# Only run for supported Python Versions
if not ((sys.version_info >= (2, 6) and sys.version_info < (3, 0))
        or sys.version_info >= (3, 1)):
    LOGGER.error("Python v{0}.{1} is not supported".format(
        *sys.version_info[0:2]))
else:
    # The following is only needed for running examples tests
    sys.path.insert(0, os.path.join(
        _TOPDIR, 'python{0}'.format(sys.version_info[0])))
    # Install Connector/Python and add it to sys.path
    tests.TEST_BUILD_DIR = os.path.join(_TOPDIR, 'build', 'testing')
    tests.install_connector(_TOPDIR, tests.TEST_BUILD_DIR)
    sys.path.insert(0, tests.TEST_BUILD_DIR)

import mysql.connector

# MySQL option file template. Platform specifics dynamically added later.
MY_CNF = """
# MySQL option file for MySQL Connector/Python tests
[mysqld-5.6]
innodb_compression_level = 0
innodb_compression_failure_threshold_pct = 0
lc_messages_dir = {lc_messages_dir}
lc_messages = en_US

[mysqld-5.5]
lc_messages_dir = {lc_messages_dir}
lc_messages = en_US

[mysqld-5.1]
language = {lc_messages_dir}

[mysqld-5.0]
language = {lc_messages_dir}

[mysqld]
basedir = {basedir}
datadir = {datadir}
tmpdir = {tmpdir}
port = {port}
socket = {unix_socket}
bind_address = {bind_address}
pid-file = {pid_file}
skip_name_resolve
server_id = {serverid}
sql_mode = ""
default_time_zone = +00:00
log-error = mysqld_{name}.err
log-bin = mysqld_{name}_bin
general_log = ON
local_infile = 1
innodb_flush_log_at_trx_commit = 2
ssl
"""

# Platform specifics
if os.name == 'nt':
    MY_CNF += '\n'.join((
        "ssl-ca = {ssl_dir}\\\\tests_CA_cert.pem",
        "ssl-cert = {ssl_dir}\\\\tests_server_cert.pem",
        "ssl-key = {ssl_dir}\\\\tests_server_key.pem",
    ))
    MYSQL_DEFAULT_BASE = os.path.join(
        "C:/", "Program Files", "MySQL", "MySQL Server 5.6")
else:
    MY_CNF += '\n'.join((
        "ssl-ca = {ssl_dir}/tests_CA_cert.pem",
        "ssl-cert = {ssl_dir}/tests_server_cert.pem",
        "ssl-key = {ssl_dir}/tests_server_key.pem",
        "innodb_flush_method = O_DIRECT",
    ))
    MYSQL_DEFAULT_BASE = os.path.join('/', 'usr', 'local', 'mysql')

MYSQL_DEFAULT_TOPDIR = _TOPDIR

_UNITTESTS_CMD_ARGS = {
    ('-T', '--one-test'): {
        'dest': 'onetest', 'metavar': 'NAME',
        'help': (
            'Particular test to execute, format: '
            '<module>[.<class>[.<method>]]. For example, to run a particular '
            'test BugOra13392739.test_reconnect() from the tests.test_bugs '
            'module, use following value for the -T option: '
            ' tests.test_bugs.BugOra13392739.test_reconnect')
    },

    ('-t', '--test'): {
        'dest': 'testcase', 'metavar': 'NAME',
        'help': 'Tests to execute, one of {names}'.format(
            names=tests.get_test_names())
    },

    ('-l', '--log'): {
        'dest': 'logfile', 'metavar': 'NAME', 'default': None,
        'help': 'Log file location (if not given, logging is disabled)'
    },

    ('', '--force'): {
        'dest': 'force', 'action': 'store_true', 'default': False,
        'help': 'Remove previous MySQL test installation.'
    },

    ('', '--keep'): {
        'dest': 'keep', 'action': "store_true", 'default': False,
        'help': 'Keep MySQL installation (i.e. for debugging)'
    },

    ('', '--debug'): {
        'dest': 'debug', 'action': 'store_true', 'default': False,
        'help': 'Show/Log debugging messages'
    },

    ('', '--verbosity'): {
        'dest': 'verbosity', 'metavar': 'NUMBER', 'default': 0, 'type': int,
        'help': 'Verbosity of unittests (default 0)',
        'type_optparse': 'int'
    },

    ('', '--stats'): {
        'dest': 'stats', 'default': False, 'action': 'store_true',
        'help': "Show timings of each individual test."
    },

    ('', '--stats-host'): {
        'dest': 'stats_host', 'default': None, 'metavar': 'NAME',
        'help': (
            "MySQL server for saving unittest statistics. Specify this option "
            "to start saving results to a database. Implies --stats.")
    },

    ('', '--stats-port'): {
        'dest': 'stats_port', 'default': 3306, 'metavar': 'PORT',
        'help': (
            "TCP/IP port of the MySQL server for saving unittest statistics. "
            "Implies --stats. (default 3306)")
    },

    ('', '--stats-user'): {
        'dest': 'stats_user', 'default': 'root', 'metavar': 'NAME',
        'help': (
            "User for connecting with the MySQL server for saving unittest "
            "statistics. Implies --stats. (default root)")
    },

    ('', '--stats-password'): {
        'dest': 'stats_password', 'default': '', 'metavar': 'PASSWORD',
        'help': (
            "Password for connecting with the MySQL server for saving unittest "
            "statistics. Implies --stats. (default to no password)")
    },

    ('', '--stats-db'): {
        'dest': 'stats_db', 'default': 'test', 'metavar': 'NAME',
        'help': (
            "Database name for saving unittest statistics. "
            "Implies --stats. (default test)")
    },

    ('', '--with-mysql'): {
        'dest': 'mysql_basedir', 'metavar': 'NAME',
        'default': MYSQL_DEFAULT_BASE,
        'help': (
            "Installation folder of the MySQL server. "
            "(default {default})").format(default=MYSQL_DEFAULT_BASE)
    },

    ('', '--mysql-topdir'): {
        'dest': 'mysql_topdir', 'metavar': 'NAME',
        'default': MYSQL_DEFAULT_TOPDIR,
        'help': (
            "Where to bootstrap the new MySQL instances for testing. "
            "(default {default})").format(default=MYSQL_DEFAULT_TOPDIR)
    },

    ('', '--bind-address'): {
        'dest': 'bind_address', 'metavar': 'NAME', 'default': '127.0.0.1',
        'help': 'IP address to bind to'
    },

    ('-H', '--host'): {
        'dest': 'host', 'metavar': 'NAME', 'default': '127.0.0.1',
        'help': 'Hostname or IP address for TCP/IP connections.'
    },

    ('-P', '--port'): {
        'dest': 'port', 'metavar': 'NUMBER', 'default': 33770, 'type': int,
        'help': 'First TCP/IP port to use.',
        'type_optparse': int,
    },

    ('', '--unix-socket'): {
        'dest': 'unix_socket_folder', 'metavar': 'NAME',
        'help': 'Folder where UNIX Sockets will be created'
    },

    ('', '--ipv6'): {
        'dest': 'ipv6', 'action': 'store_true', 'default': False,
        'help': (
            'Use IPv6 to run tests. This sets --bind-address=:: --host=::1.'
        ),
    },
}


def _get_arg_options():
    """Parse comand line ArgumentParser

    This function parses the command line arguments and returns the options.

    It works with both optparse and argparse where available.
    """
    def _clean_optparse(adict):
        """Remove items from dictionary ending with _optparse"""
        new = {}
        for key in adict.keys():
            if not key.endswith('_optparse'):
                new[key] = adict[key]
        return new

    new = True
    try:
        parser = ArgumentParser()
        add = parser.add_argument
    except NameError:
        # Fallback to old optparse
        new = False
        parser = OptionParser()
        add = parser.add_option

    for flags, params in _UNITTESTS_CMD_ARGS.items():
        if new:
            flags = [i for i in flags if i]
        add(*flags, **_clean_optparse(params))

    options = parser.parse_args()

    if isinstance(options, tuple):
        # Fallback to old optparse
        return options[0]

    return options


def _show_help(msg=None, parser=None, exit_code=0):
    """Show the help of the given parser and exits

    If exit_code is -1, this function will not call sys.exit().
    """
    tests.printmsg(msg)
    if parser is not None:
        parser.print_help()
    if exit > -1:
        sys.exit(exit_code)


def get_stats_tablename():
    return "myconnpy_{version}".format(
        version='_'.join(
            [str(i) for i in mysql.connector.__version_info__[0:3]]
        )
    )


def get_stats_field(pyver=None, myver=None):
    if not pyver:
        pyver = '.'.join([str(i) for i in sys.version_info[0:2]])
    if not myver:
        myver = '.'.join([str(i) for i in tests.MYSQL_SERVERS[0].version[0:2]])
    return "py{python}my{mysql}".format(
        python=pyver.replace('.', ''), mysql=myver.replace('.', ''))


class StatsTestResult(TextTestResult):

    """Store test results in a database"""
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

    def get_description(self, test):  # pylint: disable=R0201
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
        try:
            super(StatsTestResult, self).addSkip(test, reason)
        except AttributeError:
            # We are using Python v2.6/v3.1
            pass
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

    """Committing results test results"""
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


class BasicTestResult(TextTestResult):

    """Basic test result"""

    def addSkip(self, test, reason):
        """Save skipped reasons"""
        tests.MESSAGES['SKIPPED'].append(reason)


class BasicTestRunner(unittest.TextTestRunner):

    """Basic test runner"""
    resultclass = BasicTestResult

    def __init__(self, stream=sys.stderr, descriptions=True, verbosity=1,
                 failfast=False, buffer=False):
        try:
            super(BasicTestRunner, self).__init__(
                stream=stream, descriptions=descriptions,
                verbosity=verbosity, failfast=failfast, buffer=buffer)
        except TypeError:
            # Python v3.1
            super(BasicTestRunner, self).__init__(
                stream=stream, descriptions=descriptions, verbosity=verbosity)


class Python26TestRunner(unittest.TextTestRunner):

    """Python v2.6/3.1 Test Runner backporting needed functionality"""

    def __init__(self, stream=sys.stderr, descriptions=True, verbosity=1,
                 failfast=False, buffer=False):
        super(Python26TestRunner, self).__init__(
            stream=stream, descriptions=descriptions, verbosity=verbosity)

    def _makeResult(self):
        return BasicTestResult(self.stream, self.descriptions, self.verbosity)


def setup_stats_db(cnx):
    """Setup the database for storing statistics"""
    cur = cnx.cursor()

    supported_python = ('2.6', '2.7', '3.1', '3.2', '3.3', '3.4')
    supported_mysql = ('5.1', '5.5', '5.6', '5.7')

    columns = []
    for pyver in supported_python:
        for myver in supported_mysql:
            columns.append(
                " py{python}my{mysql} DECIMAL(8,4) DEFAULT -1".format(
                    python=pyver.replace('.', ''),
                    mysql=myver.replace('.', ''))
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
        LOGGER.info("Using exists table '{0}' for saving statistics".format(
            get_stats_tablename()))
    else:
        LOGGER.info("Created table '{0}' for saving statistics".format(
            get_stats_tablename()))
    cur.close()


def init_mysql_server(port, options):
    """Initialize a MySQL Server"""
    name = 'server{0}'.format(len(tests.MYSQL_SERVERS) + 1)

    try:
        mysql_server = mysqld.MySQLServer(
            basedir=options.mysql_basedir,
            topdir=os.path.join(options.mysql_topdir, 'cpy_' + name),
            cnf=MY_CNF,
            bind_address=options.bind_address,
            port=port,
            unix_socket_folder=options.unix_socket_folder,
            ssl_folder=os.path.abspath(tests.SSL_DIR),
            name=name)
    except tests.mysqld.MySQLBootstrapError as err:
        LOGGER.error("Failed initializing MySQL server "
                     "'{name}': {error} (use --with-mysql?)".format(
                         name=name, error=str(err)))
        sys.exit(1)

    mysql_server._debug = options.debug

    have_to_bootstrap = True
    if options.force:
        # Force removal of previous test data
        if mysql_server.check_running():
            mysql_server.stop()
            if not mysql_server.wait_down():
                LOGGER.error(
                    "Failed shutting down the MySQL server '{name}'".format(
                        name=name))
                sys.exit(1)
        mysql_server.remove()
    else:
        if mysql_server.check_running():
            LOGGER.info(
                "Reusing previously bootstrapped MySQL server '{name}'".format(
                    name=name))
            have_to_bootstrap = False
        else:
            LOGGER.warning(
                "Can not connect to previously bootstrapped "
                "MySQL Server '{name}'; forcing bootstrapping".format(
                    name=name))
            mysql_server.remove()

    tests.MYSQL_VERSION = mysql_server.version
    tests.MYSQL_SERVERS.append(mysql_server)

    mysql_server.client_config = {
        'host': options.host,
        'port': port,
        'unix_socket': mysql_server._unix_socket,
        'user': 'root',
        'password': '',
        'database': 'myconnpy',
        'connection_timeout': 5,
    }

    # Bootstrap and start a MySQL server
    if have_to_bootstrap:
        LOGGER.info("Bootstrapping MySQL server '{name}'".format(name=name))
        try:
            mysql_server.bootstrap()
        except tests.mysqld.MySQLBootstrapError:
            LOGGER.error("Failed bootstrapping MySQL server '{name}'".format(
                name=name))
            sys.exit(1)
        mysql_server.start()
        if not mysql_server.wait_up():
            LOGGER.error("Failed to start the MySQL server '{name}'. "
                         "Check error log.".format(name=name))
            sys.exit(1)


def main():
    options = _get_arg_options()

    tests.setup_logger(LOGGER, debug=options.debug, logfile=options.logfile)
    LOGGER.info(
        "MySQL Connector/Python unittest "
        "started using Python v{0}".format(
            '.'.join([str(v) for v in sys.version_info[0:3]])))

    # Check if we can test IPv6
    if options.ipv6:
        if not tests.IPV6_AVAILABLE:
            LOGGER.error("Can not test IPv6: not available on your system")
            sys.exit(1)
        options.bind_address = '::'
        options.host = '::1'
        LOGGER.info("Testing using IPv6. Binding to :: and using host ::1")
    else:
        tests.IPV6_AVAILABLE = False

    # Which tests cases to run
    if options.testcase:
        if options.testcase in tests.get_test_names():
            for module in tests.get_test_modules():
                if module.endswith('test_' + options.testcase):
                    testcases = [module]
                    break
            testsuite = unittest.TestLoader().loadTestsFromNames(testcases)
        else:
            msg = "Test case is not one of {0}".format(
                ', '.join(tests.get_test_names()))
            _show_help(msg=msg, parser=parser, exit_code=1)
    elif options.onetest:
        testsuite = unittest.TestLoader().loadTestsFromName(options.onetest)
    else:
        testcases = tests.get_test_modules()
        testsuite = unittest.TestLoader().loadTestsFromNames(testcases)

    # Initialize the MySQL Servers
    for i in range(0, tests.MYSQL_SERVERS_NEEDED):
        init_mysql_server(port=(options.port + i), options=options)

    LOGGER.info(
        "Using MySQL server version {0}".format(
            '.'.join([str(v) for v in tests.MYSQL_VERSION[0:3]])))

    LOGGER.info("Starting unit tests")
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
        elif sys.version_info[0:2] == (2, 6):
            result = Python26TestRunner(verbosity=options.verbosity).run(
                testsuite)
        else:
            result = BasicTestRunner(verbosity=options.verbosity).run(
                testsuite)
        was_successful = result.wasSuccessful()
    except KeyboardInterrupt:
        LOGGER.info("Unittesting was interrupted")
        was_successful = False

    # Log messages added by test cases
    for msg in tests.MESSAGES['WARNINGS']:
        LOGGER.warning(msg)
    for msg in tests.MESSAGES['INFO']:
        LOGGER.info(msg)

    # Show skipped tests
    if len(tests.MESSAGES['SKIPPED']):
        LOGGER.info(
            "Skipped tests: {0}".format(
                len(tests.MESSAGES['SKIPPED'])))
        if options.verbosity >= 1 or options.debug:
            for msg in tests.MESSAGES['SKIPPED']:
                LOGGER.info(msg)

    # Clean up
    for mysql_server in tests.MYSQL_SERVERS:
        name = mysql_server.name
        if not options.keep:
            mysql_server.stop()
            if not mysql_server.wait_down():
                LOGGER.error("Failed stopping MySQL server '{name}'".format(
                    name=name))
            else:
                mysql_server.remove()
                LOGGER.info(
                    "MySQL server '{name}' stopped and cleaned up".format(
                        name=name))
        elif not mysql_server.check_running():
            mysql_server.start()
            if not mysql_server.wait_up():
                LOGGER.error("MySQL could not be kept running; "
                             "failed to restart")
        else:
            LOGGER.info("MySQL server kept running on {addr}:{port}".format(
                addr=mysql_server.bind_address,
                port=mysql_server.port)
            )

    txt = ""
    if not was_successful:
        txt = "not "
    LOGGER.info(
        "MySQL Connector/Python unittests were {result}successful".format(
            result=txt))

    # Return result of tests as exit code
    sys.exit(not was_successful)

if __name__ == '__main__':
    main()
