# @date 2019-09-18
# @author Frederic SCHERMA
# @license Copyright (c) 2017 Dream Overflow
# Ohlc rebuilder from ticks/trades data tool

import sys
import logging
import traceback

from datetime import datetime

from common.utils import UTC, TIMEFRAME_FROM_STR_MAP

from terminal.terminal import Terminal
from database.database import Database


def do_rebuilder(options, siis_logger):
    Terminal.inst().info("Starting SIIS rebuilder using %s identity..." % options['identity'])
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

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
        siis_logger.error("Invalid timeframe")
        sys.exit(-1)

    # @todo tick streamer + inject in a cascaded generator

    Terminal.inst().info("Flushing database...")
    Terminal.inst().flush() 

    Database.terminate()

    Terminal.inst().info("Rebuild done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
