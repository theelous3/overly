#!/usr/bin/env python3

from setuptools import setup
from sys import version_info

if version_info < (3, 6, 0):
    # 3.5.2 is when __aiter__ became a synchronous function
    raise SystemExit('Sorry! overly requires python 3.4 or later.')

setup(
    name='overly',
    description='overly - http client testing for hoomans',
    long_description='overly is for testing your http client, from the balan to the bananas.',
    license='MIT',
    version='0.1.0',
    author='Mark Jameson - aka theelous3',
    url='https://github.com/theelous3/overly',
    packages=['overly'],
    install_requires=['h11', 'sansio_multipart'],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Internet :: WWW/HTTP',
    ]
)
