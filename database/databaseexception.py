# @date 2018-09-08
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Database exceptions classes

from app.appexception import ServiceException


class DatabaseServiceException(ServiceException):

    def __init__(self, message):
        super().__init__("database", message)

    def __str__(self):
        return 'DatabaseServiceException (%s) : %s' % (self.service_name, self.message)


class DatabaseException(DatabaseServiceException):

    def __init__(self, database_name, message):
        super().__init__(message)

        self.database_name = database_name

    def __str__(self):
        return 'DatabaseException (%s:%s) : %s' % (self.database_name, self.message)
