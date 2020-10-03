# @date 2018-09-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Trader exceptions classes

from app.appexception import ServiceException


class TraderServiceException(ServiceException):

    def __init__(self, message):
        super().__init__("trader", message)

    def __str__(self):
        return 'TraderServiceException (%s) : %s' % (self.service_name, self.message)


class TraderException(TraderServiceException):

    def __init__(self, trader_name, message):
        super().__init__(message)

        self.trader_name = trader_name

    def __str__(self):
        return 'TraderException (%s:%s) : %s' % (self.trader_name, self.message)
