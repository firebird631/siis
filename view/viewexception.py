# @date 2018-09-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# View exceptions classes

from app.appexception import ServiceException


class ViewServiceException(ServiceException):

    def __init__(self, message):
        super().__init__("view", message)

    def __str__(self):
        return 'ViewServiceException (%s) : %s' % (self.service_name, self.message)


class ViewException(ViewServiceException):

    def __init__(self, view_name, message):
        super().__init__(message)

        self.view_name = view_name

    def __str__(self):
        return 'ViewException (%s) : %s' % (self.view_name, self.message)
