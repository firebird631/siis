# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Syncer tools

import sys
import logging
import traceback

from tools.tool import Tool
    
from terminal.terminal import Terminal
from database.database import Database

from watcher.watcher import Watcher
from watcher.service import WatcherService

import logging
logger = logging.getLogger('siis.tools.syncer')
error_logger = logging.getLogger('siis.tools.error.syncer')


class Syncer(Tool):
    """
    Make a connection and synchronize the market data in local DB.
    @todo merge do_syncer into this model
    """ 

    @classmethod
    def alias(cls):
        return "sync"

    @classmethod
    def help(cls):
        return ("Process a synchronization of the watched market from a particular broker.",
                "Specify --broker, --market.",
                "Optional --initial-fetch, default False.")

    @classmethod
    def detailed_help(cls):
        return tuple()

    @classmethod
    def need_identity(cls):
        return True

    def __init__(self, options):
        super().__init__("syncer", options)

        self._watcher_service = None

    def check_options(self, options):
        if options.get('market') and options.get('broker'):
            return True

        return False

    def init(self, options):
        # database manager
        Database.create(options)
        Database.inst().setup(options)

        # want speedup the database inserts
        Database.inst().enable_fetch_mode()

        # default no initial fetch, opt-in
        if 'initial-fetch' not in options:
            options['initial-fetch'] = False

        return True

    def run(self, options):
        Terminal.inst().info("Starting watcher's service...")
        self._watcher_service = WatcherService(options)

        markets = options['market'].split(',')

        watcher = self._watcher_service.create_watcher(options, options['broker'], markets)
        if watcher:           
            watcher.initial_fetch = options.get('initial-fetch', False)

            watcher.connect()

            markets = watcher.matching_symbols_set(markets, watcher.available_instruments())

            for market_id in markets:
                watcher._watched_instruments.add(market_id)

            try:
                watcher.update_markets_info()
            except Exception as e:
                error_logger.error(str(e))

            watcher.disconnect()

        return True

    def terminate(self, options):
        self._watcher_service.terminate()

        Database.terminate()

        return True

    def forced_interrupt(self, options):
        return True


tool = Syncer
