# @date 2019-10-02
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Service responsible of the different configured and enabled notifiers.

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Union, List, Type

if TYPE_CHECKING:
    from .notifier import Notifier

from importlib import import_module

from common.signal import Signal
from common.service import Service

from config import utils
from notifier.notifierexception import NotifierServiceException

import logging
logger = logging.getLogger('siis.notifier.service')
error_logger = logging.getLogger('siis.error.notifier.service')


class NotifierService(Service):
    """
    Notifier service.
    """

    _notifiers: Dict[str, Type[Notifier, type]]
    _notifiers_insts: Dict[str, Union[Notifier, object]]

    def __init__(self, options):
        super().__init__("notifier", options)

        self._notifiers = {}
        self._notifiers_insts = {}

        self._profile = options.get('profile', 'default')
        self._profile_config = utils.load_config(options, "profiles/%s" % self._profile)

        if 'notifiers' not in self._profile_config:
            self._profile_config['notifiers'] = {}

        if 'desktop' not in self._profile_config['notifiers']:
            # always default add a desktop notifier, but could be disable opt-in in the profile
            self._profile_config['notifiers']['desktop'] = {
                'status': "enabled",
                'name': "desktop"
            }

        # notifiers config
        self._notifiers_config = self._init_notifier_config(options)

        # use to post formatted or raw tables of active and historical trades
        self._strategy_service = None
        self._trader_service = None

    def set_strategy_service(self, strategy_service):
        self._strategy_service = strategy_service

    def set_trader_service(self, trader_service):
        self._trader_service = trader_service

    @property
    def strategy_service(self):
        return self._strategy_service

    @property
    def trader_service(self):
        return self._trader_service

    def start(self, options):
        # notifiers
        for k, notifier in self._notifiers_config.items():
            if k == "default":
                continue

            if notifier.get("status") is not None and notifier.get("status") in ("load", "enabled"):
                # retrieve the class-name and instantiate it
                parts = notifier.get('classpath').split('.')

                module = import_module('.'.join(parts[:-1]))
                Clazz: Type[Notifier] = getattr(module, parts[-1])

                if not Clazz:
                    raise NotifierServiceException("Cannot load notifier %s" % k)

                self._notifiers[notifier.get("name")] = Clazz

        for k, conf in self._profile_config.get('notifiers', {}).items():
            if self._notifiers_insts.get(k) is not None:
                logger.error("Notifier %s already started" % k)
                continue

            if not conf or not conf.get('name'):
                logger.error("Invalid configuration for notifier %s. Ignored !" % k)
                continue

            notifier_conf = self._notifiers_config.get(k)
            if not notifier_conf:
                logger.error("Invalid configuration for notifier %s. Ignored !" % k)
                continue

            if notifier_conf.get("status") is not None and notifier_conf.get("status") in ("enabled", "load"):
                # retrieve the class-name and instantiate it
                if not notifier_conf.get('name'):
                    logger.error("Invalid notifier configuration for %s. Ignored !" % k)

                Clazz: Type[Notifier] = self._notifiers.get(notifier_conf['name'])
                if not Clazz:
                    logger.error("Unknown notifier name %s for %s. Ignored !" % (notifier_conf['name'], k))
                    continue

                inst = Clazz(k, self, options)
                inst.set_identifier(k)

                if inst.start(options):
                    self._notifiers_insts[k] = inst
                else:
                    logger.error("Unable to start notifier %s for %s. Ignored !" % (notifier_conf['name'], k))
                    continue

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

    def sync(self):
        pass

    def command(self, command_type: int, data: dict) -> dict:
        """
        Send a manual command to a specific notifier.
        """
        results = None

        with self._mutex:
            if data and 'notifier' in data:
                notifier_inst = self._notifiers_insts.get(data['notifier'])
                if notifier_inst:
                    results = notifier_inst.command(command_type, data)
            else:
                # multi command
                results = []

                for k, notifier_inst in self._notifiers_insts.items():
                    results.append(notifier_inst.command(command_type, data))

        return results

    def _init_notifier_config(self, options: dict) -> dict:
        """
        Get the profile configuration for a specific notifier name.
        """
        notifiers_profile = self._profile_config.get('notifiers', {})

        notifier_config = {}

        for k, profile_notifier_config in notifiers_profile.items():
            if not profile_notifier_config.get('name'):
                error_logger.error("Invalid configuration for notifier %s. Ignored !" % k)

            user_notifier_config = utils.load_config(options, 'notifiers/' + profile_notifier_config.get('name'))
            if user_notifier_config:
                # keep override
                notifier_config[k] = utils.merge_parameters(user_notifier_config, profile_notifier_config)

        return notifier_config

    def notifier_config(self, identifier: str) -> dict:
        """
        Get the configurations for a notifier as dict.
        """
        return self._notifiers_config.get(identifier, {})

    def receiver(self, signal: Signal):
        if signal.source == Signal.SOURCE_STRATEGY:
            if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_ALERT:

                # propagate the signal to the notifiers
                with self._mutex:
                    self._signals_handler.notify(signal)

    def notify(self, signal_type: int, source_name: str, signal_data):
        if signal_data is None:
            return

        signal = Signal(Signal.SOURCE_NOTIFIER, source_name, signal_type, signal_data)

        with self._mutex:
            self._signals_handler.notify(signal)

    def notifier(self, name: str) -> Union[Notifier, None]:
        return self._notifiers_insts.get(name)

    def notifiers_identifiers(self) -> List[str]:
        return [notifier.identifier for k, notifier in self._notifiers_insts.items()]
