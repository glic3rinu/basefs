import os
import tempfile
import unittest

from . import utils


class LogTests(unittest.TestCase):
    def setUp(self):
        __, self.logpath = tempfile.mkstemp()
    
    def tearDown(self):
        os.remove(self.logpath)
    
    def test_bootstrap(self):
        self.log, __ = utils.bootstrap(self.logpath)
        with open(self.logpath, 'r') as logfile:
            self.assertEqual(3, len(logfile.readlines()))
    
    def test_load(self):
        self.log, __ = utils.bootstrap(self.logpath)
        self.log.load()
        self.assertEqual(3, len(self.log.entries))
