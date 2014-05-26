# -*- coding: utf-8 -*-

import hashlib
import hmac
import json
import random
import re
import string
import uuid
from datetime import datetime

import requests
from requests_oauthlib import OAuth1
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    backref,
    relationship,
    scoped_session,
    sessionmaker,
)
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.schema import (
    Column,
    ForeignKey,
)
from sqlalchemy.sql.sqltypes import (
    String,
    DateTime,
)
from sqlalchemy.dialects.mysql import BIGINT
from zope.sqlalchemy import ZopeTransactionExtension

from miteru.compat import (
    parse_qs,
    unichr,
    urlencode,
)
from miteru.exceptions import MiteruException


DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()
LEADER = unichr(0x2026)


class User(Base):
    __tablename__ = 'users'

    id = Column(BIGINT(unsigned=True),
                primary_key=True, autoincrement=False)
    access_key = Column(String(128), nullable=False)
    access_secret = Column(String(128), nullable=False)

    def __init__(self, id):
        self.id = id
        self.access_key = ''
        self.access_secret = ''

    def set_access_token(self, key, secret):
        self.access_key = key
        self.access_secret = secret


class SharedKey(Base):
    __tablename__ = 'shared_keys'

    id = Column(String(36), primary_key=True)
    key = Column(String(40), unique=True, nullable=False)
    user_id = Column(BIGINT(unsigned=True), ForeignKey(User.id),
                     nullable=False)
    user = relationship(User, backref=backref('shared_keys', uselist=True))
    created_at = Column(DateTime(), nullable=False)
    deactivated_at = Column(DateTime(), nullable=True)

    def __init__(self, user, key, created_at):
        assert isinstance(user, User)
        assert isinstance(key, str)
        assert isinstance(created_at, datetime)

        self.id = str(uuid.uuid4())
        self.user = user
        self.key = key
        self.created_at = created_at

    def deactivate(self, now=lambda: datetime.now()):
        if callable(now):
            self.deactivated_at = now()
        else:
            self.deactivated_at = now

    @property
    def is_active(self, now=lambda: datetime.now()):
        if callable(now):
            now = now()

        return not self.deactivated_at or self.deactivated_at < now

    @classmethod
    def new(cls, user, now=lambda: datetime.now()):
        pool = string.ascii_letters + string.digits
        gen = lambda: ''.join(random.choice(pool) for _ in range(40))

        key = gen()
        while not cls._is_unique_key(key):
            key = gen()

        if callable(now):
            now = now()

        return cls(user, key, now)

    @classmethod
    def _is_unique_key(cls, key):
        count = DBSession.query(
            func.count(cls.key)
        ).filter(
            cls.key == key
        ).first()

        return count[0] < 1


class TwitterAPI:
    CLIENT_KEY = None
    CLIENT_SECRET = None

    def __new__(cls, *args, **kwargs):
        if cls.CLIENT_KEY is None:
            raise ValueError('CLIENT_KEY is not set')

        if cls.CLIENT_SECRET is None:
            raise ValueError('CLIENT_SECRET is not set')

        return super(TwitterAPI, cls).__new__(cls)

    def _get_user(self, user_id):
        user = DBSession.query(
            User
        ).filter(
            User.id == user_id
        ).first()
        if user is None:
            raise ValueError(user_id)

        return user

    def get_authorized_client(self, token, token_secret, verifier=None):
        return OAuth1(client_key=self.CLIENT_KEY,
                      client_secret=self.CLIENT_SECRET,
                      resource_owner_key=token,
                      resource_owner_secret=token_secret,
                      verifier=verifier)

    def get_unauthorized_client(self):
        return OAuth1(client_key=self.CLIENT_KEY,
                      client_secret=self.CLIENT_SECRET)

    def get_request_token(self):
        resp = requests.post(url='https://api.twitter.com/oauth/request_token',
                             auth=self.get_unauthorized_client())
        credentials = parse_qs(resp.content)
        request_token = credentials[b'oauth_token'][0].decode('utf-8')
        request_secret = credentials[b'oauth_token_secret'][0].decode('utf-8')

        return request_token, request_secret

    def get_authorization_url(self, request_token):
        return '{0}?{1}'.format(
            'https://api.twitter.com/oauth/authorize',
            urlencode([('oauth_token', request_token)]))

    def authorize(self, request_key, request_secret, verifier):
        resp = requests.post(
            url='https://api.twitter.com/oauth/access_token',
            auth=self.get_authorized_client(request_key, request_secret,
                                            verifier))
        if resp.status_code == 401:
            raise ValueError()
        elif resp.status_code != 200:
            raise Exception(resp.status_code)

        credentials = parse_qs(resp.content)

        try:
            user_id = int(credentials[b'user_id'][0].decode('utf-8'))
        except ValueError:
            raise Exception()

        try:
            user = self._get_user(user_id)
        except ValueError:
            user = User(user_id)
            DBSession.add(user)

        user.set_access_token(
            credentials[b'oauth_token'][0].decode('utf-8'),
            credentials[b'oauth_token_secret'][0].decode('utf-8'))

        key = SharedKey.new(user)
        DBSession.add(key)
        return key

    def post(self, user, text):
        resp = requests.post(
            url='https://api.twitter.com/1.1/statuses/update.json',
            data=json.dumps({'status': text}),
            auth=self.get_authorized_client(user.access_key,
                                            user.access_secret))

        if 200 <= resp.status_code < 300:
            return True

        try:
            body = resp.json()
            errors = body['errors']
        except (KeyError, ValueError):
            raise MiteruException(
                'TwitterAPI returns {0}'.format(resp.status_code), False)
        else:
            raise MiteruException(','.join(errors), False)


