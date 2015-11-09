import os
import shutil
import tempfile
import unittest

from basefs import exceptions
from basefs.handlers import BasefsSyncProtocol
from basefs.keys import Key
from basefs.logs import Log
from basefs.views import View

from . import utils


class HandlerTests(unittest.TestCase):
    def init(self):
        __, self.logpath = tempfile.mkstemp()
        __, self.logpath_b = tempfile.mkstemp()
        self.addCleanup(os.remove, self.logpath)
        self.addCleanup(os.remove, self.logpath_b)
        self.log, self.root_key = utils.bootstrap(self.logpath)
        shutil.copy2(self.logpath, self.logpath_b)
        self.log_b = Log(self.logpath_b)
        self.log.load()
        self.log_b.load()
        self.view = View(self.log, self.root_key)
        self.view_b = View(self.log_b, self.root_key)
        self.view.build()
        self.view_b.build()
        protocol = BasefsSyncProtocol(self.log)
        protocol_b = BasefsSyncProtocol(self.log_b)
        protocol.transport = utils.Socket()
        protocol_b.transport = utils.Socket()
        return protocol, protocol_b
    
    def test_sync(self):
        protocol, protocol_b = self.init()
        self.assertEqual(protocol.initial_request(), protocol_b.initial_request())
        path = os.path.join(os.sep, 'home-' + utils.random_ascii())
        node = self.view.mkdir(path)
        protocol.update_merkle(node.entry)
        self.assertNotEqual(protocol.initial_request(), protocol_b.initial_request())
        # 1
        request = protocol_b.initial_request()
        # 2
        protocol.data_received(request)
        response = protocol.transport.read()
        protocol.transport = utils.Socket()
        self.assertEqual(protocol.LS, response.decode().splitlines()[0])
        self.assertEqual('*/ ' + self.log.root.hash, response.decode().splitlines()[1])
        # 3
        protocol_b.data_received(response)
        response = protocol_b.transport.read()
        protocol_b.transport = utils.Socket()
        self.assertEqual(protocol.PATH_REQ, response.decode().splitlines()[0])
        self.assertEqual(path, response.decode().splitlines()[1])
        self.assertEqual(2, len(response.decode().splitlines()))
        # 4
        protocol.data_received(response)
        response = protocol.transport.read()
        with self.assertRaises(ValueError):
            protocol.transport.read(close_check=True)
        protocol.transport = utils.Socket()
        self.assertEqual(protocol.ENTRIES, response.decode().splitlines()[0])
        self.assertEqual(3, len(response.decode().splitlines()))
        self.assertEqual(protocol.CLOSE, response.decode().splitlines()[-1])
        # 5
        protocol_b.data_received(response)
        with self.assertRaises(ValueError):
            protocol_b.transport.read(close_check=True)
        self.assertEqual(self.log.print_tree(), self.log_b.print_tree())
        self.assertDictEqual(protocol.merkle, protocol_b.merkle)
        
        # delete
        dnode = self.view.delete(path)
        protocol.update_merkle(dnode.entry)
        request = protocol_b.initial_request()
        # 2
        protocol.data_received(request)
        response = protocol.transport.read()
        protocol.transport = utils.Socket()
        self.assertEqual(protocol.LS, response.decode().splitlines()[0])
        self.assertEqual('*/ ' + self.log.root.hash, response.decode().splitlines()[1])
        # 3
        protocol_b.data_received(response)
        response = protocol_b.transport.read()
        protocol_b.transport = utils.Socket()
        self.assertEqual(protocol.LS, response.decode().splitlines()[0])
        self.assertEqual('*%s %s' % (path, node.entry.hash), response.decode().splitlines()[1])
        self.assertEqual(2, len(response.decode().splitlines()))
        # 4 
        protocol.data_received(response)
        response = protocol.transport.read()
        with self.assertRaises(ValueError):
            protocol.transport.read(close_check=True)
        protocol.transport = utils.Socket()
        self.assertEqual(protocol.ENTRIES, response.decode().splitlines()[0])
        self.assertEqual(3, len(response.decode().splitlines()))
        self.assertEqual(protocol.CLOSE, response.decode().splitlines()[-1])
        # 5
        protocol_b.data_received(response)
        with self.assertRaises(ValueError):
            protocol_b.transport.read(close_check=True)
        self.assertEqual(self.log.print_tree(), self.log_b.print_tree())
        self.assertDictEqual(protocol.merkle, protocol_b.merkle)
        
    def test_sync_reverse(self):
        # Reverse communication
        protocol, protocol_b = self.init()
        path = os.path.join(os.sep, 'home-' + utils.random_ascii())
        node = self.view.mkdir(path)
        protocol.update_merkle(node.entry)
        # 1
        request = protocol.initial_request()
        # 2
        protocol_b.data_received(request)
        response = protocol_b.transport.read()
        protocol_b.transport = utils.Socket()
        self.assertEqual(protocol.LS, response.decode().splitlines()[0])
        self.assertEqual('*/ ' + self.log.root.hash, response.decode().splitlines()[1])
        # 3
        protocol.data_received(response)
        with self.assertRaises(ValueError):
            protocol.transport.read(close_check=True)
        response = protocol.transport.read()
        self.assertEqual(protocol.ENTRIES, response.decode().splitlines()[0])
        self.assertEqual(3, len(response.decode().splitlines()))
        self.assertEqual(protocol.CLOSE, response.decode().splitlines()[-1])
        # 4
        protocol_b.data_received(response)
        with self.assertRaises(ValueError):
            protocol_b.transport.read(close_check=True)
        with self.assertRaises(ValueError):
            protocol.transport.read(close_check=True)
        self.assertEqual(self.log.print_tree(), self.log_b.print_tree())
        self.assertDictEqual(protocol.merkle, protocol_b.merkle)
        
        # delete
        dnode = self.view.delete(path)
        protocol.update_merkle(dnode.entry)
        request = protocol.initial_request()
        # 2
        protocol_b.data_received(request)
        response = protocol_b.transport.read()
        protocol_b.transport = utils.Socket()
        self.assertEqual(protocol.LS, response.decode().splitlines()[0])
        self.assertEqual('*/ ' + self.log.root.hash, response.decode().splitlines()[1])
        # 3
        protocol.data_received(response)
        response = protocol.transport.read()
        protocol.transport = utils.Socket()
        self.assertEqual(protocol.LS, response.decode().splitlines()[0])
        self.assertEqual('*%s %s %s' % (path, node.entry.hash, dnode.entry.hash), response.decode().splitlines()[1])
        self.assertEqual(2, len(response.decode().splitlines()))
        # 4 
        protocol_b.data_received(response)
        response = protocol_b.transport.read()
        protocol_b.transport = utils.Socket()
        self.assertEqual(protocol.ENTRY_REQ, response.decode().splitlines()[0])
        self.assertEqual(dnode.entry.hash, response.decode().splitlines()[1])
        # 5
        protocol.data_received(response)
        response = protocol.transport.read()
        with self.assertRaises(ValueError):
            protocol.transport.read(close_check=True)
        protocol.transport = utils.Socket()
        self.assertEqual(protocol.ENTRIES, response.decode().splitlines()[0])
        self.assertEqual(protocol.CLOSE, response.decode().splitlines()[-1])
        self.assertEqual(3, len(response.decode().splitlines()))
        # BAD request
        before = self.log.print_tree()
        protocol.data_received(response)
        self.assertEqual(before, self.log.print_tree())
        # 6
        protocol_b.data_received(response)
        with self.assertRaises(ValueError):
            protocol_b.transport.read(close_check=True)
        self.assertDictEqual(protocol.merkle, protocol_b.merkle)
        self.assertEqual(self.log.print_tree(), self.log_b.print_tree())
