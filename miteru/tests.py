#-*- coding: utf-8 -*-

import unittest

from pyramid import testing
from pyramid.i18n import TranslationStringFactory

_ = TranslationStringFactory('miteru')


class PostBuilderTest(unittest.TestCase):

    def _get_target_instance(self, *args, **kwargs):
        from .models import PostBuilder
        return PostBuilder(*args, **kwargs)

    def test_get_shortened_url_length(self):
        inst = self._get_target_instance(
            u'http://example.com/', u'example', u'comment'
        )

        self.assertEqual(
            inst._get_shortened_url_length(u'http://www.google.com/'), 22
        )
        self.assertEqual(
            inst._get_shortened_url_length(u'https://www.google.com/'), 23
        )
        self.assertEqual(
            inst._get_shortened_url_length(u'www.google.com'), 22
        )

    def test_get_text_length(self):
        inst = self._get_target_instance(
            u'http://example.com/', u'example', u'comment'
        )

        self.assertEqual(inst._get_text_length(u'hello'), 5)
        self.assertEqual(
            inst._get_text_length(u'hello http://www.google.com/'), 28
        )
        self.assertEqual(
            inst._get_text_length(u'hello https://www.google.com/'), 29
        )
        self.assertEqual(
            inst._get_text_length(u'hello http://www.google.com/hello'), 28
        )
        self.assertEqual(inst._get_text_length(
            u'http://www.google.com/ http://wwww.yahoo.com/'
        ), 45)

    def test_round_text(self):
        inst = self._get_target_instance(
            u'http://example.com/', u'example', u'comment'
        )
        check = lambda length, correct: self.assertEqual(inst._round_text(
            u'abcdefg http://example.com/ hijklmn https://example.com/', length
        ), correct)

        check(5, u'abcd…')
        check(30, u'abcdefg …')
        check(38, u'abcdefg http://example.com/ hijklm…')
        check(61, u'abcdefg http://example.com/ hijklmn …')
        check(62, u'abcdefg http://example.com/ hijklmn https://example.com/')
        check(100, u'abcdefg http://example.com/ hijklmn https://example.com/')

    def test_build(self):
        inst = self._get_target_instance(
            u'http://example.com/', u'example', u'comment'
        )
        self.assertEqual(
            inst.build(), u'comment - example : http://example.com/ #miteru'
        )

        inst = self._get_target_instance(
            u'http://example.com/', u'example', u'comment' * 14
        )
        self.assertEqual(
            inst.build(), u'%s - exampl : http://example.com/ #miteru' % (
                u'comment' * 14
            )
        )
        self.assertEqual(len(inst.build()), 137)

        inst = self._get_target_instance(
            u'http://example.com/', u'example' * 20
        )
        self.assertEqual(
            inst.build(), u'%s : http://example.com/ #miteru' % (
                u'example' * 15 + u'ex'
            )
        )
        self.assertEqual(len(inst.build()), 137)

        inst = self._get_target_instance(
            u'http://example.com/', u'', u'comment'
        )
        self.assertEqual(inst.build(), u'comment - http://example.com/ #miteru')

        inst = self._get_target_instance(
            u'http://example.com/', u'', u''
        )
        self.assertEqual(inst.build(), u'http://example.com/ #miteru')
