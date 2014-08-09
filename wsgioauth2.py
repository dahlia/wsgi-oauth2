# Copyright (C) 2011-2014 by Hong Minhee <http://hongminhee.org/>
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
import base64
import binascii
import cgi
try:
    import Cookie
except ImportError:
    from http import cookies as Cookie
import hashlib
import hmac
try:
    import simplejson as json
except ImportError:
    import json
import numbers
try:
    import cPickle as pickle
except ImportError:
    import pickle
import random
try:
    import urllib2
except ImportError:
    from urllib import request as urllib2
try:
    import urlparse
except ImportError:
    from urllib import parse as urlparse
    urlencode = urlparse.urlencode
else:
    from urllib import urlencode

__author__ = 'Hong Minhee'  # http://hongminhee.org/
__email__ = 'minhee' "@" 'dahlia.kr'
__license__ = 'MIT License'
__version__ = '0.2.0'
__copyright__ = '2011-2014, Hong Minhee'

__all__ = ('AccessToken', 'Client', 'GitHubService', 'GithubService',
           'Service', 'WSGIMiddleware', 'github', 'google', 'facebook')


# Python 3 compatibility
try:
    basestring
except NameError:
    basestring = str


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

    def load_username(self, access_token):
        """Load a username from the service suitable for the REMOTE_USER
        variable. A valid :class:`AccessToken` is provided to allow access to
        authenticated resources provided by the service. If the service supports
        usernames this method must set the 'username' parameter to access_token.

        :param access_token: a valid :class:`AccessToken`

        .. versionadded:: 0.1.2

        """
        raise NotImplementedError(
            "This Service does not provide a username for REMOTE_USER")

    def is_user_allowed(self, access_token):
        """Check if the authenticated user is allowed to access the protected
        application. By default, any authenticated user is allowed access.
        Override this check to allow the :class:`Service` to further-restrict
        access based on additional information known by the service.

        :param access_token: a valid :class:`AccessToken`

        .. versionadded:: 0.1.3

        """
        return True

    def make_client(self, client_id, client_secret, **extra):
        """Makes a :class:`Client` for the service.

        :param client_id: a client id
        :type client_id: :class:`basestring`, :class:`numbers.Integral`
        :param client_secret: client secret key
        :type client_secret: :class:`basestring`
        :returns: a client for the service
        :rtype: :class:`Client`
        :param \*\*extra: additional arguments for authorization e.g.
                          ``scope='email,read_stream'``

        """
        return Client(self, client_id, client_secret, **extra)


class GitHubService(Service):
    """OAuth 2.0 service provider for GitHub with support for getting the
    authorized username.

    :param allowed_orgs: What GitHub Organizations are allowed to access the
                         protected application.
    :type allowed_orgs: :class:`basestring`,
                        :class:`collections.Container` of :class:`basestring`

    .. versionadded:: 0.1.3
       The ``allowed_orgs`` option.

    .. versionadded:: 0.1.2

    """

    def __init__(self, allowed_orgs=None):
        super(GitHubService, self).__init__(
            authorize_endpoint='https://github.com/login/oauth/authorize',
            access_token_endpoint='https://github.com/login/oauth/access_token')
        # coerce a single string into a list
        if isinstance(allowed_orgs, basestring):
            allowed_orgs = [allowed_orgs]
        self.allowed_orgs = allowed_orgs

    def load_username(self, access_token):
        """Load a username from the service suitable for the REMOTE_USER
        variable. A valid :class:`AccessToken` is provided to allow access to
        authenticated resources provided by the service. For GitHub the 'login'
        variable is used.

        :param access_token: a valid :class:`AccessToken`

        .. versionadded:: 0.1.2

        """
        response = access_token.get('https://api.github.com/user')
        response = response.read()
        response = json.loads(response)
        # Copy useful data
        access_token["username"] = response["login"]
        access_token["name"] = response["name"]

    def is_user_allowed(self, access_token):
        """Check if the authenticated user is allowed to access the protected
        application. If this :class:`GitHubService` was created with a list of
        allowed_orgs, the user must be a memeber of one or more of the
        allowed_orgs to get access. If no allowed_orgs were specified, all
        authenticated users will be allowed.

        :param access_token: a valid :class:`AccessToken`

        .. versionadded:: 0.1.3

        """
        # if there is no list of allowed organizations, any authenticated user
        # is allowed.
        if not self.allowed_orgs:
            return True

        # Get a list of organizations for the authenticated user
        response = access_token.get("https://api.github.com/user/orgs")
        response = response.read()
        response = json.loads(response)
        user_orgs = set(org["login"] for org in response)

        allowed_orgs = set(self.allowed_orgs)
        # If any orgs overlap, allow the user.
        return bool(allowed_orgs.intersection(user_orgs))


