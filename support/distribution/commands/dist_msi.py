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

"""Implements the Distutils command 'bdist_com_msi'

Implements the Distutils command 'bdist_com_msi' which creates a built
commercial distribution Windows Installer using Windows Installer XML 3.5.
The WiX file is available in the folder '/support/MSWindows/' of the
Connector/Python source.
"""

import sys
import os
import subprocess
import json
import re
from distutils import log
from distutils.errors import DistutilsError
from distutils.dir_util import remove_tree
from distutils.sysconfig import get_python_version
from distutils.command.bdist_dumb import bdist_dumb
from distutils.command.install_data import install_data
from distutils.command.bdist import bdist

from support.distribution.utils import get_magic_tag
from support.distribution import wix
from support.distribution.commands import COMMON_USER_OPTIONS
from version import EDITION

WIX_INSTALL = r"C:\Program Files (x86)\Windows Installer XML v3.5"


class _MSIDist(bdist):
    """"Create a MSI distribution"""
    def _get_wixobj_name(self, myc_version=None, python_version=None):
        """Get the name for the wixobj-file

        Returns a string
        """
        raise NotImplemented

    def _create_msi(self, dry_run=0):
        """Create the Windows Installer using WiX
        
        Creates the Windows Installer using WiX and returns the name of
        the created MSI file.
        
        Raises DistutilsError on errors.
        
        Returns a string
        """
        # load the upgrade codes
        fp = open('support/MSWindows/upgrade_codes.json')
        upgrade_codes = json.load(fp)
        fp.close()
        
        # version variables for Connector/Python and Python
        mycver = self.distribution.metadata.version
        match = re.match("(\d+)\.(\d+).(\d+).*", mycver)
        if not match:
            raise ValueError("Failed parsing version from %s" % mycver)
        (major, minor, patch) = match.groups()
        pyver = self.python_version
        pymajor = pyver[0]
        
        # check whether we have an upgrade code
        try:
            upgrade_code = upgrade_codes[mycver[0:3]][pyver]
        except KeyError:
            raise DistutilsError("No upgrade code found for version v%s, "
                                 "Python v%s" % mycver, pyver)
        log.info("upgrade code for v%s, Python v%s: %s" % (
                 mycver, pyver, upgrade_code))
        
        # wixobj's basename is the name of the installer
        wixobj = self._get_wixobj_name()
        msi = os.path.abspath(
            os.path.join(self.dist_dir, wixobj.replace('.wixobj', '.msi')))
        wixer = wix.WiX(self.wxs,
                        out=wixobj,
                        msi_out=msi,
                        base_path=self.build_base,
                        install=self.wix_install)

        # correct newlines in text files
        for txtfile in self.fix_txtfiles:
            builttxt = os.path.join(self.build_base, txtfile)
            open(builttxt, 'w').write(open(builttxt).read())
        
        # WiX preprocessor variables
        params = {
            'Version': '.'.join([major, minor, patch]),
            'FullVersion': mycver,
            'PythonVersion': pyver,
            'PythonMajor': pymajor,
            'Major_Version': major,
            'Minor_Version': minor,
            'Patch_Version': patch,
            'PythonInstallDir': 'Python%s' % pyver.replace('.', ''),
            'BDist': os.path.abspath(self.dist_target),
            'PyExt': 'pyc' if not self.include_sources else 'py', 
            'UpgradeCode': upgrade_code,
            'ManualPDF': os.path.abspath(os.path.join('docs', 'mysql-connector-python.pdf')),
            'ManualHTML': os.path.abspath(os.path.join('docs', 'mysql-connector-python.html')),
            'MagicTag': get_magic_tag()
        }
        
        wixer.set_parameters(params)
        
        if not dry_run:
            try:
                wixer.compile()
                wixer.link()
            except DistutilsError:
                raise

        if not self.keep_temp and not dry_run:
            log.info('WiX: cleaning up')
            os.unlink(msi.replace('.msi', '.wixpdb'))
        
        return msi

    def _prepare_distribution(self):
        raise NotImplemented

    def run(self):
        """Run the distutils command"""
        # build command: just to get the build_base
        cmdbuild = self.get_finalized_command("build")
        self.build_base = cmdbuild.build_base
        
        # Some checks
        if os.name != 'nt':
            log.info("This command is only useful on Windows. "
                     "Forcing dry run.")
            self.dry_run = True
        wix.check_wix_install(wix_install_path=self.wix_install,
                              dry_run=self.dry_run)
        
        self._prepare_distribution()
        
        # create the Windows Installer
        msi_file = self._create_msi(dry_run=self.dry_run)
        log.info("created MSI as %s" % msi_file)
        
        if not self.keep_temp:
            remove_tree(self.build_base, dry_run=self.dry_run)

