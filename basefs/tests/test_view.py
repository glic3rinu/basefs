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
    
    def rebuild(self, view):
        prev = view.paths
        prev_str = str(view.root)
        view.build()
        for path, node in view.paths.items():
            self.assertEqual(prev.pop(path).entry, node.entry)
        self.assertEqual({}, prev)
        self.assertEqual(len(prev_str), len(str(view.root)))  # len() is used becuase of random dict ordering
        
    def test_build(self):
        view = View(self.log, self.root_key)
        view.build()
        path = os.path.join(os.sep, '.cluster')
        self.assertEqual('127.0.0.1\n', view.get(path).entry.content)
    
    def test_mkdir(self):
        view = View(self.log, self.root_key)
        view.build()
        home_path = os.sep + utils.random_ascii()
        view.mkdir(home_path)
        self.assertEqual(LogEntry.MKDIR, view.paths.get(home_path).entry.action)
        user_path = os.path.join(home_path, utils.random_ascii())
        view.mkdir(user_path)
        self.assertEqual(LogEntry.MKDIR, view.get(user_path).entry.action)
        not_path = os.path.join(os.sep, utils.random_ascii(), utils.random_ascii())
        with self.assertRaises(exceptions.DoesNotExist):
            view.mkdir(not_path)
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(not_path)
        self.rebuild(view)
        self.assertEqual(LogEntry.MKDIR, view.get(home_path).entry.action)
        self.assertEqual(LogEntry.MKDIR, view.get(user_path).entry.action)
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(not_path)
    
    def test_permission(self):
        key = Key.generate()
        view = View(self.log, key)
        view.build()
        path = os.path.join(os.sep, utils.random_ascii())
        with self.assertRaises(exceptions.PermissionDenied):
            view.mkdir(path)
    
    def test_write(self):
        view = View(self.log, self.root_key)
        view.build()
        path = os.path.join(os.sep, utils.random_ascii())
        content = utils.random_ascii()
        view.write(path, content)
        self.assertEqual(LogEntry.WRITE, view.get(path).entry.action)
        self.assertEqual(content, view.get(path).entry.content)
        self.rebuild(view)
        self.assertEqual(content, view.get(path).entry.content)
    
    def test_delete(self):
        view = View(self.log, self.root_key)
        view.build()
        # Delete File
        file_path = os.path.join(os.sep, utils.random_ascii())
        content = utils.random_ascii()
        view.write(file_path, content)
        self.assertEqual(LogEntry.WRITE, view.get(file_path).entry.action)
        self.assertEqual(content, view.get(file_path).entry.content)
        view.delete(file_path)
        self.assertEqual(LogEntry.DELETE, view.get(file_path).entry.action)
        # Reload
        self.rebuild(view)
        self.assertEqual(LogEntry.DELETE, view.get(file_path).entry.action)
        # Delete Dir
        home_path = os.path.join(os.sep, utils.random_ascii())
        view.mkdir(home_path)
        self.assertEqual(LogEntry.MKDIR, view.paths.get(home_path).entry.action)
        view.delete(home_path)
        self.assertEqual(LogEntry.DELETE, view.get(home_path).entry.action)
    
    def test_deleted_nested_dir(self):
        view = View(self.log, self.root_key)
        view.build()
        home_path = os.path.join(os.sep, 'home-' + utils.random_ascii())
        user_path = os.path.join(home_path, 'user-' + utils.random_ascii())
        view.mkdir(home_path)
        view.mkdir(user_path)
        view.delete(home_path)
        self.assertEqual(LogEntry.DELETE, view.get(home_path).entry.action)
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(user_path)
        self.rebuild(view)
        self.assertEqual(LogEntry.DELETE, view.get(home_path).entry.action)
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(user_path)
    
    def test_recreate_deleted(self):
        view = View(self.log, self.root_key)
        view.build()
        home_path = os.path.join(os.sep, 'home-' + utils.random_ascii())
        user_path = os.path.join(home_path, 'user-' + utils.random_ascii())
        view.mkdir(home_path)
        view.mkdir(user_path)
        file_path = os.path.join(user_path, utils.random_ascii())
        file_content = utils.random_ascii()
        view.write(file_path, file_content)
        self.assertEqual(file_content, view.get(file_path).entry.content)
        view.delete(home_path)
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(file_path)
        view.mkdir(home_path)
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(file_path)
        with self.assertRaises(exceptions.DoesNotExist):
            view.get(user_path)
        # File
        view.mkdir(user_path)
        new_file_content = utils.random_ascii()
        view.write(file_path, new_file_content)
        self.assertEqual(new_file_content, view.get(file_path).entry.content)
        # Reload
        self.rebuild(view)
        self.assertEqual(new_file_content, view.get(file_path).entry.content)
        view.get(user_path)
        view.delete(file_path)
        new_file_content = utils.random_ascii()
        view.write(file_path, new_file_content)
        self.assertEqual(new_file_content, view.get(file_path).entry.content)
    
    def test_grant(self):
        view = View(self.log, self.root_key)
        view.build()
        home_path = os.path.join(os.sep, utils.random_ascii())
        view.mkdir(home_path)
        key = Key.generate()
        view.grant(home_path, key)
        prev = str(view.root)
        view.build()
        self.assertEqual(len(prev), len(str(view.root)))
        # Change key
        view = View(self.log, key)
        view.build()
        content = utils.random_ascii()
        file_path = os.path.join(os.sep, utils.random_ascii())
        with self.assertRaises(exceptions.PermissionDenied):
            view.write(file_path, content)
        user_path = os.path.join(home_path, utils.random_ascii())
        view.mkdir(user_path)
        self.assertEqual(LogEntry.MKDIR, view.get(user_path).entry.action)
        file_path = os.path.join(user_path, utils.random_ascii())
        content = utils.random_ascii()
        view.write(file_path, content)
        self.assertEqual(content, view.get(file_path).entry.content)
        view = View(self.log, self.root_key)
        view.build()
        view.write(file_path, content)
        self.assertEqual(content, view.get(file_path).entry.content)
        file_path = os.path.join(user_path, utils.random_ascii())
        content = utils.random_ascii()
        view.write(file_path, content)
        self.assertEqual(content, view.get(file_path).entry.content)
        self.rebuild(view)
    
    def test_revoke(self):
        root_view = View(self.log, self.root_key)
        root_view.build()
        home_path = os.path.join(os.sep, 'home-' + utils.random_ascii())
        root_view.mkdir(home_path)
        key = Key.generate()
        root_view.grant(home_path, key)
        
        view = View(self.log, key)
        view.build()
        user_path = os.path.join(home_path, 'user-' + utils.random_ascii())
        view.mkdir(user_path)
        
        root_view.build()
        file_path = os.path.join(user_path, 'file-' + utils.random_ascii())
        file_content = 'content-' + utils.random_ascii()
        root_view.write(file_path, file_content)
        root_view.revoke(home_path, key)
        self.assertEqual(file_content, root_view.get(file_path).entry.content)
        self.assertEqual(file_path, root_view.get(file_path).entry.path)
        view.build()
        alt_file_content = 'content-' + utils.random_ascii()
        with self.assertRaises(exceptions.DoesNotExist):
            view.write(file_path, alt_file_content)
    
    def test_dir_file_exists_conflict(self):
        view = View(self.log, self.root_key)
        view.build()
        path = os.path.join(os.sep, utils.random_ascii())
        content = utils.random_ascii()
        view.write(path, content)
        with self.assertRaises(exceptions.Exists):
            view.mkdir(path)
    
    def test_branch_conflict(self):
        view = View(self.log, self.root_key)
        view.build()
        home_path = os.path.join(os.sep, 'home-' + utils.random_ascii())
        view.mkdir(home_path)
        key = Key.generate()
        view.grant(home_path, key)
        view = View(self.log, key)
        view.build()
        parent_node = view.get(home_path)
        user_path = os.path.join(home_path, 'user-' + utils.random_ascii())
        max_hash = None
        for ix in range(12):
            content = 'content-' + utils.random_ascii(32)
            entry = self.log.write(parent_node.entry, user_path, content, key)
            max_hash = max(max_hash, entry.hash) if max_hash else entry.hash
        view = View(self.log, self.root_key)
        view.build()
        self.assertEqual(self.log.entries[max_hash].content, view.get(user_path).entry.content)
        # Admin branch more power
        content = 'content-' + utils.random_ascii(32)
        self.log.write(parent_node.entry, user_path, content, self.root_key)
        view.build()
        self.assertEqual(content, view.get(user_path).entry.content)
        alt_content = 'content-' + utils.random_ascii(32)
        self.log.write(parent_node.entry, user_path, alt_content, key)
        self.assertEqual(content, view.get(user_path).entry.content)
        # Grant consistency with prev state
        view.grant(os.sep, key)
        self.assertEqual(content, view.get(user_path).entry.content)
        view.build()
        self.assertEqual(content, view.get(user_path).entry.content)
