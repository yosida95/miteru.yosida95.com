# -*- coding: utf-8 -*-


class MiteruException(Exception):

    def __init__(self, message, retriable):
        self.message = message
        self.retryable = retriable
