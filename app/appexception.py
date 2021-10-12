# @date 2019-11-04
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# App exceptions classes


class AppException(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return 'AppException : %s' % self.message


class CommandHandlerException(AppException):

    def __init__(self, command_name, message):
        super().__init__(message)

    def __str__(self):
        return 'CommandHandlerException : %s' % self.message


class CommandException(CommandHandlerException):

    def __init__(self, command_name, message):
        super().__init__(message)

        self.command_name = command_name

    def __str__(self):
        return 'CommandException (%s) : %s' % (self.command_name, self.message)


class CommandExecException(CommandException):

    def __init__(self, command_name, message):
        super().__init__(command_name, message)

    def __str__(self):
        return 'CommandExecException (%s) : %s' % (self.command_name, self.message)


class CommandParseException(CommandException):

    def __init__(self, command_name, message):
        super().__init__(command_name, message)

    def __str__(self):
        return 'CommandParseException (%s) : %s' % (self.command_name, self.message)


class CommandAutocompleteException(CommandException):

    def __init__(self, command_name, message):
        super().__init__(command_name, message)

    def __str__(self):
        return 'CommandAutocompleteException (%s) : %s' % (self.command_name, self.message)


class ServiceException(AppException):

    def __init__(self, service_name, message):
        super().__init__(message)

        self.service_name = service_name

    def __str__(self):
        return 'ServiceException (%s) : %s' % (self.service_name, self.message)
