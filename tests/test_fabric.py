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

"""Unittests for mysql.connector.fabric
"""

import sys
import uuid

try:
    from xmlrpclib import Fault, ServerProxy
except ImportError:
    # Python v3
    from xmlrpc.client import Fault, ServerProxy  # pylint: disable=F0401

import tests
import mysql.connector
from mysql.connector import fabric, errorcode, errors
from mysql.connector.fabric import connection, caching, balancing

_HOST = 'tests.example.com'
_PORT = 1234


class _MockupXMLProxy(object):

    """Mock-up of XMLProxy simulating Fabric XMLRPC

    This class can be used as a mockup for xmlrpclib.ServerProxy
    """

    fabric_servers = ['tests.example.com:1234']
    fabric_uuid = 'c4563310-f742-4d24-87ec-930088d892ff'
    version_token = 1
    ttl = 1 * 60

    groups = {
        'testgroup1': [
            ['a6ac2895-574f-11e3-bc32-bcaec56cc4a7', 'testgroup1',
                _HOST, '3372', 1, 2, 1.0],
            ['af1cb1e4-574f-11e3-bc33-bcaec56cc4a7', 'testgroup1',
                _HOST, '3373', 3, 3, 1.0],
        ],
        'testgroup2': [
            ['b99bf2f3-574f-11e3-bc33-bcaec56cc4a7', 'testgroup2',
                _HOST, '3374', 3, 3, 1.0],
            ['c3afdef6-574f-11e3-bc33-bcaec56cc4a7', 'testgroup2',
                _HOST, '3375', 1, 2, 1.0],
        ],
        'testglobalgroup': [
            ['91f7090e-574f-11e3-bc32-bcaec56cc4a7', 'testglobalgroup',
                _HOST, '3370', 3, 3, 1.0],
            ['9c09932d-574f-11e3-bc32-bcaec56cc4a7', 'testglobalgroup',
                _HOST, '3371', 1, 2, 1.0],
        ],
        'onlysecondary': [
            ['b99bf2f3-574f-11e3-bc33-bcaec56cc4a7', 'onlysecondary',
                _HOST, '3374', 1, 2, 1.0],
            ['c3afdef6-574f-11e3-bc33-bcaec56cc4a7', 'onlysecondary',
                _HOST, '3375', 1, 2, 1.0],
        ],
        'onlyprimary': [
            ['af1cb1e4-574f-11e3-bc33-bcaec56cc4a7', 'onlyprimary',
                _HOST, '3373', 3, 3, 1.0],
        ],
        'onlyspare': [
            ['b99bf2f3-574f-11e3-bc33-bcaec56cc4a7', 'onlyspare',
                _HOST, '3374', 1, 1, 1.0],
            ['c3afdef6-574f-11e3-bc33-bcaec56cc4a7', 'onlyspare',
                _HOST, '3375', 1, 1, 1.0],
        ],
        'emptygroup': [],
    }

    sharding_information = {
        'shardtype.range': [
            ['shardtype', 'range', 'id', '1', '1',
             'RANGE', 'testgroup1', 'testglobalgroup'],
            ['shardtype', 'range', 'id', '21', '2',
             'RANGE', 'testgroup2', 'testglobalgroup'],
        ],
        'shardtype.hash': [
            ['shardtype', 'hash', 'name',
             '513772EE53011AD9F4DC374B2D34D0E9', '1',
             'HASH', 'testgroup1', 'testglobalgroup'],
            ['shardtype', 'hash', 'name',
             'F617868BD8C41043DC4BEBC7952C7024', '2',
             'HASH', 'testgroup2', 'testglobalgroup'],
        ],
        'shardtype.spam': [
            ['shardtype', 'spam', 'emp_no', '1', '1',
             'SPAM', 'testgroup1', 'testglobalgroup'],
            ['shardtype', 'spam', 'emp_no', '21', '2',
             'SPAM', 'testgroup2', 'testglobalgroup'],
        ],
    }

    @classmethod
    def wrap_response(self, data):
        return (
            _MockupXMLProxy.fabric_uuid,
            _MockupXMLProxy.version_token,  # version
            _MockupXMLProxy.ttl,  # ttl
            data,
            )

    @property
    def server(self):
        class Server(object):
            def set_status(self, server_uuid, status):
                return (server_uuid, status)
        return Server()

    @property
    def store(self):
        class Store(object):
            def lookup_fabrics(self):
                return _MockupXMLProxy.wrap_response(
                    _MockupXMLProxy.fabric_servers)
            def dump_servers(self, version, patterns):
                groups = patterns.split(',')
                data = [server for group in groups
                    for server in _MockupXMLProxy.groups[group]]
                return _MockupXMLProxy.wrap_response(data)
            def dump_sharding_information(self, version, patterns):
                tables = patterns.split(',')
                data = [shard for table in tables
                    for shard in _MockupXMLProxy.sharding_information[table]]
                return _MockupXMLProxy.wrap_response(data)
        return Store()

    def __init__(self, uri=None):
        """Initializing"""
        self._uri = uri

    def _some_nonexisting_method(self):
        """A non-existing method raising Fault"""
        raise Fault(0, 'Testing')

