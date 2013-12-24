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

"""Implementing communication with MySQL Fabric"""

import sys
import time
import uuid
from base64 import b16decode
from bisect import bisect
from hashlib import md5
import logging
import socket

try:
    from xmlrpclib import Fault, ServerProxy
except ImportError:
    # Python v3
    from xmlrpc.client import Fault, ServerProxy  # pylint: disable=F0401

import mysql.connector
from mysql.connector.connection import DEFAULT_CONFIGURATION
from mysql.connector.errors import (
    Error, InterfaceError, NotSupportedError, MySQLFabricError, InternalError
    )
from mysql.connector.cursor import (MySQLCursor, MySQLCursorBuffered,
    MySQLCursorRaw, MySQLCursorBufferedRaw, MySQLCursorPrepared)
from mysql.connector import errorcode
from . import FabricMySQLServer, FabricShard
from .caching import FabricCache
from .balancing import WeightedRoundRobin

RESET_CACHE_ON_ERROR = (
    errorcode.CR_SERVER_LOST,
    errorcode.ER_OPTION_PREVENTS_STATEMENT,
    )


MYSQL_FABRIC_PORT = 8080

FABRICS = {}

# For attempting to connect with Fabric
_CNX_ATTEMPT_DELAY = 1
_CNX_ATTEMPT_MAX = 3

_GETCNX_ATTEMPT_DELAY = 1
_GETCNX_ATTEMPT_MAX = 3

_MONITOR_INTERVAL = 2

MODE_READONLY = 1
MODE_WRITEONLY = 2
MODE_READWRITE = 3

STATUS_FAULTY = 0
STATUS_SPARE = 1
STATUS_SECONDARY = 2
STATUS_PRIMARY = 3

SCOPE_GLOBAL = 'GLOBAL'
SCOPE_LOCAL = 'LOCAL'

_SERVER_STATUS_FAULTY = 'FAULTY'

_CNX_PROPERTIES = {
    # name: (valid_types, description, default)
    'group': (str, "Name of group of servers", None),
    'key': ((str, int), "Sharding key", None),
    'tables': ((tuple, list), "List of tables in query", None),
    'mode': (int, "Read-Only, Write-Only or Read-Write", None),
    'shard': (str, "Identity of the shard for direct connection", None),
    'mapping': (str, "", None),
    'scope': (str, "GLOBAL for accessing Global Group, or LOCAL", SCOPE_LOCAL),
    'attempts': (int, "Attempts for getting connection", 3),
    'attempt_delay': (int, "Seconds to wait between each attempt", 1),
    }

_LOGGER = logging.getLogger('myconnpy-fabric')


def _fabric_xmlrpc_uri(host, port):
    """Create an XMLRPC URI for connecting to Fabric

    This method will create a URI using the host and TCP/IP
    port suitable for connecting to a MySQL Fabric instance.

    Returns a URI.
    """
    return 'http://{host}:{port}'.format(host=host, port=port)


def _fabric_server_uuid(host, port):
    """Create a UUID using host and port"""
    return uuid.uuid3(uuid.NAMESPACE_URL, _fabric_xmlrpc_uri(host, port))


