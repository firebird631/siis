# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Fetcher tool

import sys
import logging
import traceback

from datetime import datetime

from common.utils import UTC, TIMEFRAME_FROM_STR_MAP

from watcher.service import WatcherService

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.fetcher')


def do_fetcher(options):
    Terminal.inst().info("Starting SIIS fetcher using %s identity..." % options['identity'])
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    # want speedup the database inserts
    Database.inst().enable_fetch_mode()

    watcher_service = WatcherService(options)
    fetcher = watcher_service.create_fetcher(options, options['broker'])

    timeframe = -1
    cascaded = None

    if not options.get('timeframe'):
        timeframe = 60  # default to 1min
    else:
        if options['timeframe'] in TIMEFRAME_FROM_STR_MAP:
            timeframe = TIMEFRAME_FROM_STR_MAP[options['timeframe']]
        else:
            try:
                timeframe = int(options['timeframe'])
            except:
                pass

    if not options.get('cascaded'):
        cascaded = None
    else:
        if options['cascaded'] in TIMEFRAME_FROM_STR_MAP:
            cascaded = TIMEFRAME_FROM_STR_MAP[options['cascaded']]
        else:
            try:
                cascaded = int(options['cascaded'])
            except:
                pass

    if timeframe < 0:
        logger.error("Invalid timeframe")
        sys.exit(-1)

    try:
        fetcher.connect()
    except:
        sys.exit(-1)

    if fetcher.connected:
        logger.info("Fetcher authentified to %s, trying to collect data..." % fetcher.name)

        markets = fetcher.matching_symbols_set(options['market'].split(','), fetcher.available_instruments())

        try:
            for market_id in markets:
                if not fetcher.has_instrument(market_id, options.get('spec')):
                    logger.error("Market %s not found !" % (market_id,))
                else:
                    if options.get('install-market', False):
                        fetcher.install_market(market_id)
                    else:
                        fetcher.fetch_and_generate(market_id, timeframe,
                            options.get('from'), options.get('to'), options.get('last'),
                            options.get('spec'), cascaded)

        except KeyboardInterrupt:
            pass
        finally:
            fetcher.disconnect()

    fetcher = None

    Terminal.inst().info("Flushing database...")
    Terminal.inst().flush() 

    Database.terminate()

    Terminal.inst().info("Fetch done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