class _MockupFabric(fabric.Fabric):

    """Mock-up of fabric.Fabric

    This class is similar to fabric.Fabric except that it does not
    create a connection with MySQL Fabric. It is used to be able to
    unit tests without the need of having to run a complete Fabric
    setup.
    """

    def seed(self, host=None, port=None):
        if _HOST in (host, self._init_host):
            self._cnx_class = _MockupFabricConnection
        super(_MockupFabric, self).seed(host, port)

class _MockupFabricConnection(fabric.FabricConnection):

    """Mock-up of fabric.FabricConnection"""
    def _xmlrpc_get_proxy(self):
        return _MockupXMLProxy()


class FabricModuleTests(tests.MySQLConnectorTests):

    """Testing mysql.connector.fabric module"""

    def test___all___(self):
        attrs = [
            'MODE_READWRITE',
            'MODE_READONLY',
            'STATUS_PRIMARY',
            'STATUS_SECONDARY',
            'SCOPE_GLOBAL',
            'SCOPE_LOCAL',
            'FabricMySQLServer',
            'FabricShard',
            'connect',
            'Fabric',
            'FabricConnection',
            'MySQLFabricConnection',
        ]

        for attr in attrs:
            try:
                getattr(fabric, attr)
            except AttributeError:
                self.fail("Attribute '{0}' not in fabric.__all__".format(attr))

    def test_fabricmyqlserver(self):
        attrs = ['uuid', 'group', 'host', 'port', 'mode', 'status', 'weight']
        try:
            nmdtpl = fabric.FabricMySQLServer(*(['']*len(attrs)))
        except TypeError:
            self.fail("Fail creating namedtuple FabricMySQLServer")

        self.check_namedtuple(nmdtpl, attrs)

    def test_fabricshard(self):
        attrs = [
            'database', 'table', 'column', 'key', 'shard', 'shard_type',
            'group', 'global_group'
            ]
        try:
            nmdtpl = fabric.FabricShard(*(['']*len(attrs)))
        except TypeError:
            self.fail("Fail creating namedtuple FabricShard")

        self.check_namedtuple(nmdtpl, attrs)

    def test_connect(self):

        class FakeConnection(object):
            def __init__(self, *args, **kwargs):
                pass
        orig = fabric.MySQLFabricConnection
        fabric.MySQLFabricConnection = FakeConnection

        self.assertTrue(isinstance(fabric.connect(), FakeConnection))
        fabric.MySQLFabricConnection = orig


