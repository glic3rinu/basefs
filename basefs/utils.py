import os
import subprocess


class Candidate(object):
    def __init__(self, score, entry):
        self.score = score
        self.entry = entry
    
    def __gt__(self, candidate):
        """ self better than candidate """
        return (
            self.score > candidate.score or (
                self.score == candidate.score and self.entry.hash > candidate.entry.hash)
        )


def is_subdir(path, directory):
    path = os.path.realpath(path)
    directory = os.path.realpath(directory)
    relative = os.path.relpath(path, directory)
    if relative.startswith(os.pardir):
        return False
    else:
        return True


def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)


def get_mounted_logpath():
    path = os.getcwd()
    while path != os.sep:
        if os.path.ismount(path):
            mount = subprocess.Popen('mount', stdout=subprocess.PIPE)
            mount.wait()
            for line in mount.stdout.readlines():
                logpath, __, mountpoint = line.split()[:3]
                if path == mountpoint.decode():
                    return logpath.decode()
            return
        path = os.path.abspath(os.path.join(path, os.pardir))
