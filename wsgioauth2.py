# Copyright (C) 2011 by StyleShare, Inc
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
""":mod:`wsgioauth2` --- Simple WSGI middleware for OAuth 2.0
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This module provides a simple WSGI middleware that requires the user to
authenticate via the specific `OAuth 2.0`_ service e.g. Facebook_, Google_.

.. _OAuth 2.0: http://oauth.net/2/
.. _Facebook: http://www.facebook.com/
.. _Google: http://www.google.com/

"""
import random
import urllib
import urllib2
import urlparse
import hmac
import hashlib
import base64
import Cookie
import cgi
try:
    import simplejson as json
except ImportError:
    import json
try:
    import cPickle as pickle
except ImportError:
    import pickle

__author__ = 'Hong Minhee' # http://dahlia.kr/
__email__ = 'dahlia' "@" 'stylesha.re'
__license__ = 'MIT License'
__version__ = '0.1.1'
__copyright__ = '2011, StyleShare, Inc'


class Service(object):
    """OAuth 2.0 service provider e.g. Facebook, Google. It takes
    endpoint urls for authorization and access token gathering APIs.

    :param authorize_endpoint: api url for authorization
    :type authorize_endpoint: :class:`basestring`
    :param access_token_endpoint: api url for getting access token
    :type access_token_endpoint: :class:`basestring`

    """

    #: (:class:`basestring`) The API URL for authorization.
    authorize_endpoint = None

    #: (:class:`basestring`) The API URL for getting access token.
    access_token_endpoint = None

    def __init__(self, authorize_endpoint, access_token_endpoint):
        def check_endpoint(endpoint):
            if not isinstance(endpoint, basestring):
                raise TypeError('endpoint must be a string, not ' +
                                repr(endpoint))
            elif not (endpoint.startswith('http://') or
                      endpoint.startswith('https://')):
                raise ValueError('endpoint must be a url string, not ' +
                                 repr(endpoint))
            return endpoint
        self.authorize_endpoint = check_endpoint(authorize_endpoint)
        self.access_token_endpoint = check_endpoint(access_token_endpoint)

    def make_client(self, client_id, client_secret, **extra):
        """Makes a :class:`Client` for the service.

        :param client_id: a client id
        :type client_id: :class:`basestring`, :class:`int`, :class:`long`
        :param client_secret: client secret key
        :type client_secret: :class:`basestring`
        :returns: a client for the service
        :rtype: :class:`Client`
        :param \*\*extra: additional arguments for authorization e.g.
                          ``scope='email,read_stream'``

        """
        return Client(self, client_id, client_secret, **extra)