class ConnectionModuleTests(tests.MySQLConnectorTests):

    """Testing mysql.connector.fabric.connection module"""

    def test_module_variables(self):
        error_codes = (
            errorcode.CR_SERVER_LOST,
            errorcode.ER_OPTION_PREVENTS_STATEMENT,
            )
        self.assertEqual(error_codes, connection.RESET_CACHE_ON_ERROR)

        modvars = {
            'MYSQL_FABRIC_PORT': 8080,
            'FABRICS': {},
            '_CNX_ATTEMPT_DELAY': 1,
            '_CNX_ATTEMPT_MAX': 3,
            '_GETCNX_ATTEMPT_DELAY': 1,
            '_GETCNX_ATTEMPT_MAX': 3,
            '_MONITOR_INTERVAL': 2,
            'MODE_READONLY': 1,
            'MODE_WRITEONLY': 2,
            'MODE_READWRITE': 3,
            'STATUS_FAULTY': 0,
            'STATUS_SPARE': 1,
            'STATUS_SECONDARY': 2,
            'STATUS_PRIMARY': 3,
            'SCOPE_GLOBAL': 'GLOBAL',
            'SCOPE_LOCAL': 'LOCAL',
            '_SERVER_STATUS_FAULTY': 'FAULTY',
            }

        for modvar, value in modvars.items():
            try:
                self.assertEqual(value, getattr(connection, modvar))
            except AttributeError:
                self.fail("Module variable connection.{0} not found".format(
                    modvar))

    def test_cnx_properties(self):
        cnxprops = {
            # name: (valid_types, description, default)
            'group': (str, "Name of group of servers", None),
            'key': ((str, int), "Sharding key", None),
            'tables': ((tuple, list), "List of tables in query", None),
            'mode': (int, "Read-Only, Write-Only or Read-Write", None),
            'shard': (str, "Identity of the shard for direct connection", None),
            'mapping': (str, "", None),
            'scope': (str, "GLOBAL for accessing Global Group, or LOCAL",
                connection.SCOPE_LOCAL),
            'attempts': (int, "Attempts for getting connection", 3),
            'attempt_delay': (int, "Seconds to wait between each attempt", 1),
            }

        for prop, desc in cnxprops.items():
            try:
                self.assertEqual(desc, connection._CNX_PROPERTIES[prop])
            except KeyError:
                self.fail("Connection property '{0}'' not available".format(
                    prop))

        self.assertEqual(len(cnxprops), len(connection._CNX_PROPERTIES))

    def test__fabric_xmlrpc_uri(self):
        data = ('example.com', _PORT)
        exp = 'http://{host}:{port}'.format(host=data[0], port=data[1])
        self.assertEqual(exp, connection._fabric_xmlrpc_uri(*data))

    def test__fabric_server_uuid(self):
        data = ('example.com', _PORT)
        url = 'http://{host}:{port}'.format(host=data[0], port=data[1])
        exp = uuid.uuid3(uuid.NAMESPACE_URL, url)
        self.assertEqual(exp, connection._fabric_server_uuid(*data))


