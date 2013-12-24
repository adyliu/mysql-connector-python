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

"""Module containing distutils commands for commercial packaging"""


import sys
import os
from datetime import date
from distutils import log
from distutils.errors import DistutilsError
from distutils.sysconfig import get_python_version

GPL_NOTICE_LINENR = 19

COMMERCIAL_LICENSE_NOTICE = """
This is a release of MySQL Connector/Python, Oracle's dual-
license Python Driver for MySQL. For the avoidance of
doubt, this particular copy of the software is released
under a commercial license and the GNU General Public
License does not apply. MySQL Connector/Python is brought
to you by Oracle.

Copyright (c) 2011, 2013, Oracle and/or its affiliates. All rights reserved.

This distribution may include materials developed by third
parties. For license and attribution notices for these
materials, please refer to the documentation that accompanies
this distribution (see the "Licenses for Third-Party Components"
appendix) or view the online documentation at 
<http://dev.mysql.com/doc/>
"""

COMMERCIAL_SETUP_PY = """#!/usr/bin/env python
# -*- coding: utf-8 -*-
# MySQL Connector/Python - MySQL driver written in Python.
# Copyright (c) 2012, %d, Oracle and/or its affiliates. All rights reserved.

import os
from distutils.core import setup
from distutils.command.build import build
from distutils.dir_util import copy_tree

class Build(build):
    def run(self):
        copy_tree('mysql', os.path.join(self.build_lib, 'mysql'))

LONG_DESCRIPTION = \"\"\"
{long_description}
\"\"\"

setup(
    name = '{name}',
    version = '{version}',
    description = '{description}',
    long_description = LONG_DESCRIPTION,
    author = '{author}',
    author_email = '{author_email}',
    license = '{license}',
    keywords = '{keywords}',
    url = '{url}',
    download_url = '{download_url}',
    package_dir = {{ '': '' }},
    packages = ['mysql', 'mysql.connector',
       'mysql.connector.locales', 'mysql.connector.locales.eng'],
    classifiers = {classifiers},
    cmdclass = {{
        'build': Build,
    }}
)

""" % (date.today().year)

def remove_gpl(pyfile, dry_run=0):
    """Remove the GPL license form a Python source file

    Raise DistutilsError when a problem is found.
    """
    start = "terms of the GPLv2"
    end = "MA 02110-1301 USA"

    log.info("removing GPL license from %s" % pyfile)

    result = []
    removed = 0
    fp = open(pyfile, "r")
    line = fp.readline()
    have_gpl = False
    done = False
    while line:
        if line.strip().endswith(start) and not done:
            result.append("# Following empty comments"
                          " are intentional.\n")
            removed += 1
            line = fp.readline()
            while line:
                result.append("#\n")
                removed += 1
                line = fp.readline()
                if line.strip().endswith(end):
                    done = True
                    line = fp.readline()
                    result.append("# End empty comments.\n")
                    removed += 1
                    break
        result.append(line)
        line = fp.readline()
    fp.close()
    result.append("\n")

    if removed != GPL_NOTICE_LINENR:
        msg = ("Problem removing GPL license. Removed %d lines from "
               "file %s" % (removed, pyfile))
        raise DistutilsError(msg)

    if not dry_run:
        fp = open(pyfile, "w")
        fp.writelines(result)
        fp.close()


