# -*- coding: utf-8 -*-

import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))


def read(name):
    try:
        return open(os.path.join(here, name)).read()
    except:
        return ""
README = read('README.txt')
CHANGES = read('CHANGES.txt')

requires = [
    'pyramid',
    'pyramid_debugtoolbar',
    'pyramid_tm',
    'pyramid_jinja2',
    'SQLAlchemy',
    'transaction',
    'zope.sqlalchemy',
    'waitress',
    'oauthlib',
    'requests',
    'requests_oauthlib',
    'slimit',
]

tests_require = [
    'nose',
    'coverage',
]

setup(name='miteru',
      version='0.0',
      description='miteru',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
          "Programming Language :: Python",
          "Framework :: Pylons",
          "Topic :: Internet :: WWW/HTTP",
          "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
      ],
      author='Kohei YOSHIDA',
      author_email='license@yosida95.com',
      url='https://miteru.yosida95.com/',
      keywords='web pyramid pylons',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=tests_require,
      test_suite="miteru",
      entry_points={
          "paste.app_factory": [
              "main = miteru:main",
          ],
          "console_scripts": [
              "initialize_miteru_db = miteru.scripts.initializedb:main",
          ]
      })
