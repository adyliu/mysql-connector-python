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

import sys
import os
import signal
import socket
import re
from shutil import rmtree
import tempfile
import subprocess
import logging
import time
import ctypes

import tests

logger = logging.getLogger(tests.LOGGER_NAME)

if os.name == 'nt':
    EXEC_MYSQLD = 'mysqld.exe'
    EXEC_MYSQL = 'mysql.exe'
else:
    EXEC_MYSQLD = 'mysqld'
    EXEC_MYSQL = 'mysql'


def process_running(pid):
    if os.name == 'nt':
        # We are on Windows
        winkernel = ctypes.windll.kernel32
        process = winkernel.OpenProcess(1, 0, pid)
        if not process:
            return False

        exit_code = kernel32.GetExitCodeProcess(
            process, ctypes.byref(ctypes.wintypes.DWORD()))
        winkernel.CloseHandle(process)

        # Error 259 means the process is till running
        # If exit_code was zero, there was an error and it assumed process
        # is not available.
        return (exit_code == 0) or exit_code.value == 259

    # We are on a UNIX-like system
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def get_pid(pid_file):
    """Return the PID read from the PID file

    Returns None or int.
    """
    try:
        return int(open(pid_file, 'r').readline().strip())
    except IOError:
        return None


class MySQLInstallError(Exception):

    def __init__(self, m):
        self.msg = m

    def __str__(self):
        return repr(self.msg)
        
class MySQLBootstrapError(MySQLInstallError):
    pass

class MySQLdError(MySQLInstallError):
    pass

class MySQLInstallBase(object):
    
    def __init__(self, basedir, optionFile=None):
        self._basedir = basedir
        self._bindir = None
        self._sbindir = None
        self._sharedir = None
        self._init_mysql_install()
        
        if optionFile is not None and os.access(optionFile,0):
            MySQLBootstrapError("Option file not accessible: %s" % \
                optionFile)
        self._optionFile = optionFile

    def _init_mysql_install(self):
        """Checking MySQL installation

        Check the MySQL installation and set the directories where
        to find binaries and SQL bootstrap scripts.

        Raises MySQLBootstrapError when something fails.
        """
        locs = ('libexec', 'bin', 'sbin')
        for loc in locs:
            d = os.path.join(self._basedir,loc)
            if os.access(os.path.join(d, EXEC_MYSQLD), 0):
                self._sbindir = d
            if os.access(os.path.join(d, EXEC_MYSQL), 0):
                self._bindir = d

        if self._bindir is None or self._sbindir is None:
            raise MySQLBootstrapError("MySQL binaries not found under %s" %\
                self._basedir)

        locs = ('share', 'share/mysql')
        for loc in locs:
            d = os.path.normpath(os.path.join(self._basedir,loc))
            if os.access(os.path.join(d,'mysql_system_tables.sql'),0):
                self._sharedir = d
                break

        if self._sharedir is None:
            raise MySQLBootstrapError("MySQL bootstrap scripts not found\
                under %s" % self._basedir)

