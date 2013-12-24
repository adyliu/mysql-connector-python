#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

"""Parse client and server errors from the MySQL Sources

This module parses MySQL client and server errors from the MySQL sources.
It used to keep the mysql.connector.errorcode module up-to-date.

Important:
* The minimum MySQL version has to be updated in this script to the latest
  development MySQL Server. The script will check when the latest update
  was done and give an error when it is older than MYSQL_RELEASE_MAXAGE days.
  See the MIN_MYSQL_VERSION variable in the script.
* This script only works with Python v2.7 and Python v3.2 (or later).
"""


from __future__ import print_function
import sys

# We only support Python v2.7 or later, and v3.2 or later.
if sys.version_info[0] == 2:
    if sys.version_info[:2] < (2, 7):
        print("This script requires Python v2.7 or later")
        exit(3)
elif sys.version_info[0] == 3:
    if sys.version_info[:2] < (3, 2):
        print("This script requires Python v3.2 or later")
        exit(3)

import os
import re
import codecs
import datetime
from collections import OrderedDict
import logging
import argparse
from pprint import pprint, pformat

sys.path = ['.'] + sys.path
from support.distribution import opensource

# Minimum MySQL version we need. This should be the latest version of the
# one after the greatest GA. For example, MySQL 5.5 is GA, but 5.6 is still
# Development, then the minimum version should be the latest of 5.6.
# Set the MYSQL_RELEASED to the date when MIN_MYSQL_VERSION was released.
MIN_MYSQL_VERSION = (5, 7, 2)
MYSQL_RELEASED = datetime.date(2013, 9, 21)
MYSQL_RELEASE_MAXAGE = 120 # days

# File to parse relative to the MySQL source
ERR_SERVER_FILE = os.path.join("sql", "share", "errmsg-utf8.txt")
ERR_CLIENT_HEADER = os.path.join("include", "errmsg.h")
ERR_CLIENT_CFILE = os.path.join("libmysql", "errmsg.c")

# Name of the module which will contain the error codes and messages
ERRCODE_MODULE = 'errorcode.py'
ERRLOCALE_SERVER = 'errors_server.py'
ERRLOCALE_CLIENT = 'errors_client.py'

_ERROR_SERVER = 1
_ERROR_CLIENT = 2


class _ParseError(Exception):
    pass


