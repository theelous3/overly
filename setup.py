#!/usr/bin/env python3

from setuptools import setup
from sys import version_info


setup(
    name='overly',
    description='overly - http client testing for hoomans',
    long_description='overly is for testing your http client, from the balan to the bananas.',
    license='MIT',
    version='0.1.5',
    python_requires=">=3.7",
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