class FabricTests(tests.MySQLConnectorTests):

    """Testing mysql.connector.fabric.Fabric class"""

    def setUp(self):
        self._orig_fabric_connection_class = connection.FabricConnection
        self._orig_fabric_servers = _MockupXMLProxy.fabric_servers

        connection.FabricConnection = _MockupFabricConnection

    def tearDown(self):
        connection.FabricConnection = self._orig_fabric_connection_class
        _MockupXMLProxy.fabric_servers = self._orig_fabric_servers

    def test___init__(self):
        fab = fabric.Fabric(_HOST, port=_PORT)
        attrs = {
            '_fabric_instances': {},
            '_fabric_uuid': None,
            '_ttl': 1 * 60,
            '_version_token': None,
            '_connect_attempts': connection._CNX_ATTEMPT_MAX,
            '_connect_delay': connection._CNX_ATTEMPT_DELAY,
            '_cache': None,
            '_group_balancers': {},
            '_init_host': _HOST,
            '_init_port': _PORT,
            }

        for attr, default in attrs.items():
            if attr in ('_cache', '_fabric_instances'):
                # Tested later
                continue
            try:
                self.assertEqual(default, getattr(fab, attr))
            except AttributeError:
                self.fail("Fabric instance has no attribute '{0}'".format(
                    attr))

        self.assertTrue(isinstance(fab._cache, caching.FabricCache))
        self.assertEqual(fab._fabric_instances, {})

    def test_seed(self):
        fab = _MockupFabric(_HOST, _PORT)

        # Empty server list results in InterfaceError
        _MockupXMLProxy.fabric_servers = None
        self.assertRaises(errors.InterfaceError, fab.seed)
        _MockupXMLProxy.fabric_servers = self._orig_fabric_servers

        exp_server_uuid = uuid.UUID(_MockupXMLProxy.fabric_uuid)
        exp_version = _MockupXMLProxy.version_token
        exp_ttl = _MockupXMLProxy.ttl
        fabrics = [
                    {'host': _HOST, 'port': _PORT }
            ]

        # Normal operations
        fab.seed()
        self.assertEqual(exp_server_uuid, fab._fabric_uuid)
        self.assertEqual(exp_version, fab._version_token)
        self.assertEqual(exp_ttl, fab._ttl)

        exp_fabinst_uuid = connection._fabric_server_uuid(
            fabrics[0]['host'], fabrics[0]['port'])

        self.assertTrue(exp_fabinst_uuid in fab._fabric_instances)
        fabinst = fab._fabric_instances[exp_fabinst_uuid]
        self.assertEqual(fabrics[0]['host'], fabinst.host)
        self.assertEqual(fabrics[0]['port'], fabinst.port)

        # Don't change anything when version did not change
        exp_ttl = 10
        fab.seed()
        self.assertNotEqual(exp_ttl, fab._ttl)

    def test_reset_cache(self):
        class FabricNoServersLookup(_MockupFabric):
            def get_group_servers(self, group, use_cache=True):
                self.test_group = group

        fab = FabricNoServersLookup(_HOST)
        first_cache = fab._cache
        fab.reset_cache()
        self.assertNotEqual(first_cache, fab._cache)

        exp = 'testgroup'
        fab.reset_cache(exp)
        self.assertEqual(exp, fab.test_group)

    def test_get_instance(self):
        fab = _MockupFabric(_HOST, _PORT)
        self.assertRaises(errors.InterfaceError, fab.get_instance)

        fab.seed()
        if sys.version_info[0] == 2:
            instance_list = fab._fabric_instances.keys()
            exp = fab._fabric_instances[instance_list[0]]
        else:
            exp = fab._fabric_instances[list(fab._fabric_instances)[0]]
        self.assertEqual(exp, fab.get_instance())

    def test_set_server_status(self):
        fab = _MockupFabric(_HOST, _PORT)

        fabinst = connection.FabricConnection(fab, _HOST, _PORT)
        fabinst._proxy = _MockupXMLProxy()
        fab._fabric_instances[fabinst.uuid] = fabinst

        fab.set_server_status(uuid.uuid4(), connection._SERVER_STATUS_FAULTY)

    def test_lookup_fabric_servers(self):
        fab = _MockupFabric(_HOST, _PORT)
        fab.seed()

        exp = (
            uuid.UUID('{' + _MockupXMLProxy.fabric_uuid + '}'),
            _MockupXMLProxy.version_token,
            _MockupXMLProxy.ttl,
            [{'host': _HOST, 'port': _PORT}]
            )

        self.assertEqual(exp, fab.lookup_fabric_servers())

        # No instances available
        fabinst = _MockupFabricConnection(fab, _HOST, _PORT)
        fab._fabric_instances = {}
        self.assertRaises(errors.InterfaceError,
                          fab.lookup_fabric_servers)

        fabinst.connect()
        self.assertEqual(exp, fab.lookup_fabric_servers(fabinst))

        fab.seed()

    def test_get_group_servers(self):
        fab = _MockupFabric(_HOST, _PORT)
        fab.seed()

        exp = [
            # Secondary
            fabric.FabricMySQLServer(
                uuid='a6ac2895-574f-11e3-bc32-bcaec56cc4a7',
                group='testgroup1',
                host='tests.example.com', port=3372,
                mode=1, status=2, weight=1.0),
            # Primary
            fabric.FabricMySQLServer(
                uuid='af1cb1e4-574f-11e3-bc33-bcaec56cc4a7',
                group='testgroup1',
                host='tests.example.com', port=3373,
                mode=3, status=3, weight=1.0),
            ]

        self.assertEqual(exp, fab.get_group_servers('testgroup1'))
        self.assertEqual(exp,
                         fab.get_group_servers('testgroup1', use_cache=False))

        exp_balancers = {
            'testgroup1': balancing.WeightedRoundRobin(
                (exp[0].uuid, exp[0].weight))
            }
        self.assertEqual(exp_balancers, fab._group_balancers)

        # No instances available, checking cache
        fab._fabric_instances = {}
        fab.get_group_servers('testgroup1')
        self.assertEqual(exp, fab.get_group_servers('testgroup1'))

        # Force lookup
        self.assertRaises(errors.InterfaceError,
                          fab.get_group_servers, 'testgroup1', use_cache=False)

    def test_get_group_server(self):
        fab = _MockupFabric(_HOST, _PORT)
        fab.seed()

        self.assertRaises(ValueError, fab.get_group_server,
                          'testgroup1', mode=1, status=1)

        self.assertRaises(errors.InterfaceError, fab.get_group_server,
                          'emptygroup')

        # Request PRIMARY (master)
        exp = fab.get_group_servers('testgroup1')[1]
        self.assertEqual(
            exp,
            fab.get_group_server('testgroup1', status=fabric.STATUS_PRIMARY)
            )
        self.assertEqual(
            exp,
            fab.get_group_server('testgroup1', mode=fabric.MODE_READWRITE)
            )

        # Request PRIMARY, but non available
        self.assertRaises(errors.InterfaceError,
                          fab.get_group_server,
                          'onlysecondary', status=fabric.STATUS_PRIMARY)
        self.assertRaises(errors.InterfaceError,
                          fab.get_group_server,
                          'onlysecondary', mode=fabric.MODE_READWRITE)

        # Request SECONDARY, but non available, returns primary
        exp = fab.get_group_servers('onlyprimary')[0]
        self.assertEqual(
            exp,
            fab.get_group_server('onlyprimary', mode=fabric.MODE_READONLY)
            )

        # Request SECONDARY
        exp = fab.get_group_servers('testgroup1')[0]
        self.assertEqual(
            exp,
            fab.get_group_server('testgroup1', status=fabric.STATUS_SECONDARY)
            )
        self.assertEqual(
            exp,
            fab.get_group_server('testgroup1', mode=fabric.MODE_READONLY)
            )

        # No Primary or Secondary
        self.assertRaises(errors.InterfaceError,
                          fab.get_group_server, 'onlyspare',
                          status=fabric.STATUS_SECONDARY)

    def test_get_sharding_information(self):
        fab = _MockupFabric(_HOST, _PORT)
        fab.seed()

        self.assertRaises(ValueError, fab.get_sharding_information,
                          'notlist')

        table = ('range', 'shardtype')  # table name, database name

        exp = {
            1: {'group': 'testgroup1'},
            21: {'group': 'testgroup2'}
            }

        fab.get_sharding_information([table])
        entry = fab._cache.sharding_search(table[1], table[0])
        self.assertEqual(exp, entry.partitioning)

        fab.get_sharding_information([table[0]], 'shardtype')
        entry = fab._cache.sharding_search(table[1], table[0])
        self.assertEqual(exp, entry.partitioning)

    def test_get_shard_server(self):
        fab = _MockupFabric(_HOST, _PORT)
        fab.seed()

        self.assertRaises(ValueError, fab.get_shard_server, 'notlist', 1)
        self.assertRaises(ValueError, fab.get_shard_server, ['not_list'], 1)

        exp_local = [
            # Secondary
            fabric.FabricMySQLServer(
                uuid='a6ac2895-574f-11e3-bc32-bcaec56cc4a7',
                group='testgroup1',
                host='tests.example.com', port=3372,
                mode=1, status=2, weight=1.0),
            # Primary
            fabric.FabricMySQLServer(
                uuid='af1cb1e4-574f-11e3-bc33-bcaec56cc4a7',
                group='testgroup1',
                host='tests.example.com', port=3373,
                mode=3, status=3, weight=1.0),
            ]

        exp_global = [
            fabric.FabricMySQLServer(
                uuid='91f7090e-574f-11e3-bc32-bcaec56cc4a7',
                group='testglobalgroup',
                host='tests.example.com', port=3370,
                mode=3, status=3, weight=1.0),
            fabric.FabricMySQLServer(
                uuid='9c09932d-574f-11e3-bc32-bcaec56cc4a7',
                group='testglobalgroup',
                host='tests.example.com', port=3371,
                mode=1, status=2, weight=1.0),
            ]

        # scope=SCOPE_LOCAL, mode=None
        self.assertEqual(
            exp_local[0],
            fab.get_shard_server(['shardtype.range'], 1)
            )

        # scope=SCOPE_GLOBAL, read-only and read-write
        self.assertEqual(
            exp_global[0],
            fab.get_shard_server(['shardtype.range'], 1,
                scope=fabric.SCOPE_GLOBAL, mode=fabric.MODE_READWRITE)
            )
        self.assertEqual(
            exp_global[1],
            fab.get_shard_server(['shardtype.range'], 1,
                scope=fabric.SCOPE_GLOBAL, mode=fabric.MODE_READONLY)
            )

        self.assertRaises(errors.InterfaceError,
                          fab.get_shard_server, ['shardtype.spam'], 1)


