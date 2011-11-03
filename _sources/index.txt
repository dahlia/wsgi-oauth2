.. wsgi-oauth2 documentation master file, created by
   sphinx-quickstart on Fri Nov  4 07:40:13 2011.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

wsgi-oauth2
===========

This module provides a simple WSGI middleware that requires the user to
authenticate via the specific `OAuth 2.0`_ service e.g. Facebook_, Google_.

.. _OAuth 2.0: http://oauth.net/2/
.. _Facebook: http://www.facebook.com/
.. _Google: http://www.google.com/


Predefined services
-------------------

There are some predefined services.

.. autodata:: wsgioauth2.google

.. autodata:: wsgioauth2.facebook


.. module:: wsgioauth2

:mod:`wsgioauth2` --- API references
------------------------------------

.. autoclass:: wsgioauth2.Service
   :members:

.. autoclass:: wsgioauth2.Client
   :members:

.. autoclass:: wsgioauth2.AccessToken
   :members:

.. autoclass:: wsgioauth2.WSGIMiddleware
   :members:

