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

"""Miscellaneous utility functions"""

import os
import gzip
import tarfile

from distutils.sysconfig import get_python_version

def get_dist_name(distribution, source_only_dist=False, platname=None,
                  python_version=None, commercial=False, edition=''):
    """Get the distribution name
    
    Get the distribution name usually used for creating the egg file. The
    Python version is excluded from the name when source_only_dist is True.
    The platname will be added when it is given at the end.
    
    Returns a string.
    """
    name = distribution.metadata.name
    if edition:
        name += edition
    if commercial:
        name += '-commercial'
    name += '-' + distribution.metadata.version
    if not source_only_dist or python_version:
        pyver = python_version or get_python_version()
        name += '-py' + pyver
    if platname:
        name += '-' + platname
    return name

def get_magic_tag():
    try:
        # For Python Version >= 3.2
        from imp import get_tag
        return get_tag()
    except ImportError:
        return ''

def unarchive_targz(tarball):
    """Unarchive a tarball

    Unarchives the given tarball. If the tarball has the extension
    '.gz', it will be first uncompressed.

    Returns the path to the folder of the first unarchived member.

    Returns str.
    """
    orig_wd = os.getcwd()

    (dstdir, tarball_name) = os.path.split(tarball)
    if dstdir:
        os.chdir(dstdir)

    if '.gz' in tarball_name:
        new_file = tarball_name.replace('.gz', '')
        gz = gzip.GzipFile(tarball_name)
        tar = open(new_file, 'wb')
        tar.write(gz.read())
        tar.close()
        tarball_name = new_file

    tar = tarfile.TarFile(tarball_name)
    tar.extractall()

    os.unlink(tarball_name)
    os.chdir(orig_wd)

    return os.path.abspath(os.path.join(dstdir, tar.getmembers()[0].name))
