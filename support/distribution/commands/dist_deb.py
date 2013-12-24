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

"""Implements the Distutils commands creating Debian packages
"""

import os
import subprocess
import platform
import re

from distutils.core import Command
from distutils.file_util import copy_file, move_file
from distutils.dir_util import remove_tree
from distutils import log

from support.distribution.utils import unarchive_targz
from support.distribution.commands import COMMON_USER_OPTIONS
from version import EDITION

DPKG_MAKER = 'dpkg-buildpackage'


class DebianBuiltDist(Command):
    description = 'create a source distribution Debian package'
    debian_files = [
        'control',
        'changelog',
        'copyright',
        'docs',
        'postinst',
        'postrm',
        'compat',
        'rules',
    ]

    try:
        linux_dist = platform.linux_distribution()[0]
    except AttributeError:
        # Python v2.5 and ealier
        linux_dist = platform.dist()[0] 

    user_options = [
        ('keep-temp', 'k',
         "keep the pseudo-installation tree around after "
         "creating the distribution archive"),
        ('debug', None,
         "turn debugging on"),
        ('dist-dir=', 'd',
         "directory to put final source distributions in"),
        ('platform=', 'p',
         "name of the platform in resulting files "
         "(default '%s')" % linux_dist.lower()),
        ('sign', None,
         "sign the Debian package"),
    ] + COMMON_USER_OPTIONS

    def initialize_options(self):
        """Initialize the options"""
        self.keep_temp = False
        self.debug = False
        self.dist_dir = None
        self.platform = platform.linux_distribution()[0].lower()
        self.platform_version = '.'.join(
            platform.linux_distribution()[1].split('.', 2)[0:2])
        self.sign = False
        self.debian_support_dir = 'support/Debian/gpl'
        self.edition = EDITION

    def finalize_options(self):
        """Finalize the options"""

        cmdbuild = self.get_finalized_command("build")
        self.build_base = cmdbuild.build_base

        if not self.dist_dir:
            self.dist_dir = 'dist'

        if self.sign:
            self.sign = True

    def _get_orig_name(self):
        """Returns name for tarball according to Debian's policies
        """
        return "%(name)s_%(version)s.orig" % {
            'name': self.distribution.get_name(),
            'version': self.distribution.get_version(),
            }

    @property
    def _have_python3(self):
        """Check whether this distribution has Python 3 support
        """
        try:
            devnull = open(os.devnull, 'w')
            subprocess.Popen(['py3versions'],
                stdin=devnull, stdout=devnull, stderr=devnull)
        except OSError:
            return False

        return True

    def _populate_debian(self):
        """Copy and make files ready in the debian/ folder
        """
        for afile in self.debian_files:
            copy_file(os.path.join(self.debian_support_dir, afile),
                      self.debian_base)

        copy_file(os.path.join(self.debian_support_dir, 'source', 'format'),
                  os.path.join(self.debian_base, 'source'))

        # This code is for now disabled. It allows to make distribution
        # specific Debian packages, but we seem not to need this for now.
        if False:
            changelog_file = os.path.join(self.debian_base, 'changelog')
            changelog = open(changelog_file, 'r').readlines()
            log.info(
                "changing changelog '%s' to include platform" % changelog_file)
            newchangelog = []
            regex = re.compile(r'.*\((\d+\.\d+.\d+)\).*')
            for line in changelog:
                line = line.rstrip()
                match = regex.match(line)
                if match:
                    version = match.groups()[0]
                    line = line.replace(
                        version,
                        '%s-%s%s' % (version,
                       self.platform, self.platform_version)
                        )
                newchangelog.append(line)
            newchangelog.append('\n')
            changelog = open(changelog_file, 'w')
            changelog.write('\n'.join(newchangelog))

    def _prepare(self, tarball=None, base=None):
        dist_dirname = self.distribution.get_fullname()

        # Rename tarball to conform Debian's Policy
        if tarball:
            self.orig_tarball = os.path.join(
                os.path.dirname(tarball),
                self._get_orig_name()) + '.tar.gz'
            move_file(tarball, self.orig_tarball)

            untared_dir = unarchive_targz(self.orig_tarball)
            self.debian_base = os.path.join(
                tarball.replace('.tar.gz', ''), 'debian')
        elif base:
            self.debian_base = os.path.join(base, 'debian')

        self.mkpath(self.debian_base)
        self.mkpath(os.path.join(self.debian_base, 'source'))

        self._populate_debian()

    def _make_dpkg(self):
        """Create Debian package in the source distribution folder
        """
        log.info("creating Debian package using '%s'" % DPKG_MAKER)

        orig_wd = os.getcwd()
        os.chdir(os.path.join(self.build_base,
                 self.distribution.get_fullname()))
        cmd = [
            DPKG_MAKER,
            '-uc',
            ]

        if not self.sign:
            cmd.append('-us')

        success = True
        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True)
        stdout = proc.stdout.read()
        stderr = proc.stderr.read()
        for line in stdout.split('\n'):
            if self.debug:
                log.info(line)
            if 'error:' in line or 'E: ' in line:
                if not self.debug:
                    log.info(line)
                success = False

        if stderr:
            for line in stderr.split('\n'):
                if self.debug:
                    log.info(line)
                if 'error:' in line or 'E: ' in line:
                    if not self.debug:
                        log.info(line)
                    success = False

        os.chdir(orig_wd)
        return success

    def _move_to_dist(self):
        """Move *.deb files to dist/ (dist_dir) folder"""
        for base, dirs, files in os.walk(self.build_base):
            for filename in files:
                if '-py3' in filename and not self._have_python3:
                    continue
                if filename.endswith('.deb'):
                    newname = filename.replace(
                        '-1_',
                        '{edition}-1{platform}{version}_'.format(
                            platform=self.platform,
                            version=self.platform_version,
                            edition=self.edition or '',
                        )
                    )
                    filepath = os.path.join(base, filename)
                    copy_file(filepath, self.dist_dir)
                    move_file(os.path.join(self.dist_dir, filename),
                              os.path.join(self.dist_dir, newname))

    def run(self):
        """Run the distutils command"""
        self.mkpath(self.dist_dir)

        sdist = self.reinitialize_command('sdist')
        sdist.dist_dir = self.build_base
        sdist.formats = ['gztar']
        sdist.ensure_finalized()
        sdist.run()

        self._prepare(sdist.archive_files[0])
        success = self._make_dpkg()

        if not success:
            log.error("Building Debian package failed.")
        else:
            self._move_to_dist()

        if not self.keep_temp:
            remove_tree(self.build_base, dry_run=self.dry_run)


class DebianCommercialBuilt(DebianBuiltDist):
    description = 'create a commercial built distribution Debian package'


    def finalize_options(self):
        def _get_fullname():
            return "%s-commercial-%s" % (
                self.distribution.get_name(), self.distribution.get_version())

        self.distribution.get_fullname = _get_fullname
        self.debian_support_dir = 'support/Debian/commercial'
        DebianBuiltDist.finalize_options(self)

    def _get_orig_name(self):
        """Returns name for tarball according to Debian's policies
        """
        return "%(name)s-commercial_%(version)s.orig" % {
            'name': self.distribution.get_name(),
            'version': self.distribution.get_version(),
            }

    def run(self):
        self.mkpath(self.dist_dir)

        sdist = self.get_finalized_command('sdist_com')
        sdist.dist_dir = self.build_base
        sdist.formats = ['gztar']
        sdist.edition = self.edition
        self.run_command('sdist_com')

        self._prepare(sdist.archive_files[0])
        success = self._make_dpkg()

        if not success:
            log.error("Building Debian package failed.")
        else:
            self._move_to_dist()

        if not self.keep_temp:
            remove_tree(self.build_base, dry_run=self.dry_run)

