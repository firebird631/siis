# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Syncer tools

import sys
import logging
import traceback

from terminal.terminal import Terminal
from database.database import Database


def do_sync(options, siis_logger):
    """
    Make a connection and synchronize the market data in local DB.
    @todo
    """
    Terminal.inst().info("Starting SIIS syncer...")
    Terminal.inst().flush()

    # @todo connect only fetch market info data and prefetched markets OHLCs and say bye

    Terminal.inst().info("Sync done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
