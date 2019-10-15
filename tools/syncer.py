# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Syncer tools

import sys
import logging
import traceback

from terminal.terminal import Terminal
from database.database import Database

from watcher.watcher import Watcher
from watcher.service import WatcherService

import logging
logger = logging.getLogger('siis.tools.syncer')


def do_syncer(options):
    """
    Make a connection and synchronize the market data in local DB.
    """
    Terminal.inst().info("Starting SIIS syncer using %s identity..." % options['identity'])
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    # default no initial fetch, opt-in
    if 'initial-fetch' not in options:
        options['initial-fetch'] = False

    # watcher service
    Terminal.inst().info("Starting watcher's service...")
    watcher_service = WatcherService(options)

    markets = options['market'].split(',')

    watcher = watcher_service.create_watcher(options, options['broker'], markets)
    if watcher:
        watcher.initial_fetch = options.get('initial-fetch', False)

        watcher.connect()
        watcher.update_markets_info()
        watcher.disconnect()

    watcher_service.terminate()

    Database.terminate()

    Terminal.inst().info("Sync done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
