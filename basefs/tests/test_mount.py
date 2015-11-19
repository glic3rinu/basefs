import shutil
import tempfile
import time
import os
import random
import subprocess
import unittest

from basefs.keys import Key
from basefs.logs import Log

from . import utils


class MountTests(unittest.TestCase):
    def setUp(self):
        __, self.logpath = tempfile.mkstemp()
        __, self.logpath_b = tempfile.mkstemp()
        self.addCleanup(os.remove, self.logpath)
        self.addCleanup(os.remove, self.logpath_b)
        __, self.keypath = tempfile.mkstemp()
        self.addCleanup(os.remove, self.keypath)
        self.port = random.randint(40000, 50000-1)
        self.port_b = random.randint(50000, 60000)
        
        log = Log(self.logpath)
        root_key = Key.generate()
        log.bootstrap([root_key], ['127.0.0.1:%i' % self.port])
        root_key.save(self.keypath)
        shutil.copy2(self.logpath, self.logpath_b)
        self.hostname = utils.random_ascii(10)
        self.hostname_b = utils.random_ascii(10)
        self.mountpath = tempfile.mkdtemp()
        self.mountpath_b = tempfile.mkdtemp()
        context = {
            'mountpath': self.mountpath,
            'logpath': self.logpath,
            'keypath': self.keypath,
            'port': self.port,
            'hostname': self.hostname,
        }
        cmd = 'basefs mount %(logpath)s %(mountpath)s -k %(keypath)s -p %(port)s -n %(hostname)s'
        proc = subprocess.Popen(cmd % context, shell=True)
        self.addCleanup(proc.kill)
        time.sleep(1)
        self.addCleanup(proc.kill)
        context.update({
            'mountpath': self.mountpath_b,
            'logpath': self.logpath_b,
            'port': self.port_b,
            'hostname': self.hostname_b,
        })
        proc = subprocess.Popen(cmd % context, shell=True)
        self.addCleanup(proc.kill)
        self.addCleanup(time.sleep, 1)
        self.addCleanup(proc.kill)
        self.addCleanup(shutil.rmtree, self.mountpath)
        self.addCleanup(shutil.rmtree, self.mountpath_b)
        time.sleep(1)
    
    def test_mount(self):
        pass
