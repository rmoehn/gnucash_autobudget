# -*- coding: utf-8 -*-

# Credits: https://python-packaging.readthedocs.io/en/latest/minimal.html

from __future__ import print_function, unicode_literals

import sys

from setuptools import setup
from setuptools.command.install import install


# Credits: http://blog.niteoweb.com/setuptools-run-custom-code-in-setup-py/
class CheckExtDepsInstallCommand(install):
    """
    Install command checking GnuCash Python bindings dependency

    The GnuCash Python bindings are neither available from PyPi nor can they be
    installed from a repo or similar source compatible with Setuptools. This
    subclass makes the install command check whether the user has installed the
    GnuCash Python bindings herself before installing this Python package.
    """

    def run(self):
        try:
            import gnucash.gnucash_core # pylint: disable=unused-variable
        except ImportError:
            print("It looks like the GnuCash Python Bindings are not installed"
                  " on your system, but you need them in order to use"
                  " gnucash_autobudget. For installation instructions, see"
                  " http://wiki.gnucash.org/wiki/Python_Bindings.",
                  file=sys.stdout)
            sys.exit(1)

        install.run(self)


setup(name='gnucash_autobudget',
      version='0.1.0',
      description="Automatically adjust GnuCash transactions for envelope budgeting",
      url="https://github.com/rmoehn/gnucash_autobudget",
      author="Richard Möhn",
      author_email="richard.moehn@posteo.de",
      license="MIT",
      zip_safe=True,
      cmdclass={ 'install': CheckExtDepsInstallCommand },
)
