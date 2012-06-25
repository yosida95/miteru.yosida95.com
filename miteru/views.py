#-*- coding: utf-8 -*-

import re
import hmac
import json
import uuid
import tweepy
import hashlib
import htmlentitydefs
from datetime import (
        datetime,
        timedelta,
    )
from urllib import urlencode, urlopen
from urlparse import (
        urlparse,
        urlunparse
    )
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
        Token,
    )


def uxnu_shorten(url):
    query = [(u'url', url)]
    req_url = urlunparse(
        ['http', u'ux.nu', u'/api/short', u'', urlencode(query), u''])
    result = urlopen(req_url)
    if 200 <= result.code < 300:
        short = json.loads(result.read())['data']['url']
    elif 400 <= result.code < 500:
        raise Exception()
    else:
        short = url

    return short


def unescape_html(string):
    matches = re.findall(ur'(&#(x?)([0-9a-fA-F]+);?)', string)
    for match in matches:
        try:
            result = unichr(int(match[2], 16 if match[1] == u'x' else 10))
        except ValueError:
            continue
        else:
            string = string.replace(match[0], result)

    matches = re.findall(ur'(&([a-zA-Z]+);?)', string)
    for match in matches:
        try:
            result = htmlentitydefs.name2codepoint[match[1]]
        except KeyError:
            continue
        else:
            string = string.replace(match[0], unichr(result))

    return string


@view_config(route_name=u'homepage', request_method=u'GET',
             renderer=u'homepage.jinja2')
def homepage(request):
    return {}


@view_config(route_name=u'login', request_method=u'GET')
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


@view_config(route_name=u'authorization', request_method=u'GET',
             renderer=u'authorization.jinja2')
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
        return {u'id': user.id,
                u'key': user.key}


@view_config(route_name=u'token', request_method=u'GET',
             renderer=u'token.jinja2')
def token(request):
    id = request.GET.get(u'id')
    url = unescape_html(request.GET.get(u'url', u''))
    domain = urlparse(url).netloc
    title = unescape_html(request.GET.get(u'title', u''))

    if id is not None and len(id) > 0:
        user = User.objects.filter(id=id)
        if int(user.count()) is 1:
            token = uuid.uuid4().hex
            Token(user=user.first(), token=token, domain=domain,
                  expiration=datetime.utcnow() + timedelta(minutes=10)).save()
            return {u'token': token, u'url': url, u'title': title}

    raise HTTPUnauthorized()


@view_config(route_name=u'post', request_method=[u'GET', u'POST'],
             renderer=u'post.jinja2')
def post(request):

    url = unescape_html(request.params.get(u'url', u''))
    title = unescape_html(request.params.get(u'title', u''))
    token = request.params.get(u'token', u'')
    token_hashed = request.params.get(u'token_hashed', u'')

    if len(token) is 0 or len(token_hashed) is 0 or\
    len(request.params.get(u'access_token', u'')) is not 0 or\
    len(request.params.get(u'access_token', u'')) is not 0:
        raise HTTPFound(location=request.route_url(u'message'))

    if request.method == u'POST':
        csrf_token = request.POST.get(u'csrf_token', u'')
        comment = request.POST.get(u'comment', u'')
        max_title_length = 110 if len(comment) == 0 else 107 - len(comment)

        try:
            try:
                token = Token.objects.get(token=token, available=True,
                                          expiration__gt=datetime.utcnow())
            except Exception as why:
                raise Exception(u'無効なトークンです。', False)
            else:
                token.available = False
                token.save()

            hmac_sha1 = hmac.new(token.user.key.encode(u'utf8'),
                                 token.token.encode(u'utf8'), hashlib.sha1)
            if hmac_sha1.hexdigest() != token_hashed:
                raise Exception(u'無効なトークンです。', False)

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
                oauth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
                oauth.set_access_token(
                    token.user.access_key.encode(u'utf-8'),
                    token.user.access_secret.encode(u'utf-8'))

                api = tweepy.API(oauth)
                api.update_status(text.encode(u'utf-8'))
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

        response = Response(body, content_type=u'application/json')
    else:
        response = {u'url': url, u'title': title,
                    u'token': token, u'token_hashed': token_hashed}

    return response


@view_config(route_name=u'message', renderer=u'message.jinja2')
def message(request):
    return {}
