# @date 2019-11-04
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Notifier exceptions classes

class NotifierServiceException(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'NotifierServiceException : %s' % (self.message)


class NotifierException(NotifierServiceException):

    def __init__(self, name, identifier, message):
        super().__init__(message)

        self.notifier_name = name
        self.inst_identifier = identifier

    def __str__(self):
        return 'NotifierException (%s:%s) : %s' % (
            self.notifier_name, self.inst_identifier, self.message)
