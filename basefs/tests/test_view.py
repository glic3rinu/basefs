import os
import tempfile
import unittest

from fuse import FUSE

from basefs import exceptions
from basefs.keys import Key
from basefs.logs import LogEntry
from basefs.views import View

from . import utils


class ViewTests(unittest.TestCase):
    def setUp(self):
        __, self.logpath = tempfile.mkstemp()
        self.log, self.root_key = utils.bootstrap(self.logpath)
        self.log.load()
    
    def tearDown(self):
        os.remove(self.logpath)
    
    def test_build(self):
        view = View(self.log, self.root_key)
        view.build()
        path = '/.cluster'
        self.assertEqual('127.0.0.1\n', view.get(path).entry.content)
    
    def test_mkdir(self):
        view = View(self.log, self.root_key)
        view.build()
        path = '/home'
        view.mkdir(path)
        self.assertEqual(LogEntry.MKDIR, view.paths.get(path).entry.action)
        path = '/home/pangea'
        view.mkdir(path)
        self.assertEqual(LogEntry.MKDIR, view.get(path).entry.action)
        path = '/home/does/not'
        with self.assertRaises(exceptions.DoesNotExist):
            view.mkdir(path)
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(path)
        # Reload
        view.build()
        path = '/home'
        self.assertEqual(LogEntry.MKDIR, view.get(path).entry.action)
        path = '/home/pangea'
        self.assertEqual(LogEntry.MKDIR, view.get(path).entry.action)
        path = '/home/does/not'
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(path)
    
    def test_permission(self):
        key = Key.generate()
        view = View(self.log, key)
        view.build()
        path = '/home'
        with self.assertRaises(exceptions.PermissionDenied):
            view.mkdir(path)
    
    def test_write(self):
        view = View(self.log, self.root_key)
        view.build()
        path = '/test'
        content = utils.random_ascii()
        view.write(path, content)
        self.assertEqual(LogEntry.WRITE, view.get(path).entry.action)
        self.assertEqual(content, view.get(path).entry.content)
        # TODO move all reload sections into test_build()
        # Reload
        view.build()
        self.assertEqual(content, view.get(path).entry.content)
    
    def test_delete(self):
        view = View(self.log, self.root_key)
        view.build()
        # Delete File
        path = '/test'
        content = utils.random_ascii()
        view.write(path, content)
        self.assertEqual(LogEntry.WRITE, view.get(path).entry.action)
        self.assertEqual(content, view.get(path).entry.content)
        view.delete(path)
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(path)
        # Reload
        view.reload()
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(path)
        # Delete Dir
        home_path = '/home'
        view.mkdir(home_path)
        self.assertEqual(LogEntry.MKDIR, view.paths.get(home_path).entry.action)
        view.delete(home_path)
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(home_path)
        pangea_path = '/home/pangea'
        with self.assertRaises(exceptions.DoesNotExist):
            view.mkdir(pangea_path)
        # Nested Dir
        view.mkdir(home_path)
        view.mkdir(pangea_path)
        view.delete(home_path)
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(pangea_path)
            view.get(home_path)
        view.build()
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(pangea_path)
            view.get(home_path)
    
    def test_grant(self):
        view = View(self.log, self.root_key)
        view.build()
        home_path = '/home'
        view.mkdir(home_path)
        key = Key.generate()
        view.grant(home_path, key)
        # Change key
        view = View(self.log, key)
        view.build()
        content = utils.random_ascii()
        file_path = '/hola'
        with self.assertRaises(exceptions.PermissionDenied):
            view.write(file_path, content)
        pangea_path = os.path.join(home_path, 'pangea')
        view.mkdir(pangea_path)
        self.assertEqual(LogEntry.MKDIR, view.get(pangea_path).entry.action)
        file_path = os.path.join(pangea_path, 'file')
        content = utils.random_ascii()
        view.write(file_path, content)
        self.assertEqual(content, view.get(file_path).entry.content)
    
    def test_revoke(self):
        view = View(self.log, self.root_key)
        view.build()
        home_path = '/home'
        view.mkdir(home_path)
        key = Key.generate()
        view.grant(home_path, key)
#        print(view.get_keys())
        