class Client(object):
    """Client for :class:`Service`.

    :param service: service the client connects to
    :type servie: :class:`Service`
    :param client_id: client id
    :type client_id: :class:`basestring`, :class:`int`, :class:`long`
    :param client_secret: client secret key
    :type client_secret: :class:`basestring`
    :param \*\*extra: additional arguments for authorization e.g.
                      ``scope='email,read_stream'``

    """

    #: (:class:`Service`) The service the client connects to.
    service = None

    #: (:class:`basestring`) The client id.
    client_id = None

    #: (:class:`basestring`) The client secret key.
    client_secret = None

    #: (:class:`dict`) The additional arguments for authorization e.g.
    #: ``{'scope': 'email,read_stream'}``.

    def __init__(self, service, client_id, client_secret, **extra):
        if not isinstance(service, Service):
            raise TypeError('service must be a wsgioauth2.Service instance, '
                            'not ' + repr(service))
        elif isinstance(client_id, (int, long)):
            client_id = str(client_id)
        elif not isinstance(client_id, basestring):
            raise TypeError('client_id must be a string, not ' +
                            repr(client_id))
        elif not isinstance(client_secret, basestring):
            raise TypeError('client_secret must be a string, not ' +
                            repr(client_secret))
        self.service = service
        self.client_id = client_id
        self.client_secret = client_secret
        self.extra = extra

    def make_authorize_url(self, redirect_uri, state=None):
        """Makes an authorize URL.

        :param redirect_uri: callback url
        :type redirect_uri: :class:`basestring`
        :param state: optional state to get when the user returns to
                      callback
        :type state: :class:`basestring`
        :returns: generated authorize url
        :rtype: :class:`basestring`

        """
        query = dict(self.extra)
        query.update(client_id=self.client_id,
                     redirect_uri=redirect_uri,
                     response_type='code')
        if state is not None:
            query['state'] = state
        return '{0}?{1}'.format(self.service.authorize_endpoint,
                                urllib.urlencode(query))

    def request_access_token(self, redirect_uri, code):
        """Requests an access token.

        :param redirect_uri: ``redirect_uri`` that was passed to
                             :meth:`make_authorize_url`
        :type redirect_uri: :class:`basestring`
        :param code: verification code that authorize endpoint provides
        :type code: :class:`code`
        :returns: access token and additional data
        :rtype: :class:`AccessToken`

        """
        form = {'code': code,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'}
        u = urllib2.urlopen(self.service.access_token_endpoint,
                            data=urllib.urlencode(form))
        content_type = u.info().get('Content-Type')
        if content_type == 'application/json':
            data = json.load(u)
        else:
            data = urlparse.parse_qs(u.read())
        u.close()
        return AccessToken(data)

    def wsgi_middleware(self, *args, **kwargs):
        """Wraps a WSGI application."""
        return WSGIMiddleware(self, *args, **kwargs)


class AccessToken(dict):
    """Dictionary that contains access token. It always has ``'access_token'``
    key.

    """

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        if 'access_token' not in self:
            raise TypeError("'access_token' is required")

    @property
    def access_token(self):
        """(:class:`basestring`) Access token."""
        access_token = self['access_token']
        if isinstance(access_token, list):
            return access_token[0]
        return access_token

    def get(self, url, headers={}):
        """Requests ``url`` as ``GET``.

        :param headers: additional headers
        :type headers: :class:`collections.Mapping`

        """
        if '?' in url:
            url += '&access_token=' + self.access_token
        else:
            url += '?access_token=' + self.access_token
        request = urllib2.Request(url, headers=headers)
        return urllib2.urlopen(request)

    def post(self, url, form={}, headers={}):
        """Requests ``url`` as ``POST``.

        :param form: form data
        :type form: :class:`collections.Mapping`
        :param headers: additional headers
        :type headers: :class:`collections.Mapping`

        """
        form = dict(form)
        form['access_token'] = self.access_token
        request = urllib2.Request(url, data=form, headers=headers)
        return urllib2.urlopen(request)

    def __str__(self):
        return self.access_token

    def __repr__(self):
        cls = type(self)
        repr_ = dict.__repr__(self)
        return '{0}.{1}({2})'.format(cls.__module__, cls.__name__, repr_)


class WSGIMiddleware(object):
    """WSGI middleware application.

    :param client: oauth2 client
    :type client: :class:`Client`
    :param application: wsgi application
    :type application: callable object
    :param secret: secret key for generating HMAC signature
    :type secret: :class:`basestring`
    :param path: path prefix used for callback. by default, a randomly
                 generated complex path is used
    :type path: :class:`basestring`
    :param cookie: cookie name to be used for maintaining the user session.
                   default is :const:`DEFAULT_COOKIE`
    :type cookie: :class:`basestring`

    """

    #: (:class:`basestring`) The default name for :attr:`cookie`. 
    DEFAULT_COOKIE = 'wsgioauth2sess'

    #: (:class:`Client`) The OAuth2 client.
    client = None

    #: (callable object) The wrapped WSGI application.
    application = None

    #: (:class:`basestring`) The secret key for generating HMAC signature.
    secret = None

    #: (:class:`basestring`) The path prefix for callback URL. It always
    #: starts and ends with ``'/'``.
    path = None

    #: (:class:`basestring`) The cookie name to be used for maintaining
    #: the user session.
    cookie = None

    def __init__(self, client, application, secret,
                 path=None, cookie=DEFAULT_COOKIE):
        if not isinstance(client, Client):
            raise TypeError('client must be a wsgioauth2.Client instance, '
                            'not ' + repr(client))
        elif not callable(application):
            raise TypeError('application must be an WSGI compliant callable, '
                            'not ' + repr(application))
        elif not isinstance(secret, basestring):
            raise TypeError('secret must be a string, not ' + repr(secret))
        elif not (path is None or isinstance(path, basestring)):
            raise TypeError('path must be a string, not ' + repr(path))
        elif not isinstance(cookie, basestring):
            raise TypeError('cookie must be a string, not ' + repr(cookie))
        self.client = client
        self.application = application
        self.secret = secret
        if path is None:
            seq = ('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                   'abcdefghijklmnopqrstuvwxyz_-.')
            path = ''.join(random.choice(seq) for x in xrange(40))
            path = '__{0}__'.format(path)
        self.path = '/{0}/'.format(path.strip('/'))
        self.cookie = cookie

    def redirect(self, url, start_response, headers={}):
        h = {'Content-Type': 'text/html; charset=utf-8', 'Location': url}
        h.update(headers)
        start_response('307 Temporary Redirect', h.items())
        e_url = cgi.escape(url)
        yield '<!DOCTYPE html>'
        yield '<html><head><meta charset="utf-8">'
        yield '<meta http-equiv="refresh" content="0; url='
        yield e_url
        yield '"><title>Redirect to '
        yield e_url
        yield '</title></head><body><p>Redirect to <a href="'
        yield e_url
        yield '">'
        yield e_url
        yield '</a>&hellip;</p></body></html>'

    def __call__(self, environ, start_response):
        url = '{0}://{1}{2}'.format(environ.get('wsgi.url_scheme', 'http'),
                                    environ.get('HTTP_HOST', ''),
                                    environ.get('PATH_INFO', '/'))
        redirect_uri = urlparse.urljoin(url, self.path)
        query_string = environ.get('QUERY_STRING', '')
        if query_string:
            url += '?' + query_string
        cookie_dict = Cookie.SimpleCookie()
        cookie_dict.load(environ.get('HTTP_COOKIE', ''))
        query_dict = urlparse.parse_qs(query_string)
        if environ.get('PATH_INFO').startswith(self.path):
            try:
                code = query_dict['code']
            except KeyError:
                return self.application(environ, start_response)
            else:
                code = code[0]
                access_token = self.client.request_access_token(redirect_uri,
                                                                code)
                session = pickle.dumps(access_token)
                sig = hmac.new(self.secret, session, hashlib.sha1).hexdigest()
                signed_session = '{0},{1}'.format(sig, session)
                signed_session = base64.urlsafe_b64encode(signed_session)
                set_cookie = Cookie.SimpleCookie()
                set_cookie[self.cookie] = signed_session
                set_cookie[self.cookie]['path'] = '/'
                if 'expires_in' in access_token:
                    expires_in = int(access_token['expires_in'])
                    set_cookie[self.cookie]['expires'] = expires_in
                set_cookie = set_cookie[self.cookie].OutputString()
                return self.redirect(query_dict.get('state', [''])[0],
                                     start_response,
                                     headers={'Set-Cookie': set_cookie})
        elif self.cookie in cookie_dict:
            session = cookie_dict[self.cookie].value
            session = base64.urlsafe_b64decode(session)
            if ',' in session:
                sig, val = session.split(',', 1)
                if sig == hmac.new(self.secret, val, hashlib.sha1).hexdigest():
                    try:
                        session = pickle.loads(val)
                    except pickle.UnpicklingError:
                        session = None
                else:
                    session = None
            else:
                session = None
        else:
            session = None
        if session is None:
            return self.redirect(
                self.client.make_authorize_url(redirect_uri, state=url),
                start_response
            )
        environ = dict(environ)
        environ['wsgioauth2.session'] = session
        return self.application(environ, start_response)


#: (:class:`Service`) The predefined service definition for Facebook_.
#:
#: .. _Facebook: http://www.facebook.com/
facebook = Service(
    authorize_endpoint='https://www.facebook.com/dialog/oauth',
    access_token_endpoint='https://graph.facebook.com/oauth/access_token'
)

#: (:class:`Service`) The predefined service definition for Google_.
#:
#: .. _Google: http://www.google.com/
google = Service(
    authorize_endpoint='https://accounts.google.com/o/oauth2/auth',
    access_token_endpoint='https://accounts.google.com/o/oauth2/token'
)

