#-*- coding: utf-8 -*-

import re

from mongoengine import (
    BooleanField,
    connect,
    DateTimeField,
    Document,
    IntField,
    ReferenceField,
    StringField,
)

from .constants import MONGO_HOST

connect('miteru', host=MONGO_HOST, port=27017)


class User(Document):
    user_id = IntField(unique=True)
    key = StringField()
    access_key = StringField()
    access_secret = StringField()


class Token(Document):
    token = StringField(unique=True)
    user = ReferenceField(User, required=True)
    domain = StringField()
    expiration = DateTimeField()
    available = BooleanField(default=True)


class PostBuilder(object):
    pattern = ur'((?<![\w])(https?://)?\w+([\w\-]+\w)?(\.\w+([\w\-]+\w)?)+'\
        + ur'(/([\w\.\-\$&%/:=#~!]*\??[\w\.\-\$&%/:=#~!]*[\w&/=#])?)?)'

    def __init__(self, url, title, comment=u''):
        self.url = url
        self.title = title
        self.comment = comment

    def _get_shortened_url_length(self, url):
        return 23 if url.startswith(u'https') else 22

    def _get_text_length(self, text):
        length = len(text)
        for url in re.findall(self.pattern, text):
            length += self._get_shortened_url_length(url[0]) - len(url[0])

        return length

    def _round_text(self, text, length):
        matches = [url[0] for url in re.findall(self.pattern, text)]
        if matches and self._get_text_length(text) > length:
            deviation = 0
            result = u''
            index = 0

            for url in matches:
                index += text[index:].index(url)

                if index + deviation + self._get_shortened_url_length(url)\
                        >= length:
                    break

                deviation += self._get_shortened_url_length(url) - len(url)
            else:
                index = len(text)

            result = text[:index][:length - deviation]

            if len(result) + deviation is length:
                return u'%s…' % result[:-1]
            else:
                return u'%s…' % result
        else:
            return text[:length]

    def build(self):
        if len(self.title) > 0 and len(self.comment) > 0:
            base = u'%s - %s : %s #miteru'
            assert self._get_text_length(self.comment)\
                <= 143 - len(base) - self._get_shortened_url_length(self.url)

            text = base % (
                self.comment,
                self._round_text(
                    self.title,
                    146 - len(base) - self._get_text_length(self.comment)
                    - self._get_shortened_url_length(self.url)
                ),
                self.url
            )
        elif len(self.title) > 0:
            base = u'%s : %s #miteru'
            text = base % (
                self._round_text(
                    self.title,
                    144 - len(base) - self._get_shortened_url_length(self.url)
                ),
                self.url
            )
        elif len(self.comment) > 0:
            base = u'%s - %s #miteru'
            assert self._get_text_length(self.comment)\
                <= 144 - len(base) - self._get_shortened_url_length(self.url)

            text = u'%s - %s #miteru' % (self.comment, self.url)
        else:
            text = u'%s #miteru' % self.url

        return text
