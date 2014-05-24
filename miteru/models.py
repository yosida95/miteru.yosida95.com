# -*- coding: utf-8 -*-

import hashlib
import hmac
import random
import re
import string
import uuid
from datetime import (
    datetime,
    timedelta,
)

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
    Boolean,
    String,
    DateTime,
)
from sqlalchemy.dialects.mysql import BIGINT
from zope.sqlalchemy import ZopeTransactionExtension

from miteru.compat import unichr


DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


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

    status_id = Column(BIGINT(unsigned=True), nullable=False)

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
            func.count(SharedKey.key)
        ).filter(
            SharedKey.key == key
        ).first()

        return count[0] < 1


class OnetimeToken(Base):
    __tablename__ = 'onetime_tokens'

    id = Column(String(36), primary_key=True)
    token = Column(String(40), nullable=False)
    key_key = Column(String(40), ForeignKey(SharedKey.key), nullable=False)
    key = relationship(SharedKey,
                       backref=backref('onetime_tokens', uselist=True))
    domain = Column(String(255), nullable=False)
    expires_in = Column(DateTime(), nullable=False)
    is_used = Column(Boolean(), nullable=False)

    def __init__(self, key, token, domain, expires_in):
        self.id = str(uuid.uuid4())
        self.key = key
        self.token = token
        self.domain = domain
        self.expires_in = expires_in
        self.is_used = False

    def mark_as_used(self):
        self.is_used = True

    @property
    def available(self):
        return not self.is_used and self.expires_in >= datetime.now()

    @classmethod
    def new(cls, key_id, domain, now=lambda: datetime.now()):
        pool = string.ascii_letters + string.digits
        token = ''.join(random.choice(pool) for _ in range(40))

        key = DBSession.query(
            SharedKey
        ).filter(
            SharedKey.id == key_id
        ).first()
        if key is None:
            raise ValueError('認証に失敗しました')

        expires_in = now() + timedelta(minutes=10)

        inst = cls(key, token, domain, expires_in)
        DBSession.add(inst)
        return inst

    @classmethod
    def from_token(cls, token):
        token = DBSession.query(
            cls
        ).filter(
            cls.token == token,
        ).first()
        if token is None or not token.available:
            raise ValueError(token)

        return token


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
            raise ValueError('The comment is to long...')

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

        factor[index] = self.title[:position] + unichr(0x22ef)
        return ' '.join(factor)

    def to_dict(self, token, token_hashed):
        return {
            'title': self.title,
            'url': self.url,
            'comment': self.comment,
            'token': token,
            'token_hashed': token_hashed,
        }

    def authenticate(self, token, token_hashed):
        try:
            token = OnetimeToken.from_token(token)
        except ValueError:
            raise ValueError('認証に失敗しました。')
        else:
            token.mark_as_used()
            mac = hmac.new(token.key.key.encode('utf-8'), hashlib.sha1)
            mac.update(self.token)
            if mac.hexdigest() != token_hashed:
                raise ValueError('認証に失敗しました。')

            return True

    def do(self, token, token_hashed):
        self.authenticate(token, token_hashed)

        raise NotImplementedError
