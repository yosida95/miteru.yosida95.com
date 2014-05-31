# -*- coding: utf-8 -*-

import re
import json
from urllib.parse import quote

from jinja2 import (
    Environment,
    PackageLoader,
)
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPFound,
    HTTPServerError,
    HTTPUnauthorized,
)
from slimit import minify

from miteru.compat import (
    htmlentitydefs,
    unichr,
)
from miteru.exceptions import MiteruException
from miteru.models import (
    Tweet,
    TwitterAPI,
)

jinja2 = Environment(loader=PackageLoader('miteru', 'templates'))
REQUEST_TOKEN_SESSION_KEY = '_oauth_request_token'


def unescape_html(string):
    matches = re.findall(r'(&#(x?)([0-9a-fA-F]+);?)', string)
    for match in matches:
        try:
            result = unichr(int(match[2], 16 if match[1] == 'x' else 10))
        except ValueError:
            continue
        else:
            string = string.replace(match[0], result)

    matches = re.findall(r'(&([a-zA-Z]+);?)', string)
    for match in matches:
        try:
            result = htmlentitydefs.name2codepoint[match[1]]
        except KeyError:
            continue
        else:
            string = string.replace(match[0], unichr(result))

    return string


@view_config(route_name='homepage', request_method='GET',
             renderer='homepage.jinja2')
def homepage(request):
    return {}


@view_config(route_name='login', request_method='GET')
def login(request):
    twitter = TwitterAPI()
    request_token = twitter.get_request_token()

    request.session[REQUEST_TOKEN_SESSION_KEY] = request_token
    return HTTPFound(location=twitter.get_authorization_url(request_token[0]))


@view_config(route_name='authorization', request_method='GET',
             renderer='authorization.jinja2')
def authenticate(request):
    request_token, request_secret = request.session[REQUEST_TOKEN_SESSION_KEY]

    if request.GET.get('oauth_token') != request_token:
        raise HTTPUnauthorized()

    try:
        twitter = TwitterAPI()
        key = twitter.authorize(request_token, request_secret,
                                request.GET.get('oauth_verifier', ''))
    except ValueError:
        raise HTTPUnauthorized()
    except:
        raise
        raise HTTPServerError()

    bookmarklet =\
        jinja2.get_template('bookmarklet.js').render(key=key, request=request)
    return dict(
        raw=bookmarklet,
        minified=minify(bookmarklet, mangle=True, mangle_toplevel=True))


@view_config(route_name='token', request_method='GET')
def token(request):
    # for v2
    return HTTPFound(location=request.route_path('post', _query={
        'keyid': request.GET.get('token', ''),
        'url': request.GET.get('url', ''),
        'title': request.GET.get('title', '')
    }))


@view_config(route_name='post', request_method=['GET', 'POST'],
             renderer='post.jinja2')
def post(request):
    tweet = Tweet(
        unescape_html(request.params.get('title', '')),
        unescape_html(request.params.get('url', '')),
        unescape_html(request.params.get('comment', '')))

    if request.method == 'GET':
        return tweet.to_dict()

    try:
        csrf_token = request.POST.get('csrf_token')
        if csrf_token != request.session.get_csrf_token():
            raise MiteruException('不正なリクエストです。', False)

        signed_query = '&'.join(map(
            lambda key: '{0}={1}'.format(
                key, quote(request.POST.get(key, ''), safe='~()*!.\'')),
            request.POST.get('signed_keys', '').split(',')
        ))
        user = tweet.authenticate(request.POST.get('keyid', ''),
                                  request.POST.get('signature', ''),
                                  signed_query)

        tweet.do(user)
    except MiteruException as why:
        successful, redo = False, why.retryable
        message = '投稿に失敗しました: {0!s}'.format(why.message)
    except BaseException:
        successful, redo = False, False
        message = '投稿に失敗しました'
    else:
        successful, redo = True, False
        message = '投稿しました'

    body = json.dumps({
        'result': successful,
        'redo': redo,
        'message': message,
    })
    return Response(body, content_type='application/json')
