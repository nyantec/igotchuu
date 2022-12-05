from setuptools import setup, find_packages

setup(name='igotchuu',
      version='0.1.0',
      # Modules to import from other scripts:
      packages=["igotchuu"],
      package_dir={"igotchuu": "src/igotchuu"},
      # Executables
      scripts=["igotchuu"],
      install_requires=['pygobject']
     )
