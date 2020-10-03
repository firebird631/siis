# @date 2018-09-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Monitor exceptions classes

from app.appexception import ServiceException


class MonitorServiceException(ServiceException):

    def __init__(self, message):
        super().__init__("monitor", message)

    def __str__(self):
        return 'MonitorServiceException (%s) : %s' % (self.service_name, self.message)


class MonitorException(MonitorServiceException):

    def __init__(self, monitor_name, message):
        super().__init__(message)

        self.monitor_name = monitor_name

    def __str__(self):
        return 'MonitorException (%s:%s) : %s' % (self.monitor_name, self.message)
