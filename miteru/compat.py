# -*- coding: utf-8 -*-

import sys
PY3 = sys.version_info[0] >= 3

__all__ = ['unichr', 'parse_qs', 'urlencode', 'htmlentitydefs']


if PY3:
    unichr = chr

    from urllib.parse import (
        parse_qs,
        urlencode,
    )

    from html import entities as htmlentitydefs
else:
    unichr = unichr

    from urllib import urlencode
    from urlparse import parse_qs
    import htmlentitydefs
