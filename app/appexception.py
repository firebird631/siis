# @date 2019-11-04
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# App exceptions classes


class AppException(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'AppException : %s' % (self.message)


class CommandException(AppException):

    def __init__(self, command, message):
        super().__init__(message)

        self.command_name = command

    def __str__(self):
        return 'CommandException (%s) : %s' % (self.command_name, self.message)


class ServiceException(AppException):

    def __init__(self, service_name, message):
        super().__init__(message)

        self.service_name = service_name

    def __str__(self):
        return 'ServiceException (%s) : %s' % (self.service_name, self.message)