class FabricConnectionTests(tests.MySQLConnectorTests):

    """Testing mysql.connector.fabric.FabricConnection class"""

    def setUp(self):
        self.fab = connection.Fabric(_HOST, port=_PORT)
        self.fabcnx = connection.FabricConnection(self.fab, _HOST, port=_PORT)

    def tearDown(self):
        connection.ServerProxy = ServerProxy

    def test___init___(self):
        self.assertRaises(ValueError,
                          connection.FabricConnection, None, _HOST, port=_PORT)

        attrs = {
            '_fabric': self.fab,
            '_host': _HOST,
            '_port': _PORT,
            '_proxy': None,
            '_connect_attempts': connection._CNX_ATTEMPT_MAX,
            '_connect_delay': connection._CNX_ATTEMPT_DELAY,
            }

        for attr, default in attrs.items():
            try:
                self.assertEqual(default, getattr(self.fabcnx, attr))
            except AttributeError:
                self.fail("FabricConnection instance has no "
                          "attribute '{0}'".format(attr))

    def test_host(self):
        self.assertEqual(_HOST, self.fabcnx.host)

    def test_port(self):
        fabcnx = connection.FabricConnection(self.fab, _HOST, port=_PORT)
        self.assertEqual(_PORT, self.fabcnx.port)

    def test_uri(self):
        self.assertEqual(connection._fabric_xmlrpc_uri(_HOST, _PORT),
                         self.fabcnx.uri)

    def test_proxy(self):
        # We did not yet connect
        self.assertEqual(None, self.fabcnx.proxy)

    def test__xmlrpc_get_proxy(self):
        # Try connection, which fails
        self.fabcnx._connect_attempts = 1  # Make it fail quicker
        self.assertRaises(errors.InterfaceError,
                          self.fabcnx._xmlrpc_get_proxy)

        # Using mock-up
        connection.ServerProxy = _MockupXMLProxy
        self.assertTrue(isinstance(self.fabcnx._xmlrpc_get_proxy(),
                                   _MockupXMLProxy))

    def test_connect(self):
        # Try connection, which fails
        self.fabcnx._connect_attempts = 1  # Make it fail quicker
        self.assertRaises(errors.InterfaceError, self.fabcnx.connect)

        # Using mock-up
        connection.ServerProxy = _MockupXMLProxy
        self.fabcnx.connect()
        self.assertTrue(isinstance(self.fabcnx.proxy, _MockupXMLProxy))

    def test_is_connected(self):
        self.assertFalse(self.fabcnx.is_connected)
        self.fabcnx._proxy = 'spam'
        self.assertFalse(self.fabcnx.is_connected)

        # Using mock-up
        connection.ServerProxy = _MockupXMLProxy
        self.fabcnx.connect()
        self.assertTrue(self.fabcnx.is_connected)


