import logging
import multiprocessing
import os
import subprocess

from basefs.logs import LogEntry


logger = logging.getLogger('basefs.sync')


class Handler:
    SAFE_VARS = (
        'PATH',
        'SHELL',
        'USER',
        'HOME',
        'TERM',
        'DISPLAY',
    )
    def __init__(self, script, log, state=None):
        self.script = script
        self.state = state
        self.log = log
        if state:
            state.post_change.connect(self.process_post_change)
        log.post_save.connect(self.process_post_save)
    
    def run_script(self, action, path):
        env = {var: os.environ.get(var, '') for var in self.SAFE_VARS}
        env.update({
            'BASEFS_EVENT_TYPE': action,
            'BASEFS_EVENT_PATH': path,
        })
        p = subprocess.Popen(self.script, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env)
        return_code = p.wait()
        if return_code != 0:
            stderr = p.stderr.read().decode()
            logger.error("Error invoking watcher script '%s', exit status: %s, stderr: '%s'",
                         self.script, return_code, stderr)
        stdout = p.stdout.read()
        if stdout:
            logger.debug("Watcher script '%s' output: %s", self.script, stdout.decode())
    
    def notify(self, action, path):
        script = multiprocessing.Process(target=self.run_script, args=(action, path))
        script.start()
    
    def process_post_save(self, entry):
        if isinstance(entry, LogEntry) and entry.action != entry.WRITE:
            self.notify(entry.action, entry.path)
    
    def process_post_change(self, entry, pre, post):
        if post == self.state.COMPLETED:
            self.notify(entry.action, entry.path)
