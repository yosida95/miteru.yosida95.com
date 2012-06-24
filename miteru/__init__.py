from pyramid.config import Configurator
from pyramid.session import UnencryptedCookieSessionFactoryConfig

session_factory = UnencryptedCookieSessionFactoryConfig(
    'TDKb7XQ3SdgafTBEVrsXC325TYaXpEM3')


def main(global_config, **settings):
    """ This function returns a WSGI application.

    It is usually called by the PasteDeploy framework during
    ``paster serve``.
    """
    settings = dict(settings)
    settings.setdefault('jinja2.i18n.domain', 'miteru')
    config = Configurator(settings=settings,
                          session_factory=session_factory)
    config.add_translation_dirs('locale/')
    config.include('pyramid_jinja2')

    config.add_static_view('static', 'static')
    config.add_route('homepage', '/')
    config.add_route('login', '/login')
    config.add_route('authorization', '/authorization')
    config.add_route('token', '/token')
    config.add_route('post', '/post')
    config.add_route('message', '/message')
    config.scan()

    return config.make_wsgi_app()
