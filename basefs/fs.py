import os
import sys
import errno
import itertools
import logging
import stat
import threading

from fuse import FuseOSError, Operations

from . import exceptions, utils
from .keys import Key
from .logs import Log
from .views import View


logger = logging.getLogger('basefs.fs')


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
    def __init__(self, view, serf=None):
        self.serf = serf
        self.view = view
        self.cache = {}
        self.dirty = {}
        self.loaded = view.log.loaded
    
    def __call__(self, op, path, *args):
        logger.debug('-> %s %s %s', op, path, repr(args))
        ret = '[Unhandled Exception]'
        try:
            ret = getattr(self, op)(path, *args)
            return ret
        except OSError as e:
            ret = str(e)
            raise
        finally:
            logger.debug('<- %s %s', op, repr(ret))
    
    def get_node(self, path):
        # check if logfile has been modified
        if self.loaded != self.view.log.loaded:
            self.view.build()
            self.loaded = self.view.log.loaded
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
        try:
            content = self.cache[path]
        except KeyError:
            node = self.get_node(path)
            has_perm = bool(self.view.get_key(path))
            if node.entry.action == node.entry.MKDIR:
                mode = stat.S_IFDIR | (0o0750 if has_perm else 0o0550)
            else:
                mode = stat.S_IFREG | (0o0640 if has_perm else 0o0440)
            return {
                'st_atime': node.entry.timestamp,
                'st_ctime': node.entry.ctime,
                'st_gid': os.getgid(),
                'st_mode': mode, 
                'st_mtime': node.entry.timestamp,
                'st_nlink': 1,
                'st_size': len(node.content),
                'st_uid': os.getuid(),
            }
        else:
            import time
            return {
                'st_atime': time.time(),
                'st_ctime': time.time(),
                'st_gid': os.getgid(),
                'st_mode': stat.S_IFREG | 0o0640,
                'st_mtime': time.time(),
                'st_nlink': 1,
                'st_size': len(content),
                'st_uid': os.getuid(),
            }
        

        
#        full_path = self._full_path(path)
#        st = os.lstat(full_path)
#        return dict((key, getattr(st, key)) for key in ())

    def readdir(self, path, fh):
        node = self.get_node(path)
        entry = node.entry
        dirs = ['.', '..']
        for d in itertools.chain(dirs, [child.entry.name for child in node.childs if child.entry.action not in (entry.DELETE, entry.GRANT, entry.REVOKE)]):
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
        id = int(node.entry.hash, 16)
        if path not in self.cache:
            self.cache[path] = node.content
            self.dirty[path] = False
        return id

    def create(self, path, mode, fi=None):
        self.cache[path] = b''
        self.dirty[path] = True
        return id(path)

    def read(self, path, length, offset, fh):
        try:
            content = self.cache[path]
        except KeyError:
            node = self.get_node(path)
            content = node.content
        print(length, offset, content[offset:length])
        return content[offset:offset+length]

    def write(self, path, buf, offset, fh):
        try:
            content = self.cache[path]
        except KeyError:
            node = self.get_node(path)
            content = node.content
        size = len(buf)
        new_content = content[:offset] + buf + content[offset+size:]
        if content != new_content:
            self.dirty[path] = True
            self.cache[path] = new_content
        return size
    
    def truncate(self, path, length, fh=None):
        self.cache[path] = self.cache[path][:length]
        self.dirty[path] = True
    
#    def flush(self, path, fh):
#        # TODO Filesystems shouldn't assume that flush will always be called after some writes, or that if will be called at all.
#        content = self.cache.pop(path, None)
#        dirty = self.dirty.pop(path, False)
#        if content is not None and dirty:
#            print('write')
#            node = self.view.write(path, content)
##            self.send(node)
    
    def release(self, path, fh):
        content = self.cache.pop(path, None)
        dirty = self.dirty.pop(path, False)
        if content is not None and dirty:
            print('write')
            node = self.view.write(path, content)
            self.send(node)

#    def fsync(self, path, fdatasync, fh):
#        return self.flush(path, fh)
#        return None