class Fabric(object):

    """Class managing MySQL Fabric instances"""

    def __init__(self, host, port=MYSQL_FABRIC_PORT,
                 connect_attempts=_CNX_ATTEMPT_MAX,
                 connect_delay=_CNX_ATTEMPT_DELAY):
        """Initialize"""
        self._fabric_instances = {}
        self._fabric_uuid = None
        self._ttl = 1 * 60  # one minute by default
        self._version_token = None
        self._connect_attempts = connect_attempts
        self._connect_delay = connect_delay
        self._cache = FabricCache()
        self._group_balancers = {}
        self._init_host = host
        self._init_port = port

    def seed(self, host=None, port=None):
        """Get MySQL Fabric Instances

        This method uses host and port to connect to a MySQL Fabric server
        and get all the instances managing the same metadata.

        Raises InterfaceError on errors.
        """
        host = host or self._init_host
        port = port or self._init_port

        fabinst = FabricConnection(self, host, port)
        fabinst.connect()
        fabric_uuid, version, ttl, fabrics = self.lookup_fabric_servers(fabinst)

        if not fabrics:
            # Raise, something went wrong.
            raise InterfaceError("Failed getting list of Fabric servers")

        if self._version_token == version:
            return

        _LOGGER.info(
            "Loading Fabric configuration version {version}".format(
                version=version))
        self._fabric_uuid = fabric_uuid
        self._version_token = version
        if ttl > 0:
            self._ttl = ttl

        # Update the Fabric servers
        for fabric in fabrics:
            inst = FabricConnection(self, fabric['host'], fabric['port'])
            inst_uuid = inst.uuid
            if inst_uuid not in self._fabric_instances:
                inst.connect()
                self._fabric_instances[inst_uuid] = inst
                _LOGGER.debug(
                    "Added new Fabric server {host}:{port}".format(
                        host=inst.host, port=inst.port))

    def reset_cache(self, group=None):
        """Reset cached information

        This method destroys all cached information.
        """
        if group:
            _LOGGER.debug("Resetting cache for group '{group}'".format(
                group=group))
            self.get_group_servers(group, use_cache=False)
        else:
            _LOGGER.debug("Resetting cache")
            self._cache = FabricCache()

    def get_instance(self):
        """Get a MySQL Fabric Instance

        This method will get the next available MySQL Fabric Instance.

        Raises InterfaceError when no instance is available or connected.
        """
        nxt = 0
        errmsg = "No MySQL Fabric instance available"
        if not self._fabric_instances:
            raise InterfaceError(errmsg + " (not seeded?)")
        if sys.version_info[0] == 2:
            instance_list = self._fabric_instances.keys()
            inst = self._fabric_instances[instance_list[nxt]]
        else:
            inst = self._fabric_instances[list(self._fabric_instances)[nxt]]
        if not inst.is_connected:
            inst.connect()
        return inst

    def set_server_status(self, server_uuid, status):
        """Set the status of a MySQL server in Fabric

        This method sets the status of a MySQL server identified by
        server_uuid.
        """
        inst = self.get_instance()
        inst.proxy.server.set_status(server_uuid, status)

    def lookup_fabric_servers(self, fabric_cnx=None):
        """Get all MySQL Fabric instances

        This method looks up the other MySQL Fabric instances which uses
        the same metadata. The returned list contains dictionaries with
        connection information such ass host and port. For example:

        [
            {'host': 'fabric_prod_1.example.com', 'port': 32274 },
            {'host': 'fabric_prod_2.example.com', 'port': 32274 },
        ]

        Returns a list of dictionaries
        """
        inst = fabric_cnx or self.get_instance()
        result = []
        err_msg = "Looking up Fabric servers failed using {host}:{port}: {err}"
        try:
            (fabric_uuid_str, version,
                ttl, addr_list) = inst.proxy.store.lookup_fabrics()
            for addr in addr_list:
                try:
                    host, port = addr.split(':', 2)
                    port = int(port)
                except ValueError:
                    host, port = addr, MYSQL_FABRIC_PORT
                result.append({'host': host, 'port': port})
        except (Fault, socket.error) as exc:
            msg = err_msg.format(err=str(exc), host=inst.host, port=inst.port)
            raise InterfaceError(msg)
        except (TypeError, AttributeError):
            msg = err_msg.format(err="No Fabric server available",
                                 host=inst.host, port=inst.port)
            raise InterfaceError(msg)

        try:
            fabric_uuid = uuid.UUID('{' + fabric_uuid_str + '}')
        except TypeError:
            fabric_uuid = uuid.uuid4()

        return fabric_uuid, version, ttl, result

    def get_group_servers(self, group, use_cache=True):
        """Get all MySQL servers in a group

        This method returns information about all MySQL part of the
        given high-availability group. When use_cache is set to
        True, the cached information will be used.

        Raises InterfaceError on errors.

        Returns list of FabricMySQLServer objects.
        """
        # Get group information from cache
        if use_cache:
            entry = self._cache.group_search(group)
            if entry:
                # Cache group information
                _LOGGER.debug("Using cached group information")
                return entry.servers

        inst = self.get_instance()
        result = []
        try:
            servers = inst.proxy.store.dump_servers(
                self._version_token, group)[3]
        except (Fault, socket.error) as exc:
            msg = ("Looking up MySQL servers failed for group "
                    "{group}: {error}").format(error=str(exc), group=group)
            raise InterfaceError(msg)

        weights = []
        for server in servers:
            # We make sure, when using local groups, we skip the global group
            if server[1] == group:
                server[3] = int(server[3])  # port should be an int
                mysqlserver = FabricMySQLServer(*server)
                result.append(mysqlserver)
                if mysqlserver.status == STATUS_SECONDARY:
                    weights.append((mysqlserver.uuid, mysqlserver.weight))

        self._cache.cache_group(group, result)
        if weights:
            self._group_balancers[group] = WeightedRoundRobin(*weights)

        return result

    def get_group_server(self, group, mode=None, status=None):
        """Get a MySQL server from a group

        The method uses MySQL Fabric to get the correct MySQL server
        for the specified group. You can specify mode or status, but
        not both.

        The mode argument will decide whether the primary or a secondary
        server is returned. When no secondary server is available, the
        primary is returned.

        Status is used to force getting either a primary or a secondary.

        The returned tuple contains host, port and uuid.

        Raises InterfaceError on errors; ValueError when both mode
        and status are given.

        Returns a FabricMySQLServer object.
        """
        if mode and status:
            raise ValueError(
                "Either mode or status must be given, not both")

        errmsg = "No MySQL server available for group '{group}'"

        servers = self.get_group_servers(group, use_cache=True)
        if not servers:
            raise InterfaceError(errmsg.format(group=group))

        # Get the Master and return list (host, port, UUID)
        primary = None
        secondary = []
        for server in servers:
            if server.status == STATUS_SECONDARY:
                secondary.append(server)
            elif server.status == STATUS_PRIMARY:
                primary = server

        if mode in (MODE_WRITEONLY, MODE_READWRITE) or status == STATUS_PRIMARY:
            if not primary:
                self.reset_cache(group=group)
                raise InterfaceError((errmsg + ' {query}={value}').format(
                    query='status' if status else 'mode',
                    group=group,
                    value=status or mode))
            return primary

        # Return primary if no secondary is available
        if not secondary and primary:
            return primary
        elif group in self._group_balancers:
            next_secondary = self._group_balancers[group].get_next()[0]
            for mysqlserver in secondary:
                if next_secondary == mysqlserver.uuid:
                    return mysqlserver

        self.reset_cache(group=group)
        raise InterfaceError(errmsg.format(group=group, mode=mode))

    def get_sharding_information(self, tables=None, database=None):
        """Get and cache the sharding information for given tables

        This method is fetching sharding information from MySQL Fabric
        and caches the result. The tables argument must be sequence
        of sequences contain the name of the database and table. If no
        database is given, the value for the database argument will
        be used.

        Examples:
          tables = [('salary',), ('employees',)]
          get_sharding_information(tables, database='employees')

          tables = [('salary', 'employees'), ('employees', employees)]
          get_sharding_information(tables)

        Raises ValueError when something is wrong with the tables argument.
        """
        if not isinstance(tables, (list, tuple)):
            raise ValueError("tables should be a sequence")

        patterns = []
        for table in tables:
            if not isinstance(table, (list, tuple)) and not database:
                raise ValueError("No database specified for table {0}".format(
                    table))

            if isinstance(table, (list, tuple)):
                dbase = table[1]
                tbl = table[0]
            else:
                dbase = database
                tbl = table
            patterns.append("{0}.{1}".format(dbase, tbl))

        inst = self.get_instance()

        result = inst.proxy.store.dump_sharding_information(
            self._version_token, ','.join(patterns))

        for info in result[3]:
            self._cache.sharding_cache_table(FabricShard(*info))

    def get_shard_server(self, tables, key, scope=SCOPE_LOCAL, mode=None):
        """Get MySQL server information for a particular shard"""
        if not isinstance(tables, (list, tuple)):
            raise ValueError("tables should be a sequence")

        groups = []

        for dbobj in tables:
            try:
                database, table = dbobj.split('.')
            except ValueError:
                raise ValueError(
                    "tables should be given as <database>.<table>, "
                    "was {0}".format(dbobj))

            entry = self._cache.sharding_search(database, table)
            if not entry:
                self.get_sharding_information((table,), database)
                entry = self._cache.sharding_search(database, table)

            if scope == 'GLOBAL':
                return self.get_group_server(entry.global_group, mode=mode)

            if entry.shard_type == 'RANGE':
                partitions = sorted(entry.partitioning.keys())
                index = partitions[bisect(partitions, int(key)) - 1]
                partition = entry.partitioning[index]
            elif entry.shard_type == 'HASH':
                md5key = md5(str(key))
                partition_keys = sorted(entry.partitioning.keys(), reverse=True)
                index = partition_keys[-1]
                for partkey in  partition_keys:
                    if md5key.digest() >= b16decode(partkey):
                        index = partkey
                        break
                partition = entry.partitioning[index]
            else:
                raise mysql.connector.InterfaceError(
                    "Unsupported sharding type {0}".format(entry.shard_type))

            groups.append(partition['group'])
            if not all(group == groups[0] for group in groups):
                raise mysql.connector.InterfaceError(
                    "Tables are located in different shards.")

        return self.get_group_server(groups[0], mode=mode)


