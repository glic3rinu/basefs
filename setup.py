import os
import sys
from distutils.spawn import find_executable
from setuptools import setup
from setuptools.command.install import install as _install


def install_serf(self):
    serf_path = find_executable('serf')
    if not serf_path:
        os.system('basefs installserf %s' % self.install_scripts)
    else:
        sys.stdout.write("Serf is already installed in %s\n" % serf_path)


class install(_install):
    def run(self):
        super().run()
        self.execute(install_serf, [self], msg="Installing serf ...")


setup(
    name = 'basefs',
    packages = [
        'basefs',
        'basefs/management'
    ],
    version = '0.7',
    description = 'Basically Available, Soft state, Eventually consistent File System',
    scripts=[
        'basefs/bin/basefs',
    ],
    author = 'Marc Aymerich',
    author_email = 'glicerinu@gmail.com',
    url = 'http://github.com/glic3rinu/basefs',
    download_url = 'http://github.com/glic3rinu/basefs/tarball/master#egg=basefs',
    keywords = [
        'filesystem',
        'decentralized',
        'distributed'
    ],
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: System :: Networking',
        'Topic :: System :: Filesystems',
        'Topic :: System :: Distributed Computing',
    ],
    install_requires = [
        'ecdsa',
        'fusepy',
        'serfclient',
        'bsdiff4',
    ],
    cmdclass={
        'install': install,
    },
)
