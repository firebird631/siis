# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Siis standard implementation of the application (application main)

import sys
import logging
import traceback

from common.utils import UTC, TIMEFRAME_FROM_STR_MAP

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.optimizer')


def do_optimizer(options):
    Terminal.inst().info("Starting SIIS optimizer...")
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    broker_id = options['broker']
    market_id = options['market']

    timeframe = -1
    cascaded = None

    if options.get('timeframe') and options['timeframe'] in TIMEFRAME_FROM_STR_MAP:
        timeframe = TIMEFRAME_FROM_STR_MAP[options['timeframe']]
    else:
        try:
            timeframe = int(options['timeframe'])
        except:
            pass

    if timeframe < 0:
        logger.error("Invalid timeframe")
        sys.exit(-1)

    if timeframe == 0:
        # tick
        pass
        # @todo 
    else:
        # ohlc
        pass
        # @todo

    Terminal.inst().info("Flushing database...")
    Terminal.inst().flush() 

    Database.terminate()

    Terminal.inst().info("Optimization done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
