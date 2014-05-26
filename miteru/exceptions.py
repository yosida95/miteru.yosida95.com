# -*- coding: utf-8 -*-


class MiteruException(Exception):

    def __init__(self, message, retryable):
        self.message = message
        self.retryable = retryable