class MySQLBootstrap(MySQLInstallBase):
    
    def __init__(self, topdir, datadir=None, optionFile=None,
                 basedir='/usr/local/mysql', tmpdir=None,
                 readOptionFile=False):
        if optionFile is not None:
            MySQLBootstrapError("No default option file support (yet)")
        self._topdir = topdir
        self._datadir = datadir or os.path.join(topdir,'data')
        self._tmpdir = tmpdir or os.path.join(topdir,'tmp')
        self.extra_sql = list()
        super(MySQLBootstrap, self).__init__(basedir, optionFile)
        
    def _create_directories(self):
        """Create directory structure for bootstrapping
        
        Create the directories needed for bootstrapping a MySQL
        installation, i.e. 'mysql' directory.
        The 'test' database is deliberately not created.
        
        Raises MySQLBootstrapError when something fails.
        """
        logger.debug("Creating %(d)s %(d)s/mysql and %(d)s/test" % dict(
            d=self._datadir))
        try:
            os.mkdir(self._topdir)
            os.mkdir(os.path.join(self._topdir, 'tmp'))
            os.mkdir(self._datadir)
            os.mkdir(os.path.join(self._datadir, 'mysql'))
        except OSError as e:
            raise MySQLBootstrapError("Failed creating directories: " + str(e))

    def _get_bootstrap_cmd(self):
        """Get the command for bootstrapping.
        
        Get the command which will be used for bootstrapping. This is
        the full path to the mysqld executable and its arguments.
        
        Returns a list (used with subprocess.Popen)
        """
        cmd = [
          os.path.join(self._sbindir, EXEC_MYSQLD),
          '--no-defaults',
          '--bootstrap',
          '--basedir=%s' % self._basedir,
          '--datadir=%s' % self._datadir,
          '--log-warnings=0',
          #'--loose-skip-innodb',
          '--loose-skip-ndbcluster',
          '--max_allowed_packet=8M',
          '--default-storage-engine=myisam',
          '--net_buffer_length=16K',
          '--tmpdir=%s' % self._tmpdir,
        ]
        return cmd
    
    def bootstrap(self):
        """Bootstrap a MySQL installation
        
        Bootstrap a MySQL installation using the mysqld executable
        and the --bootstrap option. Arguments are defined by reading
        the defaults file and options set in the _get_bootstrap_cmd()
        method.
        
        Raises MySQLBootstrapError when something fails.
        """
        if os.access(self._datadir,0):
            raise MySQLBootstrapError("Datadir exists, can't bootstrap MySQL")
        
        # Order is important
        script_files = (
            'mysql_system_tables.sql',
            'mysql_system_tables_data.sql',
            'fill_help_tables.sql',
            )
        
        self._create_directories()
        try:
            cmd = self._get_bootstrap_cmd()
            sql = list()
            sql.append("USE mysql;")
            for f in script_files:
                logger.debug("Reading SQL from '%s'" % f)
                fp = open(os.path.join(self._sharedir,f),'r')
                sql += [ line.strip() for line in fp.readlines() ]
                fp.close()
            sql += self.extra_sql
            devnull = open(os.devnull, 'w')
            prc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                   stderr=devnull, stdout=devnull)
            prc.communicate('\n'.join(sql))
        except Exception as e:
            raise MySQLBootstrapError(e)

class MySQLd(MySQLInstallBase):
    
    def __init__(self, basedir, optionFile):
        self._process = None
        super(MySQLd, self).__init__(basedir, optionFile)
        self._version = self._get_version()
        
    def _get_cmd(self):
        cmd = [
            os.path.join(self._sbindir, EXEC_MYSQLD),
            "--defaults-file=%s" % (self._optionFile)
        ]

        if os.name == 'nt':
            cmd.append('--standalone')

        return cmd

    def _get_version(self):
        """Get the MySQL server version
        
        This method executes mysqld with the --version argument. It parses
        the output looking for the version number and returns it as a
        tuple with integer values: (major,minor,patch)
        
        Returns a tuple.
        """
        cmd = [
            os.path.join(self._sbindir, EXEC_MYSQLD),
            '--version'
        ]
        
        prc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        verstr = str(prc.communicate()[0])
        matches = re.match(r'.*Ver (\d)\.(\d).(\d{1,2}).*', verstr)
        if matches:
            return tuple([int(v) for v in matches.groups()])
        else:
            raise MySQLdError('Failed reading version from mysqld --version')
    
    @property
    def version(self):
        """Returns the MySQL server version
        
        Returns a tuple.
        """
        return self._version
        
    def start(self):
        try:
            cmd = self._get_cmd()
            devnull = open(os.devnull, 'w')
            self._process = subprocess.Popen(cmd, stdout=devnull,
                                             stderr=devnull)
        except Exception as e:
            raise MySQLdError(e)
    
    def stop(self):
        if not self._process:
            return False
        try:
            try:
                self._process.terminate()
            except AttributeError:
                os.kill(self._process.pid, signal.SIGKILL)
        except Exception as e:
            raise MySQLdError(e)

        return True