class BuiltCommercialMSI(_MSIDist):
    """Create a Built Commercial MSI distribution"""
    description = 'create a commercial built MSI distribution'
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
        ('wix-install', None,
         "location of the Windows Installer XML installation"
         "(default: %s)" % WIX_INSTALL),
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
        self.wix_install = WIX_INSTALL
        self.python_version = get_python_version()
        self.edition = EDITION
    
    def finalize_options(self):
        """Finalize the options"""
        self.set_undefined_options('bdist',
                                   ('dist_dir', 'dist_dir'))

        self.wxs = 'support/MSWindows/product_com.wxs'
        self.fix_txtfiles = ['README.txt', 'LICENSE.txt']

    def _get_wixobj_name(self, myc_version=None, python_version=None):
        """Get the name for the wixobj-file

        Return string
        """
        mycver = myc_version or self.distribution.metadata.version
        pyver = python_version or self.python_version
        return ("mysql-connector-python-commercial-"
                "{conver}{edition}-py{pyver}.wixobj").format(
                    conver=mycver,
                    pyver=pyver,
                    edition=self.edition
                )

    def _prepare_distribution(self):
        """Prepare the distribution"""
        cmdbdist = self.get_finalized_command("bdist_com")
        cmdbdist.dry_run = self.dry_run
        cmdbdist.dist_dir = self.build_base
        cmdbdist.keep_temp = True
        self.run_command("bdist_com")
        self.dist_target = cmdbdist.dist_target

class SourceMSI(_MSIDist):
    """Create a Source MSI distribution"""
    description = 'create a source MSI distribution'
    user_options = [
        ('bdist-dir=', 'd',
         "temporary directory for creating the distribution"),
        ('keep-temp', 'k',
         "keep the pseudo-installation tree around after " +
         "creating the distribution archive"),
        ('dist-dir=', 'd',
         "directory to put final built distributions in"),
        ('wix-install', None,
         "location of the Windows Installer XML installation"
         "(default: %s)" % WIX_INSTALL),
        ('python-version=', None,
         "target Python version"),
    ] + COMMON_USER_OPTIONS

    boolean_options = [
        'keep-temp',
    ]
    
    def initialize_options (self):
        """Initialize the options"""
        self.bdist_dir = None
        self.keep_temp = 0
        self.dist_dir = None
        self.include_sources = True
        self.wix_install = WIX_INSTALL
        self.python_version = get_python_version()[:3]
        self.edition = EDITION
    
    def finalize_options(self):
        """Finalize the options"""
        self.set_undefined_options('bdist',
                                   ('dist_dir', 'dist_dir'))

        self.wxs = 'support/MSWindows/product.wxs'
        self.fix_txtfiles = ['README.txt', 'COPYING.txt']

        supported = ['2.6', '2.7', '3.1', '3.2', '3.3']
        if self.python_version not in supported:
            raise DistutilsOptionError(
                "The --target-python should be a supported version, one "
                "of %s" % ','.join(supported))

        if self.python_version[0] != get_python_version()[0]:
            raise DistutilsError(
                "Python v3 distributions need to be build with a "
                "supported Python v3 installation.")

    def _get_wixobj_name(self, myc_version=None, python_version=None):
        """Get the name for the wixobj-file

        Return string
        """
        mycver = myc_version or self.distribution.metadata.version
        pyver = python_version or self.python_version
        return ("mysql-connector-python-"
                "{conver}{edition}-py{pyver}.wixobj").format(
                    conver=mycver,
                    pyver=pyver,
                    edition=self.edition
                )

    def _prepare_distribution(self):
        """Prepare the distrubtion"""
        cmd = self.get_finalized_command("sdist_gpl")
        cmd.dry_run = self.dry_run
        cmd.dist_dir = self.build_base
        cmd.keep_temp = True
        self.run_command("sdist_gpl")
        self.dist_target = cmd.dist_target

