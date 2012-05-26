#-*- coding: utf-8 -*-

import re
import tweepy
import json
from urllib import urlencode, urlopen
from urlparse import urlunparse
from pyramid.response import Response
from pyramid.i18n import TranslationStringFactory
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


_ = TranslationStringFactory(u'miteru')


def uxnu_shorten(url):
    query = [('url', url)]
    req_url = urlunparse(
        ['http', 'ux.nu', '/api/short', '', urlencode(query), ''])
    result = urlopen(req_url)
    if 200 <= result.code < 300:
        short = json.loads(result.read())['data']['url']
    elif 400 <= result.code < 500:
        raise Exception()
    else:
        short = url

    return short


@view_config(route_name='homepage', request_method='GET',
             renderer='homepage.jinja2')
def homepage(request):
    return {}


@view_config(route_name='login', request_method='GET')
def login(request):
    try:
        oauth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
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
        request_key, request_secret = request.session[
            REQUEST_TOKEN_SESSION_KEY]
    except KeyError:
        raise HTTPForbidden()
    else:
        if request_key != request.GET.get(u'oauth_token'):
            raise HTTPForbidden()

    try:
        verifier = request.GET.get(u'oauth_verifier', u'')

        oauth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        oauth.set_request_token(request_key, request_secret)
        oauth.get_access_token(verifier)
    except tweepy.TweepError:
        raise HTTPUnauthorized()
    else:
        post_url = '%s?access_key=%s&access_secret=%s' % (
            request.route_url(u'post'),
            oauth.access_token.key, oauth.access_token.secret)
        return {u'post_url': post_url}


@view_config(route_name='post', request_method=[u'GET', u'POST'],
             renderer=u'post.jinja2')
def post(request):
    url = request.params.get(u'url', u'')
    title = request.params.get(u'title', u'')
    access_key = request.params.get(u'access_key', u'')
    access_secret = request.params.get(u'access_secret', u'')

    if request.method == u'POST':
        csrf_token = request.POST.get(u'csrf_token', u'')
        comment = request.POST.get(u'comment', u'')
        max_title_length = 110 if len(comment) == 0 else 107 - len(comment)

        oauth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        oauth.set_access_token(access_key.encode(u'utf-8'),
                               access_secret.encode(u'utf-8'))

        try:
            if csrf_token != request.session.get_csrf_token():
                raise Exception(u'不正なリクエストです。', False)

            if re.match(r'^https?://.+$', url):
                url = uxnu_shorten(url)
            else:
                raise Exception(u'不正なURLです。', False)

            title = u'(No Title)' if len(title) == 0 else title
            if len(title) > max_title_length:
                title = title[:max_title_length - 1] + u'…'

            if len(comment) > 100:
                raise Exception(u'コメントが長過ぎます。100字以内で入力してください。', True)
        except Exception, why:
            successful = False
            message, redo = why.args
        else:
            if len(comment) == 0:
                text = u'%s: %s #miteru' % (title, url)
            else:
                text = u'%s - %s: %s #miteru' % (comment, title, url)

            try:
                api = tweepy.API(oauth)
                api.update_status(text.encode('utf-8'))
            except tweepy.TweepError, why:
                successful, redo = False, False
                message = u'投稿に失敗しました: %s' % (unicode(why), )
            else:
                successful, redo = True, False
                message = u'投稿しました'

        body = json.dumps({
            u'result': successful,
            u'redo': redo,
            u'message': message,
        })
        return Response(body, content_type='application/json')
    else:
        return {u'url': url, u'title': title,
                u'access_key': access_key, u'access_secret': access_secret,
               }
