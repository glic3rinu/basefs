import os
import sys
import errno
import stat

from fuse import FuseOSError, Operations
from serfclient.client import SerfClient

from .logs import Log
from .views import View


class FileSystem(Operations):
    def __init__(self, logpath, keypath):
        self.logpath = logpath
        self.log = Log(logpath)
        self.view = View(self.log)
        self.load()
        self.serf = SerfClient()
        node = self.get_node('/.cluster')
        type(self.log).serf = self.serf
        for line in node.entry.decode().splitlines():
            ip = line.strip()
            if ip:
                result = self.serf.join(line.strip())
                if not result.head[b'Error']:
                    break
        else:
            raise RuntimeError("Couldn't connect to serf cluster.")
    
    def load(self):
        print('load')
        self.log_mtime = os.stat(self.logpath).st_mtime
        self.log.load()
        self.view.build()
        self.log.set_key(Key.load(self.keypath))
    
    def get_node(self, path):
        # check if logfile has been modified
        mtime = os.stat(self.logpath).st_mtime
        if mtime != self.log_mtime:
            self.load()
        path = os.path.normpath(path)
        return self.view.paths[path]
    
    def access(self, path, mode):
        print('access', path, mode)
        return super(FileSystem, self).access(path, mode)
#        full_path = self._full_path(path)
#        if not os.access(full_path, mode):
#            raise FuseOSError(errno.EACCES)

#    def chmod(self, path, mode):
#        full_path = self._full_path(path)
#        return os.chmod(full_path, mode)

#    def chown(self, path, uid, gid):
#        full_path = self._full_path(path)
#        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        print('getattr', path)
        try:
            node = self.get_node(path)
        except KeyError:
            raise FuseOSError(errno.ENOENT)
        if node.entry.action == node.entry.MKDIR:
            mode = stat.S_IFDIR | 0o0750
        else:
            mode = stat.S_IFREG | 0o0640
        return {
            'st_atime': node.entry.time,
            'st_ctime': node.entry.ctime,
            'st_gid': os.getgid(),
            'st_mode': mode, 
            'st_mtime': node.entry.time, 
            'st_nlink': 1,
            'st_size': len(node.entry.content),
            'st_uid': os.getuid(),
        }
        
#        full_path = self._full_path(path)
#        st = os.lstat(full_path)
#        return dict((key, getattr(st, key)) for key in ())

    def readdir(self, path, fh):
        print('readdir')
        node = self.get_node(path)
        dirs = ['.', '..']
        for d in itertools.chain(dirs, [os.path.basename(child.entry.path) for child in node.childs]):
            yield d

    def readlink(self, path):
        print('readlink', path)
#        pathname = os.readlink(self._full_path(path))
#        if pathname.startswith("/"):
#            # Path name is absolute, sanitize it.
#            return os.path.relpath(pathname, self.root)
#        else:
#            return pathname

    def mknod(self, path, mode, dev):
        print('mknod', path, mode, dev)
        raise NotImplementedError
#        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        print('rmdir', path)
        node = self.get_node(path)
        return node.delete()

    def mkdir(self, path, mode):
        print('mkdir', path, mode)
        parent_node = self.get_node(os.path.dirname(path))
        return parent_node.mkdir(os.path.normpath(path))

    def statfs(self, path):
        print('statfs', path)
#        full_path = self._full_path(path)
#        stv = os.statvfs(full_path)
#        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
#            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
#            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        print('unlink', path)
#        return os.unlink(self._full_path(path))

    def symlink(self, name, target):
        print('symlink', name, target)
#        return os.symlink(name, self._full_path(target))

    def rename(self, old, new):
        print('rename', old, new)
#        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        print('link', target, name)
#        return os.link(self._full_path(target), self._full_path(name))

    def utimens(self, path, times=None):
        print('utimes', path, times)
#        return os.utime(self._full_path(path), times)

#    # File methods
#    # ============

    def open(self, path, flags):
        print('open', path, flags)
        node = self.get_node(path)
        return uuid.UUID(node.entry.id).int
        
#        full_path = self._full_path(path)
#        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        print('create', path, mode, fi)
        node = self.get_node(os.path.dirname(path))
        node.create(path)
        return 1
#        full_path = self._full_path(path)
#        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        print('read', path, length, offset, fh)
        node = self.get_node(path)
        return node.entry.decode()
        return node.read(length, offset, fh)

    def write(self, path, buf, offset, fh):
        print('write', path, buf, offset, fh)
        node = self.get_node(path)
        node.write(buf)
        # TODO seek
        # TODO FS.get_path() and do os.path.normpath there

    def truncate(self, path, length, fh=None):
        print('truncate', path, length, fh)
#        full_path = self._full_path(path)
#        with open(full_path, 'r+') as f:
#            f.truncate(length)

    def flush(self, path, fh):
        print('flush', path, fh)
        return 0
#        return os.fsync(fh)

    def release(self, path, fh):
        print('release', path, fh)
        return fh
#        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        print('fsync', path, fdatasync, fh)
#        return self.flush(path, fh)
