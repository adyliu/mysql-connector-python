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

from distutils.sysconfig import get_python_lib

from distutils.file_util import copy_file
from distutils.dir_util import mkpath, copy_tree
from distutils.errors import DistutilsError
from distutils import util

from version import VERSION, LICENSE

if LICENSE == 'Commercial':
    util.orig_byte_compile = util.byte_compile

def _byte_compile(py_files, optimize=0, force=0, prefix=None, base_dir=None,
                verbose=1, dry_run=0, direct=None):
    """Byte-compile Python source files

    This function calls the original distutils.util.byte_compile function and
    it removes the original Python source files.

    This function is only to be used for non GPLv2 sources.
    """
    util.orig_byte_compile(py_files, optimize, force, prefix, base_dir,
                      verbose, dry_run, direct)

    for pyfile in py_files:
        if 'mysql/__init__.py' in pyfile:
            continue
        os.unlink(pyfile)

if LICENSE == 'Commercial':
    util.byte_compile = _byte_compile

# Development Status Trove Classifiers significant for Connector/Python
DEVELOPMENT_STATUSES = {
    'a': '3 - Alpha',
    'b': '4 - Beta',
    '': '5 - Production/Stable'
}

if sys.version_info >= (3, 1):
    sys.path = ['python3/'] + sys.path
    package_dir = { '': 'python3' }
elif sys.version_info >= (2, 6) and sys.version_info < (3, 0):
    sys.path = ['python2/'] + sys.path
    package_dir = { '': 'python2' }
else:
    raise RuntimeError(
        "Python v%d.%d is not supported" % sys.version_info[0:2])

package_dir['mysql.connector.django'] = os.path.join('python23', 'django')

name = 'mysql-connector-python'
version = '{0}.{1}.{2}'.format(*VERSION[0:3])

try:
    from support.distribution.commands import (
        sdist, bdist, dist_rpm, build, dist_deb
        )

    from distutils import dir_util
    dir_util.copy_tree = copy_tree 

    cmdclasses = {
        'build': build.Build,
        'sdist': sdist.GenericSourceGPL,
        'sdist_gpl': sdist.SourceGPL,
        'bdist_com': bdist.BuiltCommercial,
        'bdist_com_rpm': dist_rpm.BuiltCommercialRPM,
        'sdist_gpl_rpm': dist_rpm.SDistGPLRPM,
        'sdist_com': sdist.SourceCommercial,
        'sdist_gpl_deb': dist_deb.DebianBuiltDist,
        'bdist_com_deb': dist_deb.DebianCommercialBuilt,
    }

    if sys.version_info >= (2, 7):
        # MSI only supported for Python 2.7 and greater
        from support.distribution.commands import (dist_msi)
        cmdclasses.update({
            'bdist_com': bdist.BuiltCommercial,
            'bdist_com_msi': dist_msi.BuiltCommercialMSI,
            'sdist_gpl_msi': dist_msi.SourceMSI,
            })

except ImportError:
    # Part of Source Distribution
    cmdclasses = {}

packages = [
    'mysql',
    'mysql.connector', 
    'mysql.connector.locales',
    'mysql.connector.locales.eng',
    'mysql.connector.django',
    ]
description = "MySQL driver written in Python"
long_description = """\
MySQL driver written in Python which does not depend on MySQL C client
libraries and implements the DB API v2.0 specification (PEP-249).
"""
author = 'Oracle and/or its affiliates'
author_email = ''
maintainer = 'Geert Vanderkelen'
maintainer_email = 'geert.vanderkelen@oracle.com'
license = "GNU GPLv2 (with FOSS License Exception)"
keywords = "mysql db",
url = 'http://dev.mysql.com/doc/connector-python/en/index.html'
download_url = 'http://dev.mysql.com/downloads/connector/python/'
classifiers = [
    'Development Status :: %s' % (DEVELOPMENT_STATUSES[VERSION[3]]),
    'Environment :: Other Environment',
    'Intended Audience :: Developers',
    'Intended Audience :: Education',
    'Intended Audience :: Information Technology',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: GNU General Public License (GPL)',
    'Operating System :: OS Independent',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.1',
    'Programming Language :: Python :: 3.2',
    'Programming Language :: Python :: 3.3',
    'Topic :: Database',
    'Topic :: Software Development',
    'Topic :: Software Development :: Libraries :: Application Frameworks',
    'Topic :: Software Development :: Libraries :: Python Modules'
]

