import os
import sys
import errno
import itertools
import logging
import stat

from fuse import FuseOSError, Operations

from . import exceptions, utils
from .keys import Key
from .logs import Log
from .messages import SerfClient
from .views import View


class ViewToErrno():
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc, exc_tb):
        if exc_type is exceptions.PermissionDenied:
            raise FuseOSError(errno.EACCES)
        if exc_type is exceptions.DoesNotExist:
            raise FuseOSError(errno.ENOENT)
        if exc_type is exceptions.Exists:
            raise FuseOSError(errno.EEXIST)


class FileSystem(Operations):
    logger = logging.getLogger('basefs.fs')
    
    def __init__(self, logpath, keypath, serf=True, loglevel=logging.DEBUG):
        logging.basicConfig(level=loglevel)
        self.logpath = os.path.normpath(logpath)
        self.log = Log(logpath)
        self.key = Key.load(keypath)
        self.view = View(self.log, self.key)
        self.logupdated = logpath + '.updated'
        utils.touch(self.logupdated)
        self.operations = {}
        self.load()
        self.serf = None
        if serf:
            self.serf = SerfClient(self.log)
            node = self.get_node('/.cluster')
            type(self.log).serf = self.serf
            for line in node.entry.content.splitlines():
                ip = line.strip()
                if ip:
                    result = self.serf.join(line.strip())
                    if not result.head[b'Error']:
                        break
            else:
                raise RuntimeError("Couldn't connect to serf cluster.")
    
    def __call__(self, op, path, *args):
        self.logger.debug('-> %s %s %s', op, path, repr(args))
        ret = '[Unhandled Exception]'
        try:
            ret = getattr(self, op)(path, *args)
            return ret
        except OSError as e:
            ret = str(e)
            raise
        finally:
            self.logger.debug('<- %s %s', op, repr(ret))
    
    def load(self):
        self.log_mtime = os.stat(self.logupdated).st_mtime
        self.log.load()
        self.view.build()
    
    def get_node(self, path):
        # check if logfile has been modified
        mtime = os.stat(self.logupdated).st_mtime
        if mtime != self.log_mtime:
            self.load()
        with ViewToErrno():
            node = self.view.get(path)
        if node.entry.action == node.entry.DELETE:
            raise FuseOSError(errno.ENOENT)
        return node
    
    def send(self, node):
        if self.serf:
            self.serf.send(node.entry)
    
#    def access(self, path, mode):
#        return super(FileSystem, self).access(path, mode)
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
        node = self.get_node(path)
        has_perm = bool(self.view.get_key(path))
        if node.entry.action == node.entry.MKDIR:
            mode = stat.S_IFDIR | (0o0750 if has_perm else 0o0550)
        else:
            mode = stat.S_IFREG | (0o0640 if has_perm else 0o0440)
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
        node = self.get_node(path)
        dirs = ['.', '..']
        for d in itertools.chain(dirs, [os.path.basename(child.entry.path) for child in node.childs if child.entry.action != child.entry.DELETE]):
            yield d

#    def readlink(self, path):
#        pathname = os.readlink(self._full_path(path))
#        if pathname.startswith("/"):
#            # Path name is absolute, sanitize it.
#            return os.path.relpath(pathname, self.root)
#        else:
#            return pathname

    def mknod(self, path, mode, dev):
        raise NotImplementedError

    def rmdir(self, path):
        with ViewToErrno():
            node = self.view.delete(path)
        self.send(node)

    def mkdir(self, path, mode):
        with ViewToErrno():
            node = self.view.mkdir(path)
        self.send(node)
        return 0

#    def statfs(self, path):
#        full_path = self._full_path(path)
#        stv = os.statvfs(full_path)
#        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
#            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
#            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        with ViewToErrno():
            node = self.view.delete(path)
        self.send(node)
#        return os.unlink(self._full_path(path))

#    def symlink(self, name, target):
#        return os.symlink(name, self._full_path(target))

    def rename(self, old, new):
        raise NotImplementedError

#    def link(self, target, name):
#        return os.link(self._full_path(target), self._full_path(name))

#    def utimens(self, path, times=None):
#        return os.utime(self._full_path(path), times)

#    # File methods
#    # ============

    def open(self, path, flags):
        node = self.get_node(path)
        return int(node.entry.hash, 16)

    def create(self, path, mode, fi=None):
        node = self.view.write(path, '', commit=False)
        return node.entry.hash

    def read(self, path, length, offset, fh):
        node = self.get_node(path)
        return node.entry.content.encode()[offset:length+1]

    def write(self, path, buf, offset, fh):
        size = len(buf)
        content = buf.decode()
        node = self.get_node(path)
        if offset:
            entry = node.entry
            content = entry.content[:offset] + content + entry.content[offset+size:]
        if not node.entry.signature:
            node.entry.content = content
        else:
            with ViewToErrno():
                self.view.write(path, content, commit=False)
        return size
    
    def truncate(self, path, length, fh=None):
        """ not implemented because every time ther is a file.write() a truncate(0) is issued """
        pass
    
    def flush(self, path, fh):
        # TODO Filesystems shouldn't assume that flush will always be called after some writes, or that if will be called at all.
        node = self.get_node(path)
        if not node.entry.signature:
            node.entry.sign()
            node.entry.save()
            self.send(node)
    
#    def release(self, path, fh):
#        return None
#        return os.close(fh)

#    def fsync(self, path, fdatasync, fh):
#        return self.flush(path, fh)
#        return None