class FabricConnection(object):

    """Class holding a connection to a MySQL Fabric server"""

    def __init__(self, fabric, host, port=MYSQL_FABRIC_PORT,
                 connect_attempts=_CNX_ATTEMPT_MAX,
                 connect_delay=_CNX_ATTEMPT_DELAY):
        if not isinstance(fabric, Fabric):
            raise ValueError("fabric must be instance of class Fabric")
        self._fabric = fabric
        self._host = host
        self._port = port
        self._proxy = None
        self._connect_attempts = connect_attempts
        self._connect_delay = connect_delay

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def uri(self):
        return _fabric_xmlrpc_uri(self._host, self._port)

    @property
    def uuid(self):
        return _fabric_server_uuid(self._host, self._port)

    @property
    def proxy(self):
        return self._proxy

    def _xmlrpc_get_proxy(self):
        """Return the XMLRPC server proxy instance to MySQL Fabric

        This method tries to get a valid connection to a MySQL Fabric
        server.

        Returns a XMLRPC ServerProxy instance.
        """
        if self.is_connected:
            return self._proxy

        attempts = self._connect_attempts
        delay = self._connect_delay

        proxy = None
        counter = 0
        while counter != attempts:
            counter += 1
            try:
                proxy = ServerProxy(self.uri)
                proxy._some_nonexisting_method()
            except Fault:
                # We are actually connected
                return proxy
            except socket.error as exc:
                if counter == attempts:
                    raise InterfaceError(
                        "Connection to MySQL Fabric failed ({0})".format(exc))
                _LOGGER.debug(
                    "Retrying {host}:{port}, attempts {counter}".format(
                        host=self.host, port=self.port, counter=counter))
            if delay > 0:
                time.sleep(delay)

    def connect(self):
        """Connect with MySQL Fabric"""
        self._proxy = self._xmlrpc_get_proxy()

    @property
    def is_connected(self):
        """Check whether connection with Fabric is valid

        Return True if we can still interact with the Fabric server; False
        if Not.

        Returns True or False.
        """
        try:
            self._proxy._some_nonexisting_method()
        except Fault:
            return True
        except (TypeError, AttributeError):
            return False
        else:
            return False

    def __repr__(self):
        return "{class_}(host={host}, port={port})".format(
            class_=self.__class__,
            host=self._host,
            port=self._port,
        )


