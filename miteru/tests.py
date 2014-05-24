# -*- coding: utf-8 -*-

import unittest

from pyramid import testing
from pyramid.i18n import TranslationStringFactory

from miteru.models import Tweet
from miteru.compat import unichr

_ = TranslationStringFactory('miteru')
LEADER = unichr(0x22ef)


class TestTweet(unittest.TestCase):

    HTTP = 'http://example.com/'
    HTTPS = 'https://example.com/'

    def test_build_01(self):
        inst = Tweet('title', self.HTTP, 'comment')
        self.assertEqual(
            inst.build(),
            'comment - title : http://example.com/ #miteru'
        )

    def test_build_02(self):
        inst = Tweet('', self.HTTP, 'comment')
        self.assertEqual(
            inst.build(),
            'comment - http://example.com/ #miteru'
        )

    def test_build_03(self):
        inst = Tweet(' '.join(self.HTTP for _ in range(5)), self.HTTP,
                     'comment')
        self.assertEqual(
            inst.build(),
            u'comment - {title} {leader} : http://example.com/ #miteru'.format(
                title=' '.join(self.HTTP for _ in range(4)),
                leader=LEADER,
            )
        )

    def test_build_04(self):
        inst = Tweet(
            '{0} extra title'.format(' '.join(self.HTTP for _ in range(4))),
            self.HTTP, 'comment')
        self.assertEqual(
            inst.build(),
            u'comment - {title} extr{leader} : '
            u'http://example.com/ #miteru'.format(
                title=' '.join(self.HTTP for _ in range(4)),
                leader=LEADER,
            )
        )

    def test_build_05(self):
        inst = Tweet('', self.HTTP,
                     ' '.join(self.HTTP for _ in range(5)))

        with self.assertRaises(ValueError):
            inst.build()

    def test_build_06(self):
        inst = Tweet('example.com', self.HTTP, 'comment')
        self.assertEqual(
            inst.build(),
            'comment - example.com : http://example.com/ #miteru'
        )

    def test_build_07(self):
        title = (
            'http://example.com/ verylongverylongverylong'  # 47
            'verylongverylongverylongverylongverylong'  # 40
            'verylongverylongverylongverylongverylong'  # 40
        )  # 127
        # 140 - (22(HTTP) + 7(comment) + 7(hashtag) + 7(spaces)) = 97
        inst = Tweet(title, self.HTTP, 'comment')
        self.assertEqual(
            inst.build(),
            u'comment - {title}{leader} : {url} #miteru'.format(
                title=title[:-31],
                leader=LEADER,
                url=self.HTTP,
            )
        )

    def test_build_08(self):
        inst = Tweet(
            '{0} extra title {1}'.format(
                ' '.join(self.HTTP for _ in range(4)), self.HTTP
            ),
            self.HTTP, 'comment')
        self.assertEqual(
            inst.build(),
            u'comment - {title} extr{leader} : '
            u'http://example.com/ #miteru'.format(
                title=' '.join(self.HTTP for _ in range(4)),
                leader=LEADER,
            )
        )
