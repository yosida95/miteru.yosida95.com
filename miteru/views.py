#-*- coding: utf-8 -*-

import tweepy
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


@view_config(route_name='post', request_method=['GET', u'POST'],
             renderer=u'post.jinja2')
def post_form(request):
    if request.method == u'POST':
        if request.POST.get(u'csrf_token') != request.session.get_csrf_token():
            raise HTTPForbidden()

        oauth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        oauth.set_access_token(
            request.POST.get(u'access_key'),
            request.POST.get(u'access_secret'))
        comment = request.POST.get(u'comment', '')
        title = request.POST.get(u'title', '')
        url = request.POST.get(u'url', '')

        if len(comment) <= 100:
            error = u'コメントが長過ぎます。100文字以内で入力してください'
        else:
            if len(comment) > 0:
                text = '%s - %s: %s #miteru' % (
                    comment, title[:107 - len(comment)], url)
            else:
                text = '%s: %s #miteru' % (title[:110], url)

            try:
                api = tweepy.API(auth_handler=oauth)
                api.update_status(text.encode(u'utf8'))
            except tweepy.TweepError:
                raise HTTPServerError()
            else:
                return {u'posted': True}
    else:
        error = u''

    return {u'posted': False, u'access_key': request.params.get(u'access_key'),
            u'access_secret': request.params.get(u'access_secret'),
            u'title': request.params.get(u'title', ''),
            u'url': request.params.get(u'url', ''),
            u'error': error}
