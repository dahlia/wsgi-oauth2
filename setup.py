from __future__ import with_statement
from distutils.core import setup
import wsgioauth2

try:
    with open('README.rst') as fd:
        long_description = fd.read()
except IOError:
    long_description = None

setup(name='wsgi-oauth2',
      description='Simple WSGI middleware for OAuth 2.0',
      long_description=long_description,
      version=wsgioauth2.__version__,
      author=wsgioauth2.__author__,
      author_email=wsgioauth2.__email__,
      py_modules=['wsgioauth2'],
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Web Environment',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware'
      ])