class MySQLFabricConnection(object):
    """Connection to a MySQL server through MySQL Fabric"""
    def __init__(self, **kwargs):
        """Initialize"""
        self._mysql_cnx = None
        self._fabric = None
        self._fabric_mysql_server = None
        self._mysql_config = None
        self._cnx_properties = {}
        self.reset_properties()

        # Validity of fabric-argument is checked in config()-method
        if 'fabric' not in kwargs:
            raise ValueError("Configuration parameters for Fabric missing")

        if kwargs:
            self.store_config(**kwargs)

    def __getattr__(self, attr):
        """Return the return value of the MySQLConnection instance"""
        if attr.startswith('cmd_'):
            raise NotSupportedError(
                "Calling {attr} is not supported for connections managed by "
                "MySQL Fabric.".format(attr=attr))
        return getattr(self._mysql_cnx, attr)

    @property
    def fabric_uuid(self):
        """Returns the Fabric UUID of the MySQL server"""
        if self._fabric_mysql_server:
            return self._fabric_mysql_server.uuid
        return None

    @property
    def properties(self):
        """Returns connection properties"""
        return self._cnx_properties

    def reset_cache(self, group=None):
        """Reset cache for this connection's group"""
        if not group:
            group = self._fabric_mysql_server.group
        self._fabric.reset_cache(group=group)

    def is_connected(self):
        """Check whether we are connected with the MySQL server

        Returns True or False
        """
        return self._mysql_cnx is not None

    def reset_properties(self):
        """Resets the connection properties

        This method can be called to reset the connection properties to
        their default values.
        """
        for key, attr in _CNX_PROPERTIES.items():
            self._cnx_properties[key] = attr[2]

    def set_property(self, **properties):
        """Set one or more connection properties

        Arguments to the set_property() method will be used as properties.
        They are validated against the _CNX_PROPERTIES constant.

        Raise ValueError in case an invalid property is being set. TypeError
        is raised when the type of the value is not correct.

        To unset a property, set it to None.
        """
        try:
            self.close()
        except Error:
            # We tried, but it's OK when we fail.
            pass

        props = self._cnx_properties
        for name, value in properties.items():
            if name not in _CNX_PROPERTIES:
                ValueError("Invalid property connection {0}".format(name))
            elif name == 'group' and value and props['key']:
                raise ValueError(
                    "'group' property can not be set when 'key' is set.")
            elif name == 'key' and value and props['group']:
                raise ValueError(
                    "'key' property can not be set when 'group' is set.")
            elif name == 'scope' and value not in (SCOPE_LOCAL, SCOPE_GLOBAL):
                raise ValueError("Invalid value for 'scope'")
            elif name == 'mode' and value not in (
                    MODE_READWRITE, MODE_READONLY):
                raise ValueError("Invalid value for 'mode'")
            elif value is None:
                self._cnx_properties[name] = None
                continue
            elif not isinstance(value, _CNX_PROPERTIES[name][0]):
                raise TypeError(
                    "{name} is not valid, expeted a {typename})".format(
                        name=name,
                        typename=_CNX_PROPERTIES[name][0].__name__))
            props[name] = value

    def _configure_fabric(self, config):
        """Configure the Fabric connection

        The config argument can be either a dictionary containing the
        necessary information to setup the connection. Or config can
        be an instance of Fabric.
        """
        if isinstance(config, Fabric):
            self._fabric = config
        else:
            required_keys = ('host',)
            for required_key in required_keys:
                if required_key not in config:
                    raise ValueError(
                        "Missing configuration parameter '{parameter}' "
                        "for fabric".format(paramter=required_key))
            host = config['host']
            port = config.get('port', MYSQL_FABRIC_PORT)
            server_uuid = _fabric_server_uuid(host, port)
            try:
                self._fabric = FABRICS[server_uuid]
            except KeyError:
                _LOGGER.debug("New Fabric connection")
                self._fabric = Fabric(**config)
                self._fabric.seed()
                # Cache the new connection
                FABRICS[server_uuid] = self._fabric

    def store_config(self, **kwargs):
        """Store configuration of MySQL connections to use with Fabric

        The configuration found in the dictionary kwargs is used
        when instanciating a MySQLConnection object. The host and port
        entries are used to connect to MySQL Fabric.

        Raises ValueError when the Fabric configuration parameter
        is not correct or missing; AttributeError is raised when
        when a paramater is not valid.
        """
        config = kwargs.copy()

        # Configure the Fabric connection
        if 'fabric' in config:
            self._configure_fabric(config['fabric'])
            del config['fabric']

        if 'unix_socket' in config:
            _LOGGER.warning("MySQL Fabric does not use UNIX sockets.")
            config['unix_socket'] = None

        # Try to use the configuration
        test_config = config.copy()
        if 'pool_name' in test_config:
            del test_config['pool_name']
        if 'pool_size' in test_config:
            del test_config['pool_size']
        try:
            pool = mysql.connector.MySQLConnectionPool(
                pool_name=str(uuid.uuid4()))
            pool.set_config(**test_config)
        except AttributeError as err:
            raise AttributeError(
                "Connection configuration not valid: {0}".format(err))

        self._mysql_config = config

    def _connect(self):
        """Get a MySQL server based on properties and connect

        This method gets a MySQL server from MySQL Fabric using already
        properties set using the set_property() method. You can specify how
        many times and the delay between trying using attempts and
        attempt_delay.

        Raises InterfaceError on errors. A ValueError is raised when
        both group and sharding are specified, or neither of them.
        """
        if self.is_connected():
            return
        props = self._cnx_properties
        attempts = props['attempts']
        attempt_delay = props['attempt_delay']

        if props['group'] and props['tables']:
            raise ValueError(
                "Either 'group' or 'tables' property can be set, not both.")
        if not (props['group'] or props['tables']):
            raise ValueError(
                "Either 'group' or 'tables' property needs to be set.")

        dbconfig = self._mysql_config.copy()
        counter = 0
        while counter != attempts:
            counter += 1
            try:
                group = None
                if props['tables']:
                    if props['scope'] == 'LOCAL' and not props['key']:
                        raise ValueError(
                            "Scope 'LOCAL' needs key property to be set")
                    mysqlserver = self._fabric.get_shard_server(
                        props['tables'], props['key'],
                        scope=props['scope'],
                        mode=props['mode'])
                elif props['group']:
                    group = props['group']
                    mysqlserver = self._fabric.get_group_server(
                        group, mode=props['mode'])
                else:
                    raise InterfaceError(
                        "Missing group or key and tables properties")
            except InterfaceError as err:
                _LOGGER.debug(
                    "Trying to get MySQL server (attempt {0}; {1})".format(
                        counter, err))
                if counter == attempts:
                    raise InterfaceError(
                        "Error getting connection: {0}".format(err))
                if attempt_delay > 0:
                    time.sleep(attempt_delay)
                continue

            # Make sure we do not change the stored configuration
            dbconfig['host'] = mysqlserver.host
            dbconfig['port'] = mysqlserver.port
            try:
                self._mysql_cnx = mysql.connector.connect(**dbconfig)
            except InterfaceError as err:
                self._fabric.set_server_status(mysqlserver.uuid,
                                                STATUS_FAULTY)
                self.reset_cache(mysqlserver.group)
                if counter == attempts:
                    raise InterfaceError(
                        "Reported faulty server to Fabric ({0})".format(err))
            else:
                self._fabric_mysql_server = mysqlserver
                break

    def disconnect(self):
        """Close connection to MySQL server"""
        try:
            self.rollback()
            self._mysql_cnx.close()
        except (AttributeError):
            pass  # There was no connection
        except Error:
            raise
        finally:
            self._mysql_cnx = None
            self._fabric_mysql_server = None
    close = disconnect

    def cursor(self, buffered=None, raw=None, prepared=None, cursor_class=None):
        """Instantiates and returns a cursor

        This method is similar to MySQLConnection.cursor() except that
        it checks whether the connection is available and raises
        an InterfaceError when not.

        cursor_class argument is not supported and will raise a
        NotSupportedError exception.

        Returns a MySQLCursor or subclass.
        """
        self._connect()
        if cursor_class:
            raise NotSupportedError(
                "Custom cursors not supported with MySQL Fabric")

        if prepared:
            raise NotSupportedError(
                "Prepared Statements are not supported with MySQL Fabric")

        if self._unread_result is True:
            raise InternalError("Unread result found.")

        buffered = buffered or self._buffered
        raw = raw or self._raw

        cursor_type = 0
        if buffered is True:
            cursor_type |= 1
        if raw is True:
            cursor_type |= 2

        types = (
            MySQLCursor,  # 0
            MySQLCursorBuffered,
            MySQLCursorRaw,
            MySQLCursorBufferedRaw,
        )
        return (types[cursor_type])(self)

    def handle_mysql_error(self, exc):
        """Handles MySQL errors

        This method takes a mysql.connector.errors.Error exception
        and checks the error code. Based on the value, it takes
        certain actions such as clear in the cache.
        """
        if exc.errno in RESET_CACHE_ON_ERROR:
            self.reset_cache()
            raise MySQLFabricError(
                "Temporary error ({error}); "
                "retry transaction".format(error=str(exc)))

        raise exc

    def commit(self):
        """Commit current transaction

        Raises whatever MySQLConnection.commit() raises, but
        raises MySQLFabricError when MySQL returns error
        ER_OPTION_PREVENTS_STATEMENT.
        """
        try:
            self._mysql_cnx.commit()
        except Error as exc:
            self.handle_mysql_error(exc)

    def rollback(self):
        """Rollback current transaction

        Raises whatever MySQLConnection.rollback() raises, but
        raises MySQLFabricError when MySQL returns error
        ER_OPTION_PREVENTS_STATEMENT.
        """
        try:
            self._mysql_cnx.rollback()
        except Error as exc:
            self.handle_mysql_error(exc)

    def cmd_query(self, statement):
        """Send a statement to the MySQL server

        Raises whatever MySQLConnection.cmd_query() raises, but
        raises MySQLFabricError when MySQL returns error
        ER_OPTION_PREVENTS_STATEMENT.

        Returns a dictionary.
        """
        self._connect()
        try:
            return self._mysql_cnx.cmd_query(statement)
        except Error as exc:
            self.handle_mysql_error(exc)

    def cmd_query_iter(self, statements):
        """Send one or more statements to the MySQL server

        Raises whatever MySQLConnection.cmd_query_iter() raises, but
        raises MySQLFabricError when MySQL returns error
        ER_OPTION_PREVENTS_STATEMENT.

        Returns a dictionary.
        """
        self._connect()
        try:
            return self._mysql_cnx.cmd_query_iter(statements)
        except Error as exc:
            self.handle_mysql_error(exc)