class Tweet:
    pattern = re.compile(
        r'((?<![\w])(https?://)?\w+([\w\-]+\w)?(\.\w+([\w\-]+\w)?)+'
        r'(/([\w\.\-\$&%/:=#~!]*\??[\w\.\-\$&%/:=#~!]*[\w&/=#])?)?)'
    )
    HTTP = 22
    HTTPS = 23
    HASHTAG = '#miteru'

    def __init__(self, title, url, comment):
        self.title = title
        self.url = url
        self.comment = comment

    def _detect_urls(self, text):
        http = []
        https = []

        urls = self.pattern.findall(text)
        if not urls:
            return http, https

        for url in urls:
            if url[0].startswith('https://'):
                https.append(url[0])
            else:
                http.append(url[0])

        return http, https

    def _calc_text_length(self, text):
        http, https = self._detect_urls(text)

        length = len(text)
        length += len(http) * self.HTTP - sum(map(len, http))
        length += len(https) * self.HTTPS - sum(map(len, https))
        return length

    def build(self):
        url_length = self.HTTPS if self.url.startswith('https') else self.HTTP
        comment_length = self._calc_text_length(self.comment)
        title_length = self._calc_text_length(self.title)

        gap = url_length - len(self.url)
        gap += comment_length - len(self.comment)
        gap += title_length - len(self.title)

        factor = []
        if comment_length > 0:
            factor.extend([self.comment, '-'])

        if title_length > 0:
            index = len(factor)
            factor.extend([self.title, ':'])
        else:
            index = -1

        factor.extend([self.url, self.HASHTAG])

        length = sum(map(len, factor)) + (len(factor) - 1) + gap
        if length <= 140:
            return ' '.join(factor)

        allowed_title_length = 140 - (length - title_length)
        if index < 0 or allowed_title_length < 5:
            raise MiteruException('The comment is to long...', True)

        rest = allowed_title_length - 1
        position = 0
        for match in self.pattern.finditer(self.title):
            if match.start() - position <= rest:
                rest -= match.start() - position
                position = match.start()
            else:
                position += rest
                break

            if match.group(3) == 'https://':
                url_length = self.HTTPS
            else:
                url_length = self.HTTP

            if url_length <= rest:
                rest -= url_length
                position = match.end()
            else:
                break
        else:
            position += rest

        factor[index] = self.title[:position] + LEADER
        return ' '.join(factor)

    def to_dict(self):
        return {
            'title': self.title,
            'url': self.url,
            'comment': self.comment,
        }

    def authenticate(self, key_id, signature, query):
        key = DBSession.query(
            SharedKey
        ).filter(
            SharedKey.id == key_id
        ).first()
        if key is None:
            raise MiteruException('認証に失敗しました。', False)

        expected_signature = hmac.new(
            key.key.encode('utf8'), query.encode('utf8'), hashlib.sha1
        ).hexdigest()
        if signature != expected_signature:
            raise MiteruException('認証に失敗しました。', False)

        return key.user

    def do(self, user):
        return TwitterAPI().post(user, self.build())
