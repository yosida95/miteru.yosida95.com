#-*- coding: utf-8 -*-

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
