#!/usr/bin/env python
"""
    RF Front End Control Daemon.
"""

try:
    import setuptools
except ImportError:
    print("=========================================================")
    print(" RFFE Control Daemon requires setuptools for installing  ")
    print(" You can install setuptools using pip:                   ")
    print("    $ pip install setuptools                             ")
    print("=========================================================")
    exit(1)


from setuptools import setup
import rffe_daemon

setup(
    name         = 'RFFE Control Daemon', # This is the name of your PyPI-package.
    version      = __version__,
    url          = __url__,
    author       = __author__,
    author_email = __email__,
    #scripts=['relay_daemon']  # executable name  
    entry_points ={
        "console_scripts": ["rffe_daemon = rffe_daemon.main:main"]
    }
)
