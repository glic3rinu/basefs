from distutils.core import setup


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
)