class MySQLErrorsProcessor(object):
    """Parse and write MySQL client and server error messages"""
    def __init__(self, source_path, mysql_version, output_folder):
        self._source_path = source_path
        self._output_folder = output_folder
        self._mysql_version = mysql_version
        self._mysql_version_str = '{:d}.{:d}.{:d}'.format(*mysql_version)
        self._languages = []
        self._errors = OrderedDict()
        self._init_server_errors()
        self._init_client_errors()
        self._lang_count = {}

        self._parse_server_errors()
        self._parse_client_errors()

    def _init_server_errors(self):
        """Initialize the server error parser"""
        txt_file = os.path.join(self._source_path, ERR_SERVER_FILE)
        if not os.path.isfile(txt_file):
            _ParseError("Could not find error messages file under {}".format(
                args.source))

        logging.debug('Parsing server errors from file {}'.format(txt_file))
        self._server_errmsg_file = txt_file
        self._errors_info = {}

    def _init_client_errors(self):
        """Initialize the client error parser"""
        header_file = os.path.join(self._source_path, ERR_CLIENT_HEADER)
        if not os.path.isfile(header_file):
            _ParseError("Could not find error messages file under {}".format(
                args.source))
        
        c_file = os.path.join(self._source_path, ERR_CLIENT_CFILE)
        if not os.path.isfile(c_file):
            _ParseError("Could not find error messages source under {}".format(
                args.source))

        logging.debug('Parsing client errors from file {}'.format(header_file))
        self._client_errmsg_header = header_file
        self._client_errmsg_cfile = c_file

    def _parse_server_errors(self):
        """Parse server error codes"""
        fp = codecs.open(self._server_errmsg_file, 'r', 'utf8')
        curr_err_name = None
        line_nr = 1
        curr_code = 1000 # will be set reading 'start-error-number'
        self._regex_serverr_msg = None
        for line in fp:
            if line.startswith('#'):
                continue
            elif line.startswith('start-error-number'):
                self._errors_info['offset'] = \
                    self._serverr_error_offset(line)
                curr_code = self._errors_info['offset']
            elif line.startswith(('\t',' ')):
                if not self._regex_serverr_msg:
                    self._regex_serverr_msg = re.compile(r'([\w-]*)\s+"(.*?)"')
                try:
                    lang, msg = self._serverr_message(line)
                except ValueError:
                    raise ValueError("Found problem in line nr %d" % line_nr)
                self._lang_count[lang] = self._lang_count.get(lang, 0) + 1
                self._errors[curr_err_name]['messages'][lang] = msg
                if lang not in self._languages:
                    self._languages.append(lang)
                if lang == '':
                    logging.debug("Empty lang: {}".format(line))
            elif line.startswith(('ER_', 'WARN_')):
                res = self._serverr_string(line)
                curr_err_name = res[0]
                if curr_err_name not in self._errors:
                    self._errors[curr_err_name] = {
                        'sqlcodes': res[1:],
                        'messages': {},
                        'code': curr_code,
                        'type': _ERROR_SERVER,
                        }
                    curr_code += 1
            line_nr += 1
        logging.debug(
            "MySQL v{version} server error messages read, "\
            "last was {last}.".format(
                version=self._mysql_version_str,
                last=curr_code))

        self._regex_serverr_msg = None
        fp.close()

    def get_error_by_number(self, nr):
        """Get information about an error by it's number

        Returns a string and dictionary.
        """
        for errname, err in self._errors.items():
            if err['code'] == nr:
                return errname, err
        return None

    def _parse_client_error_messages(self):
        """Parse client error messages"""
        lang = 'eng'
        fp = codecs.open(self._client_errmsg_cfile)
        with codecs.open(self._client_errmsg_cfile, 'r', 'latin1') as fp:
            found = False
            nr = 2000
            for line in fp:
                line = line.strip()
                if not found:
                    if line == "const char *client_errors[]=":
                        found = True
                    continue
                
                if line.startswith('"') and line != '""':
                    err_name, err = self.get_error_by_number(nr)
                    message = line.replace('"', '').rstrip(',')
                    self._errors[err_name]['messages'][lang] = message
                    self._lang_count[lang] = self._lang_count.get(lang, 0) + 1
                    nr += 1

    def _parse_client_errors(self):
        """Parse client error codes"""
        fp = codecs.open(self._client_errmsg_header, 'r', 'utf8')

        ignored = (
            '#define CR_MIN_ERROR',
            '#define CR_MAX_ERROR',
            '#define CR_ERROR_FIRST',
            '#define CR_ERROR_LAST'
            )

        err_code = None
        for line in fp:
            if line.startswith(ignored):
                continue
            if line.startswith('#define CR_'):
                err_name, err_code = line.split()[1:3]
                self._errors[err_name] = {
                    'messages': {},
                    'code': int(err_code),
                    'type': _ERROR_CLIENT,
                    }
        logging.debug("Last client error code was {}".format(err_code))

        fp.close()

        self._parse_client_error_messages()

    def _serverr_string(self, line):
        """Parse server error from given line

        This method parsers the given line and returns a tuple containing
        the error code and, if available, also the SQL State information.

        Example line:
            ER_ACCESS_DENIED_ERROR 28000

        Returns a tuple.
        """
        try:
            return line.strip().split()
        except ValueError:
            return (line.strip())

    def _serverr_error_offset(self, line):
        """Parse the offset from which server errors begin

        This method parsers the server error offset and returns it as an
        integer. The value of the offset is most probably 1000.

        Line is usually as follows:
            start-error-number 1000

        """
        errno = int(line.strip().split()[1])
        logging.debug("Server error offset: {:d}".format(errno))
        return errno
    
    def _serverr_message(self, line):
        """Parse the error message

        This method parses the language and message from the given line and
        returns it as a tuple: (language, message). Values in the tuple are
        unicode.

        Returns a tuple.
        """
        matches = self._regex_serverr_msg.search(line)
        if matches:
            return matches.groups()
        else:
            raise ValueError("Failed reading server error message")
    
    def _serverr_get_translations(self):
        """Create a dictionary of server codes with translations

        This method will return a dictionary where the key is the server
        error code and value another dictionary containing the error message
        in all available languages.

        Example output:
            { 1003: {
                'eng': "NO",
                'ger': "Nein",
                'kor': "아니오"',
                ...
                }
            }

        String values are unicode.

        Returns a dictionary.
        """
        result = {}
        for err_name, err in self._errors.items():
            result[err['code']] = err['messages']
        return result

    def _write_header(self, fp):
        fp.write("# -*- coding: utf-8 -*-\n\n")

        license = opensource.GPLGNU2_LICENSE_NOTICE.format(
            year=datetime.datetime.now().year)
        linenr = 0
        for licline in license.split('\n'):
            linenr += 1
            if linenr == 3 and licline == "":
                fp.write("\n".format(licline))
                continue
            fp.write("# {}\n".format(licline))
        fp.write("\n# This file was auto-generated.\n")

        fp.write("_GENERATED_ON = '{}'\n".format(
            datetime.datetime.now().date()))
        fp.write("_MYSQL_VERSION = ({:d}, {:d}, {:d})\n\n".format(
            *self._mysql_version))

    def write_module(self, output_folder=None):
        output_folder = output_folder or self._output_folder

        errcode_module = os.path.join(output_folder, ERRCODE_MODULE)
        logging.debug("Writing error codes to '{}', MySQL v{}".format(
                      errcode_module, self._mysql_version_str))

        fp = codecs.open(errcode_module, 'w', 'utf8')
        self._write_header(fp)

        fp.write("\"\"\"This module contains the MySQL Server "
            "and Client error codes\"\"\"\n\n")

        fp.write("# Start MySQL Errors\n")
        for err_name, err in self._errors.items():
            fp.write('{0} = {1}\n'.format(err_name, err['code']))
        
        fp.write("# End MySQL Errors\n\n")

        fp.close()

    def _setup_locales_folder(self, output_folder, language='all'):
        """Setup the folder for storing translations

        This method will setup the folder storing translations using the
        languages found while parsing error messages.

        The folder (package) structure will be as follows:
            <output_folder>/
                locales/
                    __init__.py
                    <language>/
                        __init__.py

        Returns a string.
        """
        if language == 'all':
            languages = self._languages
        else:
            languages = [ language ]

        def create(folder):
            if not os.path.exists(folder):
                os.mkdir(folder)
            init_file = os.path.join(folder, '__init__.py')
            if not os.path.isfile(init_file):
                open(init_file, 'w').close()

        locale_folder = os.path.join(self._output_folder, 'locales')
        create(locale_folder)

        for lang in languages:
            lang_folder = os.path.join(locale_folder,
                                       lang.replace('-','_'))
            create(lang_folder)

        return locale_folder

    def _write_error_messages(self, language, locale_folder,
                              module_name, errtype=None):
        """Write the error messages to a Python module

        This method will write error messages for a certain language into a
        python module locate in the locale_folder. If the errtype is
        given, it will only write message corresponding to a certain error
        type.
        """
        modfile = os.path.join(locale_folder, language.replace('-','_'),
                               module_name)

        logging.debug("Writing error module for {}, ".format(
            modfile, self._mysql_version_str))
        fp = codecs.open(modfile, 'w', 'utf8')
        self._write_header(fp)

        fp.write("# Start MySQL Error messages\n")
        for err_name, err in self._errors.items():
            if errtype and err['type'] != errtype:
                continue

            try:
                err_msg = err['messages'][language]
            except KeyError:
                # No translation available
                continue

            err_msg = err_msg.replace('%d', '%s')
            err_msg = err_msg.replace('%lu', '%s')

            if sys.version_info[0] == 2:
                fp.write(unicode('{code} = u"{msg}"\n').format(
                    code=err_name, msg=err_msg))
            else:
                fp.write('{code} = "{msg}"\n'.format(
                    code=err_name, msg=err_msg))

        fp.write("# End MySQL Error messages\n\n")
        fp.close()

    def write_locale_errors(self, language='all', output_folder=None):
        """Write the MySQL server error translations to Python module

        This method will write the MySQL server error translations to a
        Python module. If output_folder is given, it will create (or overwrite)
        the module in the given directory. If not given, a subfolder will
        be used (and if needed created) in the Connector/Python source.
        """
        output_folder = output_folder or self._output_folder
        locale_folder = self._setup_locales_folder(output_folder, language)

        if language == 'all':
            languages = self._languages
        else:
            languages = [ language ]

        for lang in languages:
            self._write_error_messages(lang, locale_folder,
                                       'client_error.py', _ERROR_CLIENT)
            #self._write_error_messages(lang, locale_folder,
            #                           'server_error.py', _ERROR_SERVER,)


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Parse MySQL error messages from the MySQL source")

    parser.add_argument(
        'source',
        help="Location of the latest released MySQL sources.")
    parser.add_argument(
        '--debug', action='store_true', dest='debug',
        help="Show debug messages")
    parser.add_argument(
        '--output', metavar="DIR",
        help="Where to write the modules (used for debugging)")
    parser.add_argument(
        '--language', metavar="LANG", default='eng',
        help="Which language to parse and write. Use 'all' for all languages.")

    return parser


