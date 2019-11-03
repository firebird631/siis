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
        self._notifiers_insts = {}

        self._profile = options.get('profile', 'default')
        self._profile_config = utils.load_config(options, "profiles/%s" % self._profile)

    def start(self, options):
        for k in self._profile_config.get('notifiers', []):
            notifier_conf = utils.load_config(options, "notifiers/%s" % k)

            if self._notifiers_insts.get(k) is not None:
                logger.error("Notifier %s already started" % k)
                continue

            if notifier_conf.get("status") is not None and notifier_conf.get("status") == "enabled":
                # retrieve the classname and instanciate it
                notifier_conf = notifier.get('notifier')

                if not notifier_model or not notifier_model.get('name'):
                    logger.error("Invalid notifier configuration for %s !" % k)

                Clazz = self._notifiers.get(strategy['name'])
                if not Clazz:
                    logger.error("Unknown strategy name %s for appliance %s !" % (strategy['name'], k))

                inst = Clazz(self, parameters)
                inst.set_identifier(k)

                if inst.start():
                    self._notifiers_insts[k] = inst

    def terminate(self):
        for k, notifier in self._notifiers_insts.items():
            # stop workers
            if notifier.running:
                notifier.stop()

        for k, notifier in self._notifiers_insts.items():
            # join them
            if notifier.thread.is_alive():
                notifier.thread.join()

        self._notifiers_insts = {}