class MySQLInit(object):
    
    def __init__(self, basedir, topdir, cnf, option_file, bind_address, port,
                 unix_socket, ssldir, pid):
        self._cnf = cnf
        self._option_file = option_file
        self._unix_socket = unix_socket
        self._bind_address = bind_address
        self._port = port
        self._topdir = topdir
        self._basedir = basedir
        self._ssldir = ssldir
        self._pid_file = pid
        
        self._install = None
        self._server = None
        self._debug = False

        self._server = MySQLd(self._basedir, self._option_file)

    @property
    def version(self):
        """Returns the MySQL server version
        
        Returns a tuple.
        """
        return self._server.version

    def _get_pid(self):
        """Return the PID read from the PID file

        Returns None or int.
        """
        try:
            return int(open(self._pid_file, 'r').readline().strip())
        except IOError:
            return None

    def _slashes(self, path):
        """Convert forward slashes with backslashes

        This method replaces forward slashes with backslashes. This
        is necessary using Microsoft Windows for location of files in
        the option files.

        Returns a string.
        """
        if os.name == 'nt':
            nmpath = os.path.normpath(path)
            return path.replace('\\', '\\\\')
        return path
        
    def bootstrap(self):
        """Bootstrap a MySQL server"""
        try:
            self._install = MySQLBootstrap(self._topdir,
                basedir=self._basedir)
            self._install.extra_sql = (
                "CREATE DATABASE myconnpy;",)
            self._install.bootstrap()
        except Exception as e:
            logger.error("Failed bootstrapping MySQL: %s" % e)
            if self._debug is True:
                raise
            sys.exit(1)
    
    def start(self):
        """Start a MySQL server"""
        if self.check_running():
            logger.error("Not started MySQL server; already running")
            return

        options = {
            'mysqld_basedir': self._slashes(self._basedir),
            'mysqld_datadir': self._slashes(self._install._datadir),
            'mysqld_tmpdir': self._slashes(self._install._tmpdir),
            'mysqld_bind_address': self._bind_address,
            'mysqld_port': self._port,
            'mysqld_socket': self._slashes(self._unix_socket),
            'ssl_dir': self._slashes(self._ssldir),
            'mysqld_pid': self._slashes(self._pid_file),
            }
        try:
            fp = open(self._option_file,'w')
            fp.write(self._cnf % options)
            fp.close()
            self._server = MySQLd(self._basedir, self._option_file)
            self._server.start()
            time.sleep(3)
        except MySQLdError as err:
            logger.error("Failed starting MySQL server: %s" % err)
            if self._debug is True:
                raise
            sys.exit(1)

    def stop(self):
        pid = get_pid(self._pid_file)
        if not pid:
            return
        logger.info("Stopping MySQL server (pid={0})".format(pid))
        try:
            if not self._server.stop():
                os.kill(pid, signal.SIGKILL)
        except MySQLdError as err:
            logger.error("Failed stopping MySQL server: {0}".format(err))
            if self._debug is True:
                raise
        else:
            time.sleep(3)
            logger.info("MySQL server stopped (pid={0})".format(pid))
            return True

        return False
    
    def remove(self):
        try:
            rmtree(self._topdir)
        except Exception as e:
            logger.debug("Failed removing %s: %s" % (self._topdir, e))
            if self._debug is True:
                raise
        else:
            logger.info("Removed %s" % self._topdir)

    def check_running(self):
        """Check if MySQL server is running

        Check if the MySQL server is running using the PID file.

        Returns True or False.
        """
        pid = get_pid(self._pid_file)
        if pid:
            return process_running(pid)

        return False

    def wait_up(self, tries=10, delay=1):
        """Wait until the MySQL server is up

        This method can be used to wait until the MySQL server is started.
        True is returned when the MySQL server is up, False otherwise.

        Return True or False.
        """
        running = self.check_running()
        while not running:
            if tries == 0:
                break
            time.sleep(delay)
            running = self.check_running()
            tries -= 1

        return running

    def wait_down(self, tries=10, delay=1):
        """Wait until the MySQL server is down

        This method can be used to wait until the MySQL server has stopped.
        True is returned when the MySQL server is down, False otherwise.

        Return True or False.
        """
        running = self.check_running()
        while running:
            if tries == 0:
                break
            time.sleep(delay)
            running = self.check_running()
            tries -= 1

        return running
