import os
import sys
from distutils import command, spawn
from distutils.command.install import install as distutil_install
from distutils.core import setup


def install_serf():
    serf_path = spawn.find_executable('serf')
    if not serf_path:
        os.system('basefs installserf')
    else:
        sys.stdout.write("Serf is already installed in %s\n" % serf_path)


class install(distutil_install):
    def run(self):
        print('aaaaaaaaaaaaaaaaaaaaaaaaaaaa')
        super().run()
#        distutil_install.install.run(self)
#        self.execute(install_serf, [], msg="Installing serf")


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
