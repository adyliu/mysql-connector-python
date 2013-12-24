# MySQL Connector/Python - MySQL driver written in Python.
# Copyright (c) 2012, 2013, Oracle and/or its affiliates. All rights reserved.

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

"""Implements the Distutils command 'bdist_com_egg'

Implements the Distutils command 'bdist_com_egg' which creates a built
commercial distribution Egg archive and a pth-file.

Note: This method of distribution can not be used currently since it will not
work with any other packages installed in the 'mysql' package.
"""

import sys
import os
import subprocess
import json
from distutils import log
from distutils.errors import DistutilsError, DistutilsOptionError
from distutils.core import Command
from distutils.util import byte_compile
from distutils.dir_util import remove_tree, mkpath, copy_tree
from distutils.file_util import copy_file
from distutils.sysconfig import get_python_version
from distutils.command.bdist_dumb import bdist_dumb
from distutils.command.install_data import install_data
from distutils.command.bdist import bdist

class BuiltCommercialEgg(bdist_dumb):
    """Create a Built Commercial Egg distribution"""
    description = 'create a commercial built egg distribution'
    user_options = [
        ('bdist-dir=', 'd',
         "temporary directory for creating the distribution"),
        ('keep-temp', 'k',
         "keep the pseudo-installation tree around after " +
         "creating the distribution archive"),
        ('dist-dir=', 'd',
         "directory to put final built distributions in"),
        ('include-sources', None,
         "exclude sources built distribution (default: True)"),
        ('without-pth', None,
         "don't create the path file")
    ]

    boolean_options = [
        'keep-temp', 'without-pth', 'include-sources'
    ]

    def initialize_options (self):
        """Initialize the options"""
        self.bdist_dir = None
        self.keep_temp = 0
        self.dist_dir = None
        self.include_sources = False
        self.without_pth = False
        self.plat_name = ''

    def finalize_options(self):
        """Finalize the options"""
        if self.bdist_dir is None:
            bdist_base = self.get_finalized_command('bdist').bdist_base
            self.bdist_dir = os.path.join(bdist_base, 'egg')

        self.set_undefined_options('bdist',
                                   ('dist_dir', 'dist_dir'),
                                   ('plat_name', 'plat_name'),)
        
        commercial_license = 'Other/Proprietary License'
        self.distribution.metadata.license = commercial_license
        
        python_version = get_python_version()
        if self.include_sources:
            pyver = python_version[0:2]
        else:
            pyver = python_version
        
        # Change classifiers
        new_classifiers = []
        for classifier in self.distribution.metadata.classifiers:
            if classifier.startswith("License ::"):
                classifier = "License :: " + commercial_license
            elif (classifier.startswith("Programming Language ::") and
                  (pyver not in classifier)):
                  log.info("removing classifier %s" % classifier)
                  continue
            new_classifiers.append(classifier)
        self.distribution.metadata.classifiers = new_classifiers

    def _remove_sources(self):
        """Remove Python source files from the build directory"""
        for base, dirs, files in os.walk(self.bdist_dir):
            for filename in files:
                if filename.endswith('.py'):
                    filepath = os.path.join(base, filename)
                    log.info("removing source '%s'", filepath)
                    os.unlink(filepath)
    
    def _create_path_file(self):
        """Create a pth-file with same basename as egg file"""
        pthfile = self.egg.get_path_filename()
        log.info("creating path file '%s'" % pthfile)
        if not self.dry_run:
            fp = open(pthfile, 'w')
            fp.write('./' + os.path.basename(self.egg.get_archive_name()))
            fp.write('\n\n')
            fp.close()

    def run(self):
        """Run the distutils command"""
        log.info("installing library code to %s" % self.bdist_dir)
        
        egg_name = _get_dist_name(self.distribution,
                                  source_only_dist=self.include_sources)
        self.egg = egg.Egg(name=egg_name,
                           destination=self.dist_dir,
                           builtdir=self.bdist_dir, info_file=None)
        log.info("egg will created as '%s'" % self.egg.get_archive_name())
        
        # build command: just to get the build_base
        cmdbuild = self.get_finalized_command("build")
        self.build_base = cmdbuild.build_base
        
        # install command
        install = self.reinitialize_command('install', reinit_subcommands=1)
        install.compile = False
        install.warn_dir = 0
        install.prefix = self.bdist_dir
        install.install_purelib = self.bdist_dir
        
        log.info("installing to %s" % self.bdist_dir)
        self.run_command('install')
        
        # install_data command
        install_data = self.reinitialize_command('install_data',
                                                 reinit_subcommands=1)
        install_data.install_dir = self.bdist_dir
        
        log.info("installing data files to %s" % self.bdist_dir)
        self.run_command('install_data')
        
        # install_egg_info command
        cmd_egginfo = self.get_finalized_command('install_egg_info')
        self.egg._info_file = cmd_egginfo.target

        # remove the GPL license
        to_compile = install.get_outputs()
        ignore = [
            os.path.join(self.bdist_dir,
                         os.path.normcase('mysql/__init__.py')),
            cmd_egginfo.target,
            os.path.join(self.bdist_dir,
                         os.path.normcase('mysql/connector/version.py')),
        ]
        for pyfile in install.get_outputs():
            if pyfile not in ignore:
                _remove_gpl(pyfile, dry_run=self.dry_run)
        
        # compile and remove sources
        if not self.include_sources:
            byte_compile(to_compile, optimize=0,
                         force=True, prefix=install.root)
            self._remove_sources()
        
        # create the egg
        info_files = [
            ('README_com.txt', 'README.txt'),
            ('LICENSE_com.txt', 'LICENSE.txt')
        ]
        self.egg.create(out=self.egg.get_archive_name(),
                        extra_info_files=info_files,
                        zip_safe=getattr(self.distribution, 'zip_safe', True),
                        dry_run=self.dry_run)
        
        # create the pth-file
        if not self.without_pth:
            self._create_path_file()

        if not self.keep_temp:
            remove_tree(self.build_base, dry_run=self.dry_run)
