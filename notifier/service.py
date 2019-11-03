# @date 2019-10-02
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Service responsible of the differents configured and enabled notifiers.

import json
import time, datetime
import threading
import base64, hashlib

from common.service import Service

from config import utils

import logging
logger = logging.getLogger('siis.notifier.service')


class NotifierService(Service):
    """
    Notifier service.
    @todo
    """

    def __init__(self, options):
        super().__init__("notifier", options)

        self._notifiers = {}

    def start(self, options):
        pass

    def terminate(self):
        self.lock()
        for k, notifier in self._notifiers.items():
            notifier.terminate()

        self._notifiers = {}

        self.unlock()

    def add_notifier(self, notifier):
        if not notifier:
            return

        self.lock()

        if notifier.identifier in self._notifiers:
            raise Exception("Notifier %s already registred" % notifier.identifier)

        self._notifiers[notifier.identifier] = notifier
        self.unlock()
