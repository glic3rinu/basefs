import os
import tempfile
import time
import unittest
from multiprocessing import Process

from fuse import FUSE

from basefs.fs import FileSystem
from basefs.logs import Log
from basefs.tests import utils


class FSTests(unittest.TestCase):
    def setUp(self):
        __, self.logpath = tempfile.mkstemp()
        __, self.keypath = tempfile.mkstemp()
        self.mountpoint = tempfile.mkdtemp()
        __, self.root_key = utils.bootstrap(self.logpath)
        self.root_key.save(self.keypath)
        self.fs = FileSystem(self.logpath, self.keypath, serf=False)
        self.process = Process(target=lambda: FUSE(self.fs, self.mountpoint, nothreads=True, foreground=True))
        self.process.start()
        time.sleep(0.01)
    
    def tearDown(self):
        self.process.terminate()
        self.process.join()
        os.remove(self.logpath)
        os.remove(self.keypath)
        os.rmdir(self.mountpoint)
    
    def full_path(self, path):
        return os.path.join(self.mountpoint, path)
    
    def test_mount(self):
        self.assertEqual(set(('.keys', '.cluster')), set(os.listdir(self.mountpoint)))
    
    def test_mkdir(self):
        home_path = 'home-' + utils.random_ascii()
        os.mkdir(self.full_path(home_path))
        self.assertEqual(set(('.keys', '.cluster', home_path)), set(os.listdir(self.mountpoint)))
        user_path = os.path.join(home_path, 'user-' + utils.random_ascii())
        with self.assertRaises(FileExistsError):
            os.mkdir(self.full_path(home_path))
        os.mkdir(self.full_path(user_path))
        self.assertEqual(set(('.keys', '.cluster', home_path)), set(os.listdir(self.mountpoint)))
        self.assertEqual([os.path.basename(user_path)], os.listdir(self.full_path(home_path)))
    
    def test_write(self):
        file_path = 'file-' + utils.random_ascii()
        file_content = 'content-' + utils.random_ascii()
        with open(self.full_path(file_path), 'w') as handler:
            handler.write(file_content)
        self.assertEqual(set(('.keys', '.cluster', file_path)), set(os.listdir(self.mountpoint)))
        with open(self.full_path(file_path), 'r') as handler:
            self.assertEqual(file_content, handler.read())
        # Update
        alt_file_content = 'content-' + utils.random_ascii()
        with open(self.full_path(file_path), 'w') as handler:
            handler.write(alt_file_content)
        with open(self.full_path(file_path), 'r') as handler:
            self.assertEqual(alt_file_content, handler.read())
    
    def test_delete(self):
        # RMDIR
        home_path = 'home-' + utils.random_ascii()
        os.mkdir(self.full_path(home_path))
        self.assertEqual(set(('.keys', '.cluster', home_path)), set(os.listdir(self.mountpoint)))
        os.rmdir(self.full_path(home_path))
        self.assertEqual(set(('.keys', '.cluster')), set(os.listdir(self.mountpoint)))
        # RMFILE
        home_path = 'home-' + utils.random_ascii()
        os.mkdir(self.full_path(home_path))
        file_path = os.path.join(home_path, 'file-' + utils.random_ascii())
        file_content = 'content-' + utils.random_ascii()
        with open(self.full_path(file_path), 'w') as handler:
            handler.write(file_content)
        with open(self.full_path(file_path), 'r') as handler:
            self.assertEqual(file_content, handler.read())
        os.remove(self.full_path(file_path))
        with self.assertRaises(FileNotFoundError):
            os.stat(self.full_path(file_path))
        self.assertEqual([], os.listdir(self.full_path(home_path)))
        with self.assertRaises(FileNotFoundError):
            with open(self.full_path(file_path), 'r') as handler:
                handler.read()
        with open(self.full_path(file_path), 'w') as handler:
            handler.write(file_content)
        self.assertEqual([os.path.basename(file_path)], os.listdir(self.full_path(home_path)))
        os.rmdir(self.full_path(home_path))
        with self.assertRaises(FileNotFoundError):
            os.stat(self.full_path(file_path))
        with self.assertRaises(FileNotFoundError):
            os.stat(self.full_path(home_path))