class MySQLFabricConnectionTests(tests.MySQLConnectorTests):

    """Testing mysql.connector.fabric.FabricConnection class"""

    def setUp(self):
        # Mock-up: we don't actually connect to Fabric
        connection.ServerProxy = _MockupXMLProxy
        self.fabric_config = {
            'host': _HOST,
            'port': _PORT,
            }
        config = {'fabric': self.fabric_config}
        self.cnx = connection.MySQLFabricConnection(**config)

    def tearDown(self):
        connection.ServerProxy = ServerProxy

    def _get_default_properties(self):
        result = {}
        for key, attr in connection._CNX_PROPERTIES.items():
            result[key] = attr[2]
        return result

    def test___init__(self):
        # Missing 'fabric' argument
        self.assertRaises(ValueError,
                          connection.MySQLFabricConnection)

        attrs = {
            '_mysql_cnx': None,
            '_fabric': None,
            '_fabric_mysql_server': None,
            '_mysql_config': {},
            '_cnx_properties': {},
            }

        for attr, default in attrs.items():
            if attr in ('_cnx_properties', '_fabric'):
                continue
            try:
                self.assertEqual(default, getattr(self.cnx, attr),
                                 "Wrong init for {0}".format(attr))
            except AttributeError:
                self.fail("MySQLFabricConnection instance has no "
                          "attribute '{0}'".format(attr))

        self.assertEqual(self._get_default_properties(),
                         self.cnx._cnx_properties)

    def test___getattr__(self):
        none_supported_attrs = [
            'cmd_refresh',
            'cmd_quit',
            'cmd_shutdown',
            'cmd_statistics',
            'cmd_process_info',
            'cmd_process_kill',
            'cmd_debug',
            'cmd_ping',
            'cmd_change_user',
            'cmd_stmt_prepare',
            'cmd_stmt_execute',
            'cmd_stmt_close',
            'cmd_stmt_send_long_data',
            'cmd_stmt_reset',
        ]
        for attr in none_supported_attrs:
            self.assertRaises(errors.NotSupportedError,
                              getattr, self.cnx, attr)

    def test_fabric_uuid(self):
        self.cnx._fabric_mysql_server = fabric.FabricMySQLServer(
            uuid='af1cb1e4-574f-11e3-bc33-bcaec56cc4a7',
            group='testgroup1',
            host='tests.example.com', port=3373,
            mode=3, status=3, weight=1.0
            )
        exp = 'af1cb1e4-574f-11e3-bc33-bcaec56cc4a7'
        self.assertEqual(exp, self.cnx.fabric_uuid)


    def test_properties(self):
        self.assertEqual(self.cnx._cnx_properties, self.cnx.properties)


class FabricConnectorPythonTests(tests.MySQLConnectorTests):

    """Testing mysql.connector.connect()"""

    def setUp(self):
        # Mock-up: we don't actually connect to Fabric
        connection.ServerProxy = _MockupXMLProxy
        self.fabric_config = {
            'host': _HOST,
            'port': _PORT,
            }
        self.config = {'fabric': self.fabric_config}

    def tearDown(self):
        connection.ServerProxy = ServerProxy

    def test_connect(self):
        self.assertTrue(isinstance(
            mysql.connector.connect(**self.config),
            connection.MySQLFabricConnection
            ))

