# @date 2021-05-16
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2021 Dream Overflow
# History tools

import sys
import logging
import traceback

from tools.tool import Tool
from config import utils

from terminal.terminal import Terminal

from watcher.watcher import Watcher
from watcher.service import WatcherService

import logging
logger = logging.getLogger('siis.tools.history')
error_logger = logging.getLogger('siis.tools.error.history')


class History(Tool):
    """
    Make a connection and take the history of orders or position.
    """ 

    @classmethod
    def alias(cls):
        return "hist"

    @classmethod
    def help(cls):
        return ("Process a checkout of the history of orders or position from a particular account and period.",
                "Specify --profile, --broker, --from, --to.",
                "Optional --market, --filename.")

    @classmethod
    def detailed_help(cls):
        return tuple()

    @classmethod
    def need_identity(cls):
        return True

    def __init__(self, options):
        super().__init__("history", options)

        self._watcher_service = None

        self._identity = options.get('identity')
        self._identities_config = utils.identities(options.get('config-path'))

        self._profile = options.get('profile', 'default')

        self._profile_config = utils.load_config(options, "profiles/%s" % self._profile)

    def check_options(self, options):
        if not options.get('from') or not options.get('to'):
            logger.error("Options from, and to must be defined")
            return False

        if not options.get('broker'):
            logger.error("Options broker must be defined")
            return False

        if options.get('filename'):
            if options['filename'][-4:] == '.csv':
                logger.error("Base filename only must be specified")
                return False

        return True

    def init(self, options):
        Terminal.inst().info("Starting watcher's service...")
        self._watcher_service = WatcherService(None, options)

        return True

    def run(self, options):
        strategy = self._profile_config.get('strategy', {})

        if not strategy:
            logger.error("Missing strategy")
            return False

        watchers = self._profile_config.get('watchers', {})

        if not watchers or options['broker'] not in watchers:
            logger.error("Missing watcher")
            return False

        watcher_id = options['broker']

        if not watcher_id:
            logger.error("Missing watcher name")
            return False

        markets = options['market'].split(',') if options.get('market') else None

        fetcher = self._watcher_service.create_fetcher(options, options['broker'])
        if fetcher:           
            fetcher.connect()

            orders = []

            try:
                orders = fetcher.fetch_orders_history(options.get('from'), options.get('to'), markets)
            except Exception as e:
                error_logger.error(str(e))

            if options.get('filename'):
                self.export_to_csv(orders, options['filename'])
            else:
                self.display(orders)

            fetcher.disconnect()

        return True

    def export_to_csv(orders, filename):
        pass

    def display(self, orders):
        for o in orders:
            # format to display or to CSV
            print(o)

    def terminate(self, options):
        self._watcher_service.terminate()

        return True

    def forced_interrupt(self, options):
        return True


tool = History
