# @date 2018-09-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Watcher exceptions classes

from app.appexception import ServiceException


class WatcherServiceException(ServiceException):

    def __init__(self, message):
        super().__init__("watcher", message)

    def __str__(self):
        return 'WatcherServiceException (%s) : %s' % (self.service_name, self.message)


class WatcherException(WatcherServiceException):

    def __init__(self, watcher_name, message):
        super().__init__(message)

        self.watcher_name = watcher_name

    def __str__(self):
        return 'WatcherException (%s:%s) : %s' % (self.watcher_name, self.message)
