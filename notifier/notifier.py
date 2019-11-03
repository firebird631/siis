# @date 2019-10-02
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Notifier module.

from common.runnable import Runnable

import logging
logger = logging.getLogger('siis.notifier')


class Notifier(Runnable):
    """
    Notifier service.
    @todo
    """

    def __init__(self, name, identifier, service):
        super().__init__("nt-%s" % name)

        self._name = name
        self._identifier = identifier
        self._notifier_service = service

        self._activity = True  # trading activity

    @property
    def name(self):
        return self._name

    @property
    def identifier(self):
        """Unique notifier identifier"""
        return self._identifier

    @property
    def service(self):
        return self._notifier_service

    def start(self, options):
        pass

    def terminate(self):
        pass

    def notify(self):
        pass

    def pre_run(self):
        Terminal.inst().info("Running notifier %s - %s..." % (self._name, self._identifier), view='content')

    def post_run(self):
        Terminal.inst().info("Joining notifier %s - %s..." % (self._name, self._identifier), view='content')

    def post_update(self):
        pass

    def update(self):
        pass
