from setuptools import setup, find_packages

setup(name='igotchuu',
      version='0.1.0',
      packages=find_packages(),
      scripts=["scripts/igotchuu"],
      install_requires=['pygobject']
     )
