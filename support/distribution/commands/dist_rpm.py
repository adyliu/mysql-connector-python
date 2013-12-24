# MySQL Connector/Python - MySQL driver written in Python.
# Copyright (c) 2012, 2013, Oracle and/or its affiliates. All rights reserved.

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

"""Implements the Distutils command 'bdist_com_rpm'

Implements the Distutils command 'bdist_com_rpm' which creates a built
commercial distribution RPM using the spec file available under in the
folder '/support/RPM/' of the source of Connector/Python.
"""


import sys
import os
import subprocess
from distutils import log
from distutils.errors import DistutilsError
from distutils.dir_util import remove_tree, mkpath
from distutils.file_util import copy_file
from distutils.command.bdist_dumb import bdist_dumb
from distutils.command.bdist import bdist
from distutils.core import Command

from support.distribution.commands import COMMON_USER_OPTIONS
from version import EDITION


class _RPMDist(Command):
    """Create a RPM distribution"""
    def _populate_topdir(self):
        """Create and populate the RPM topdir"""
        mkpath(self.topdir)
        dirs = ['BUILD', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS']
        self._rpm_dirs = {}
        for dirname in dirs:
            self._rpm_dirs[dirname] = os.path.join(self.topdir, dirname)
            self.mkpath(self._rpm_dirs[dirname])
    
    def _prepare_distribution(self):
        raise NotImplemented

    def _create_rpm(self, rpm_name):
        log.info("creating RPM using rpmbuild")
        macro_bdist_dir = "bdist_dir " + os.path.join(rpm_name, '')
        cmd = ['rpmbuild',
            '-bb',
            '--define', macro_bdist_dir,
            '--define', "_topdir " + os.path.abspath(self.topdir),
            self.rpm_spec
            ]
        if not self.verbose:
           cmd.append('--quiet')
        if self.edition:
            cmd.extend(['--define', "edition " + self.edition])

        self.spawn(cmd)

        rpms = os.path.join(self.topdir, 'RPMS')
        for base, dirs, files in os.walk(rpms):
            for filename in files:
                if filename.endswith('.rpm'):
                    filepath = os.path.join(base, filename)
                    copy_file(filepath, self.dist_dir)

    def run(self):
        """Run the distutils command"""
        # check whether we can execute rpmbuild
        if not self.dry_run:
            try:
                devnull = open(os.devnull, 'w')
                subprocess.Popen(['rpmbuild', '--version'],
                                 stdin=devnull, stdout=devnull)
            except OSError:
                raise DistutilsError("Cound not execute rpmbuild. Make sure "
                                     "it is installed and in your PATH")
        
        # build command: to get the build_base
        cmdbuild = self.get_finalized_command("build")
        cmdbuild.verbose = self.verbose 
        self.build_base = cmdbuild.build_base
        self.topdir = os.path.join(self.build_base, 'rpmtopdir')

        self._prepare_distribution()
        self._populate_topdir()
        self._create_rpm(rpm_name=self.target_rpm)

        if not self.keep_temp:
            remove_tree(self.build_base, dry_run=self.dry_run)

class BuiltCommercialRPM(_RPMDist):
    """Create a Built Commercial RPM distribution"""
    description = 'create a commercial built RPM distribution'
    user_options = [
        ('bdist-dir=', 'd',
         "temporary directory for creating the distribution"),
        ('keep-temp', 'k',
         "keep the pseudo-installation tree around after "
         "creating the distribution archive"),
        ('dist-dir=', 'd',
         "directory to put final built distributions in"),
        ('include-sources', None,
         "exclude sources built distribution (default: True)"),
    ] + COMMON_USER_OPTIONS

    boolean_options = [
        'keep-temp', 'include-sources'
    ]
    
    def initialize_options (self):
        """Initialize the options"""
        self.bdist_dir = None
        self.keep_temp = 0
        self.dist_dir = None
        self.include_sources = False
        self.edition = EDITION
    
    def finalize_options(self):
        """Finalize the options"""
        self.set_undefined_options('bdist',
                                   ('dist_dir', 'dist_dir'))

        mkpath(self.dist_dir)
        self.rpm_spec = 'support/RPM/connector_python_com.spec'
    
    def _prepare_distribution(self):
        """Prepare the distribution"""
        cmd = self.get_finalized_command("bdist_com")
        cmd.dry_run = self.dry_run
        cmd.dist_dir = os.path.join(self.topdir, 'BUILD')
        cmd.keep_temp = True
        cmd.edition = self.edition
        self.run_command("bdist_com")
        self.target_rpm = self.distribution.get_fullname()


class SDistGPLRPM(Command):
    """Create a source distribution packages as RPM"""
    description = "create a RPM distribution (GPL)"
    user_options = [
        ('bdist-base=', 'd',
         "base directory for creating distributions"),
        ('rpm-base=', 'd',
         "base directory for creating RPMs (default <bdist-dir>/rpm)"),
        ('keep-temp', 'k',
         "keep the pseudo-installation tree around after "
         "creating the distribution archive"),
        ('dist-dir=', 'd',
         "directory to put final built distributions in"),
    ] + COMMON_USER_OPTIONS

    rpm_spec = 'support/RPM/connector_python.spec'

    def initialize_options(self):
        """Initialize the options"""
        self.bdist_base = None
        self.rpm_base = None
        self.keep_temp = 0
        self.dist_dir = None
        self.edition = EDITION
    
    def finalize_options(self):
        """Finalize the options"""
        self.set_undefined_options('bdist', 
                                   ('bdist_base', 'bdist_base'),
                                   ('dist_dir', 'dist_dir'))

        if not self.rpm_base:
            self.rpm_base = os.path.join(self.bdist_base, 'rpm')

    def _populate_rpmbase(self):
        """Create and populate the RPM base directory"""
        self.mkpath(self.rpm_base)
        dirs = ['BUILD', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS']
        self._rpm_dirs = {}
        for dirname in dirs:
            self._rpm_dirs[dirname] = os.path.join(self.rpm_base, dirname)
            self.mkpath(self._rpm_dirs[dirname])

    def _create_rpm(self):
        log.info("creating RPM using rpmbuild")
        cmd = ['rpmbuild',
            '-bb',
            '--define', "_topdir " + os.path.abspath(self.rpm_base),
            self.rpm_spec
            ]

        if not self.verbose:
           cmd.append('--quiet')
        if self.edition:
            cmd.extend(['--define', "edition " + self.edition])

        self.spawn(cmd)

        rpms = os.path.join(self.rpm_base, 'RPMS')
        for base, dirs, files in os.walk(rpms):
            for filename in files:
                if filename.endswith('.rpm'):
                    filepath = os.path.join(base, filename)
                    copy_file(filepath, self.dist_dir)

    def run(self):
        """Run the distutils command"""
        # check whether we can execute rpmbuild
        self.mkpath(self.dist_dir)
        if not self.dry_run:
            try:
                devnull = open(os.devnull, 'w')
                subprocess.Popen(['rpmbuild', '--version'],
                    stdin=devnull, stdout=devnull, stderr=devnull)
            except OSError:
                raise DistutilsError("Cound not execute rpmbuild. Make sure "
                                     "it is installed and in your PATH")

        self._populate_rpmbase()
        
        sdist = self.get_finalized_command('sdist')
        sdist.dist_dir = self._rpm_dirs['SOURCES']
        sdist.formats = ['gztar']
        sdist.edition = self.edition
        self.run_command('sdist')
        
        self._create_rpm()

        if not self.keep_temp:
            remove_tree(self.bdist_base, dry_run=self.dry_run)