GithubService = GitHubService


class Client(object):
    """Client for :class:`Service`.

    :param service: service the client connects to
    :type servie: :class:`Service`
    :param client_id: client id
    :type client_id: :class:`basestring`, :class:`numbers.Integral`
    :param client_secret: client secret key
    :type client_secret: :class:basestring`
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
        elif isinstance(client_id, numbers.Integral):
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
                                urlencode(query))

    def load_username(self, access_token):
        """Load a username from the configured service suitable for the
        REMOTE_USER variable. A valid :class:`AccessToken` is provided to allow
        access to authenticated resources provided by the service. For GitHub
        the 'login' variable is used.

        :param access_token: a valid :class:`AccessToken`

        .. versionadded:: 0.1.2

        """
        self.service.load_username(access_token)

    def is_user_allowed(self, access_token):
        return self.service.is_user_allowed(access_token)

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
                            data=urlencode(form).encode('utf-8'))
        m = u.info()
        try:
            # Python 2
            content_type = m.gettype()
        except AttributeError:
            # Python 3
            content_type = m.get_content_type()
        if content_type == 'application/json':
            data = json.load(u)
        else:
            data = dict(
                (k.decode('utf-8')
                 if not isinstance(k, str) and isinstance(k, bytes)
                 else k, v)
                for k, v in urlparse.parse_qs(u.read()).items()
            )
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
        super(AccessToken, self).__init__(*args, **kwargs)
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
        url += '&' if '?' in url else '?' + 'access_token=' + self.access_token
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
    :type secret: :class:`bytes`
    :param path: path prefix used for callback. by default, a randomly
                 generated complex path is used
    :type path: :class:`basestring`
    :param cookie: cookie name to be used for maintaining the user session.
                   default is :const:`DEFAULT_COOKIE`
    :type cookie: :class:`basestring`
    :param set_remote_user: Set to True to set the REMOTE_USER environment
                            variable to the authenticated username (if supported
                            by the :class:`Service`)
    :type set_remote_user: :class:`bool`
    :param forbidden_path: What path should be used to display the 403 Forbidden
                           page.  Any forbidden user will be redirected to this
                           path and a default 403 Forbidden page will be shown.
                           To override the default Forbidden page see the
                           ``forbidden_passthrough`` option.
    :type forbidden_path: :class:`basestring`
    :param forbidden_passthrough: Should the forbidden page be passed-through to
                                  the protected application. By default, a
                                  generic Forbidden page will be generated. Set
                                  this to :const:`True` to pass the request
                                  through to the protected application.
    :type forbidden_passthrough: :class:`bool`
    :param login_path:  The base path under which login will be required. Any
                        URL starting with this path will trigger the OAuth2
                        process.  The default is '/', meaning that the entire
                        application is protected.  To override the default
                        path see the :attr:`login_path` option.
    :type login_path: :class:`basestring`

    .. versionadded:: 0.1.4
       The ``login_path`` option.

    .. versionadded:: 0.1.3
       The ``forbidden_path`` and ``forbidden_passthrough`` options.

    .. versionadded:: 0.1.2
       The ``set_remote_user`` option.

    """

    #: (:class:`basestring`) The default name for :attr:`cookie`.
    DEFAULT_COOKIE = 'wsgioauth2sess'

    #: (:class:`Client`) The OAuth2 client.
    client = None

    #: (callable object) The wrapped WSGI application.
    application = None

    #: (:class:`bytes`) The secret key for generating HMAC signature.
    secret = None

    #: (:class:`basestring`) The path prefix for callback URL. It always
    #: starts and ends with ``'/'``.
    path = None

    #: (:class:`basestring`) The path that is used to display the 403 Forbidden
    #: page.  Any forbidden user will be redirected to this path and a default
    #: 403 Forbidden page will be shown.  To override the default Forbidden
    #: page see the :attr:`forbidden_passthrough` option.
    forbidden_path = None

    #: (:class:`bool`) Whether the forbidden page should be passed-through
    #: to the protected application.   By default, a generic Forbidden page
    #: will be generated.  Set this to :const:`True` to pass the request
    #: through to the protected application.
    forbidden_passthrough = None

    #: (:class:`basestring`) The base path under which login will be required.
    #: Any URL starting with this path will trigger the OAuth2 process.  The
    #: default is '/', meaning that the entire application is protected.  To
    #: override the default path see the :attr:`login_path` option.
    #:
    #: .. versionadded:: 0.1.4
    login_path = None

    #: (:class:`basestring`) The cookie name to be used for maintaining
    #: the user session.
    cookie = None

    def __init__(self, client, application, secret,
                 path=None, cookie=DEFAULT_COOKIE, set_remote_user=False,
                 forbidden_path=None, forbidden_passthrough=False,
                 login_path=None):
        if not isinstance(client, Client):
            raise TypeError('client must be a wsgioauth2.Client instance, '
                            'not ' + repr(client))
        if not callable(application):
            raise TypeError('application must be an WSGI compliant callable, '
                            'not ' + repr(application))
        if not isinstance(secret, bytes):
            raise TypeError('secret must be bytes, not ' + repr(secret))
        if not (path is None or isinstance(path, basestring)):
            raise TypeError('path must be a string, not ' + repr(path))
        if not (forbidden_path is None or
                isinstance(forbidden_path, basestring)):
            raise TypeError('forbidden_path must be a string, not ' +
                            repr(path))
        if not (login_path is None or
                isinstance(login_path, basestring)):
            raise TypeError('login_path must be a string, not ' +
                            repr(path))
        if not isinstance(cookie, basestring):
            raise TypeError('cookie must be a string, not ' + repr(cookie))
        self.client = client
        self.application = application
        self.secret = secret
        if path is None:
            seq = ('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                   'abcdefghijklmnopqrstuvwxyz_-.')
            path = ''.join(random.choice(seq) for x in range(40))
            path = '__{0}__'.format(path)
        self.path = '/{0}/'.format(path.strip('/'))
        if forbidden_path is None:
            forbidden_path = "/forbidden"
        # forbidden_path must start with a / to avoid relative links
        if not forbidden_path.startswith('/'):
            forbidden_path = '/' + forbidden_path
        self.forbidden_path = forbidden_path
        self.forbidden_passthrough = forbidden_passthrough
        if login_path is None:
            login_path = '/'
        # login_path must start with a / to ensure proper matching
        if not login_path.startswith('/'):
            login_path = '/' + login_path
        self.login_path = login_path
        self.cookie = cookie
        self.set_remote_user = set_remote_user

    def sign(self, value):
        """Generate signature of the given ``value``.

        .. versionadded:: 0.2.0

        """
        if not isinstance(value, bytes):
            raise TypeError('expected bytes, not ' + repr(value))
        return hmac.new(self.secret, value, hashlib.sha1).hexdigest()

    def redirect(self, url, start_response, headers={}):
        h = {'Content-Type': 'text/html; charset=utf-8', 'Location': url}
        h.update(headers)
        start_response('307 Temporary Redirect', list(h.items()))
        e_url = cgi.escape(url).encode('iso-8859-1')
        yield b'<!DOCTYPE html>'
        yield b'<html><head><meta charset="utf-8">'
        yield b'<meta http-equiv="refresh" content="0; url='
        yield e_url
        yield b'"><title>Redirect to '
        yield e_url
        yield b'</title></head><body><p>Redirect to <a href="'
        yield e_url
        yield b'">'
        yield e_url
        yield b'</a>&hellip;</p></body></html>'

    def forbidden(self, start_response):
        """Respond with an HTTP 403 Forbidden status."""
        h = [('Content-Type', 'text/html; charset=utf-8')]
        start_response('403 Forbidden', h)
        yield b'<!DOCTYPE html>'
        yield b'<html><head><meta charset="utf-8">'
        yield b'<title>Forbidden</title></head>'
        yield b'<body><p>403 Forbidden - '
        yield b'Your account does not have access to the requested resource.'
        yield b'<pre>'
        yield b'</pre>'
        yield b'</p></body></html>'

    def __call__(self, environ, start_response):
        url = '{0}://{1}{2}'.format(environ.get('wsgi.url_scheme', 'http'),
                                    environ.get('HTTP_HOST', ''),
                                    environ.get('PATH_INFO', '/'))
        redirect_uri = urlparse.urljoin(url, self.path)
        forbidden_uri = urlparse.urljoin(url, self.forbidden_path)
        query_string = environ.get('QUERY_STRING', '')
        if query_string:
            url += '?' + query_string
        cookie_dict = Cookie.SimpleCookie()
        cookie_dict.load(environ.get('HTTP_COOKIE', ''))
        query_dict = urlparse.parse_qs(query_string)
        path = environ['PATH_INFO']
        if path.startswith(self.forbidden_path):
            if self.forbidden_passthrough:
                # Pass the forbidden request through to the app
                return self.application(environ, start_response)
            return self.forbidden(start_response)

        elif path.startswith(self.path):
            code = query_dict.get('code')
            if not code:
                # No code in URL - forbidden
                return self.redirect(forbidden_uri, start_response)

            try:
                code = code[0]
                access_token = self.client.request_access_token(redirect_uri,
                                                                code)
            except TypeError:
                # No access token provided - forbidden
                return self.redirect(forbidden_uri, start_response)

            # Load the username now so it's in the session cookie
            if self.set_remote_user:
                self.client.load_username(access_token)

            # Check if the authenticated user is allowed
            if not self.client.is_user_allowed(access_token):
                return self.redirect(forbidden_uri, start_response)

            session = pickle.dumps(access_token)
            sig = self.sign(session)
            signed_session = sig.encode('ascii') + b',' + session
            signed_session = base64.urlsafe_b64encode(signed_session)
            set_cookie = Cookie.SimpleCookie()
            set_cookie[self.cookie] = signed_session.decode('ascii')
            set_cookie[self.cookie]['path'] = '/'
            if 'expires_in' in access_token:
                expires_in = int(access_token['expires_in'])
                set_cookie[self.cookie]['expires'] = expires_in
            set_cookie = set_cookie[self.cookie].OutputString()
            return self.redirect(query_dict.get('state', [''])[0],
                                 start_response,
                                 headers={'Set-Cookie': set_cookie})
        elif path.startswith(self.login_path):
            if self.cookie in cookie_dict:
                session = cookie_dict[self.cookie].value
                try:
                    session = base64.urlsafe_b64decode(session)
                except binascii.Error:
                    session = b''
                if b',' in session:
                    sig, val = session.split(b',', 1)
                    if sig.decode('ascii') == self.sign(val):
                        try:
                            session = pickle.loads(val)
                        except (pickle.UnpicklingError, ValueError):
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
            else:
                environ = dict(environ)
                environ['wsgioauth2.session'] = session
                if self.set_remote_user and session['username']:
                    environ['REMOTE_USER'] = session['username']

        return self.application(environ, start_response)


#: (:class:`Service`) The predefined service for Facebook__.
#:
#: __ https://www.facebook.com/
facebook = Service(
    authorize_endpoint='https://www.facebook.com/dialog/oauth',
    access_token_endpoint='https://graph.facebook.com/oauth/access_token'
)

#: (:class:`Service`) The predefined service for Google__.
#:
#: __ http://www.google.com/
google = Service(
    authorize_endpoint='https://accounts.google.com/o/oauth2/auth',
    access_token_endpoint='https://accounts.google.com/o/oauth2/token'
)

#: (:class:`GitHubService`) The predefined service for GitHub__.
#:
#: .. versionadded:: 0.1.2
#:
#: __ https://github.com/
github = GitHubService()
