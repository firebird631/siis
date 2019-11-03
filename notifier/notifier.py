# @date 2019-10-02
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Notifier module.

import logging
logger = logging.getLogger('siis.notifier')


class Notifier(object):
    """
    Notifier service.
    @todo
    """

    def __init__(self, name, identifier, service):
        self._name = name
        self._identifier = identifier
        self._service = service

    def start(self, options):
        pass

    def terminate(self):
        pass

    def notify(self):
        pass
