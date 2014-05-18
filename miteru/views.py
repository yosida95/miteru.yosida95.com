# -*- coding: utf-8 -*-

import re
import json
import uuid
import htmlentitydefs
from urlparse import urlparse

import tweepy
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPFound,
    HTTPServerError,
    HTTPUnauthorized,
    HTTPForbidden,
)

from constants import (
    CONSUMER_KEY,
    CONSUMER_SECRET,
    REQUEST_TOKEN_SESSION_KEY,
)
from .models import (
    User,
    OnetimeToken,
    Tweet,
)


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
    try:
        oauth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET, secure=True)
        authorization_url = oauth.get_authorization_url()
        request.session[REQUEST_TOKEN_SESSION_KEY] = (
            oauth.request_token.key, oauth.request_token.secret)
    except tweepy.TweepError:
        raise HTTPServerError()
    else:
        return HTTPFound(location=authorization_url)


@view_config(route_name='authorization', request_method='GET',
             renderer='authorization.jinja2')
def authenticate(request):
    try:
        request_key, request_secret\
            = request.session[REQUEST_TOKEN_SESSION_KEY]
    except KeyError:
        raise HTTPForbidden()
    else:
        if request_key != request.GET.get('oauth_token'):
            raise HTTPForbidden()

    try:
        verifier = request.GET.get('oauth_verifier', '')

        oauth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET, secure=True)
        oauth.set_request_token(request_key, request_secret)
        oauth.get_access_token(verifier)

        user, created = User.objects.get_or_create(
            user_id=tweepy.API(oauth).me().id)
        if created is True:
            user.key = uuid.uuid4().hex
        user.access_key = oauth.access_token.key
        user.access_secret = oauth.access_token.secret
        user.save()
    except tweepy.TweepError:
        raise HTTPUnauthorized()
    else:
        return {'id': user.id,
                'key': user.key}


@view_config(route_name='token', request_method='GET',
             renderer='token.jinja2')
def token(request):
    url = unescape_html(request.GET.get('url', ''))
    domain = urlparse(url).netloc

    try:
        token = OnetimeToken.new(request.GET.get('id'), domain)
    except ValueError:
        raise HTTPUnauthorized()

    return {
        'token': token.token,
        'url': url,
        'title': unescape_html(request.GET.get('title', '')),
    }


@view_config(route_name='post', request_method=['GET', 'POST'],
             renderer='post.jinja2')
def post(request):

    tweet = Tweet(
        unescape_html(request.params.get('title', '')),
        unescape_html(request.params.get('url', '')),
        unescape_html(request.params.get('comment', '')))

    token = request.params.get('token', '')
    token_hashed = request.params.get('token_hashed', '')

    if request.POST:
        try:
            csrf_token = request.params.get('csrf_token')
            if csrf_token != request.session.get_csrf_token():
                raise Exception('不正なリクエストです。', False)

            if re.match(r'^https?://.+$', tweet.url) is None:
                raise Exception('不正なURLです。', False)

            tweet.do(token, token_hashed)
        except ValueError as why:
            successful, redo = False, False
            message = '投稿に失敗しました: {0!s}'.format(why)
        else:
            successful, redo = True, False
            message = '投稿しました'

        body = json.dumps({
            'result': successful,
            'redo': redo,
            'message': message,
        })
        return Response(body, content_type='application/json')
    else:
        return tweet.to_dict(token, token_hashed)
