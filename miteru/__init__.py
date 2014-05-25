# -*- coding: utf-8 -*-

from pyramid.config import Configurator
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from sqlalchemy import engine_from_config

from miteru.models import (
    Base,
    DBSession,
    TwitterAPI,
)


session_factory =\
    UnencryptedCookieSessionFactoryConfig('TDKb7XQ3SdgafTBEVrsXC325TYaXpEM3')


def main(global_config, **settings):
    settings = dict(settings)
    settings.setdefault('jinja2.i18n.domain', 'miteru')

    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine

    TwitterAPI.CLIENT_KEY = settings.get('twitter.client_key')
    TwitterAPI.CLIENT_SECRET = settings.get('twitter.client_secret')

    config = Configurator(settings=settings,
                          session_factory=session_factory)

    config.add_translation_dirs('locale/')

    config.add_static_view('static', 'static')

    config.add_route('homepage', '/')
    config.add_route('login', '/login')
    config.add_route('authorization', '/authorization')
    config.add_route('token', '/token')
    config.add_route('post', '/post')
    config.add_route('message', '/message')
    config.scan()

    return config.make_wsgi_app()