def read_version(source):
    """Reads the MySQL version from the source

    This function reads the MySQL version from the source and returns it as
    as tuple: (MAJOR, MINOR, PATCH).

    Returns a tuple.
    """
    fn = os.path.join(source, 'VERSION')
    with open(fn, 'r') as fp:
        lines = fp.readlines()
        version = [int(l.split('=')[1]) for l in lines[0:3]]
    return tuple(version)


def check_execution_location():
    """Check whether this script is exeucted in the correct location

    This function checks wether the script is executed in the correct
    location. This script has to be executed from the root of the
    Connector/Python source.
    """
    cwd = os.getcwd()
    checks = [
        os.path.join(cwd, 'python2'),
        os.path.join(cwd, 'python3'),
        ]
    for location in checks:
        if not os.path.exists(location):
            raise RuntimeError


def get_output_folder():
    """Returns the output folder according to Python's major version"""
    if sys.version_info[0] == 2:
        return os.path.join('python2','mysql','connector')
    elif sys.version_info[0] == 3:
        return os.path.join('python3','mysql','connector')


def check_mysql_sources(source):
    """Check the given MySQL source location

    This function will check if the given MySQL source is usable. If not, it
    will raise a ValueError exception.
    """
    version = read_version(source)
    if version < MIN_MYSQL_VERSION:
        raise ValueError("MySQL v{:d}.{:d}.{:d} is too old".format(*version))

    checks = [
        os.path.join(source, ERR_SERVER_FILE),
        os.path.join(source, ERR_CLIENT_HEADER),
        os.path.join(source, ERR_CLIENT_CFILE),
        ]
    for location in checks:
        if not os.path.exists(location):
            raise ValueError("File '{}' not available".format(location))

    return version


