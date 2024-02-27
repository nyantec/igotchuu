from setuptools import setup, find_packages

setup(
    name='igotchuu',
    version='0.1.0',
    packages=find_packages(),
    install_requires=['pygobject', 'click', 'python-unshare', 'btrfsutil'],
    entry_points={
        'console_scripts': ['igotchuu=igotchuu:cli']
    }
)
