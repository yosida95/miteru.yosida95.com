#-*- coding: utf-8 -*-

import os

from paste.deploy import loadapp

app = loadapp(u'config:%s' % os.path.join(
    os.path.dirname(os.path.abspath(__file__)), u'./production.ini'
))
