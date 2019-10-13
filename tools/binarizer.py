# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Binarizer tools

import sys
import logging
import traceback

from common.utils import UTC, TIMEFRAME_FROM_STR_MAP

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.fetcher')


def do_binarizer(options):
    from database.tickstorage import TextToBinary

    Terminal.inst().info("Starting SIIS binarizer...")
    Terminal.inst().flush()

    timeframe = -1

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

    if timeframe < 0:
        logger.error("Invalid timeframe !")
        sys.exit(-1)

    converter = TextToBinary(options['markets-path'], options['broker'], options['market'], options.get('from'), options.get('to'))
    converter.process()

    Terminal.inst().info("Binarization done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
