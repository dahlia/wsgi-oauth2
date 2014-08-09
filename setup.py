from __future__ import with_statement
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
import distutils.cmd
import os
import os.path
import tempfile
import shutil
import wsgioauth2

try:
    with open('README.rst') as fd:
        long_description = fd.read()
except IOError:
    long_description = None


class upload_doc(distutils.cmd.Command):
    """Uploads the documentation to GitHub pages."""

    description = __doc__
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        path = tempfile.mkdtemp()
        build = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'build', 'sphinx', 'html')
        os.chdir(path)
        os.system('git clone git@github.com:dahlia/wsgi-oauth2.git .')
        os.system('git checkout gh-pages')
        os.system('git rm -r .')
        os.system('touch .nojekyll')
        os.system('cp -r ' + build + '/* .')
        os.system('git stage .')
        os.system('git commit -a -m "Documentation updated."')
        os.system('git push origin gh-pages')
        shutil.rmtree(path)


cmdclass = {'upload_doc': upload_doc}


setup(name='wsgi-oauth2',
      description='Simple WSGI middleware for OAuth 2.0',
      long_description=long_description,
      version=wsgioauth2.__version__,
      author=wsgioauth2.__author__,
      author_email=wsgioauth2.__email__,
      license='MIT license',
      url='http://hongminhee.org/wsgi-oauth2/',
      py_modules=['wsgioauth2'],
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Web Environment',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.2',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware'
      ],
      cmdclass=cmdclass)
