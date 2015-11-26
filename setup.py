import os
import sys

from distutils.spawn import find_executable
from setuptools import setup
from setuptools.command.install import install as _install


def install_serf(self):
    serf_path = find_executable('serf')
    print(dir(self.install_scripts))
    print(str(self.install_scripts.__dict__))
    if not serf_path:
        os.system('basefs installserf %s' % self.script_dir)
    else:
        sys.stdout.write("Serf is already installed in %s\n" % serf_path)


class install(_install):
    def run(self):
        super().run()
        self.execute(install_serf, [self], msg="Installing serf ...")


setup(
    name = 'basefs',
    packages = ['basefs'],
    version = '0.5.4',
    description = 'Basically Available, Soft state, Eventually consistent File System',
    scripts=[
        'basefs/bin/basefs',
    ],
    author = 'Marc Aymerich',
    author_email = 'glicerinu@gmail.com',
    url = 'http://github.com/glic3rinu/basefs/tarball/master#egg=basefs',
    download_url = 'https://github.com/glic3rinu/basefs/archive/master.zip',
    keywords = ['filesystem', 'decentralized', 'distributed'],
    classifiers = [],
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