def check_mysql_version_freshness(released=MYSQL_RELEASED):
    """Check whether the release date of minimum MySQL version is valid"""
    days = (datetime.datetime.now().date() - released).days
    logging.debug("Minimum MySQL version is {} days old.".format(days))
    if days > MYSQL_RELEASE_MAXAGE:
        raise ValueError("Minimum MySQL version is older than {} days".format(
            MYSQL_RELEASE_MAXAGE))


def main():
    """Start the script"""
    args = argument_parser().parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    try:
        check_mysql_version_freshness()
        check_execution_location()
    except RuntimeError:
        print("Execute this script from the root of Connector/Python source")
        exit(3)
    except ValueError as err:
        print("Update script: {}".format(err))
        exit(3)

    try:
        mysql_version = check_mysql_sources(args.source)
    except ValueError as err:
        print("The given MySQL source can not be used: {}".format(err))
        exit(3)
    logging.debug("Using MySQL v{ver} sources found in {loc}".format(
        ver="{:d}.{:d}.{:d}".format(*mysql_version), loc=args.source))

    output_folder = args.output or get_output_folder()
    logging.debug("Output folder: {}".format(output_folder))

    try:
        myerrmsgs = MySQLErrorsProcessor(
            args.source, mysql_version, output_folder)
    except _ParseError as err:
        print(err)
        exit(1)

    myerrmsgs.write_module()
    myerrmsgs.write_locale_errors(language=args.language)


if __name__ == '__main__':
    main()


