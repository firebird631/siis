# @date 2020-01-02
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# Cleaner tools

import sys
import logging
import traceback

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.cleaner')
error_logger = logging.getLogger('siis.error.tools.cleaner')


def do_cleaner(options):
    """
    Clean the database for a specific data set.
    @todo timeframe(s), --from, --to
    """
    Terminal.inst().info("Starting SIIS cleaner...")
    Terminal.inst().flush()

    # default no initial fetch, opt-in
    if 'object' not in options:
        options['object'] = "ohlc"

    broker_id = options.get('broker')
    if not broker_id:
        error_logger.error("Undefined broker identifier")
        sys.exit(-1)

    markets = options.get('market').split(',') if options.get('market', None) else None

    if not options.get('no-conf', False):
        sys.stdout.write("Confirm you want to delete [Y/n] ? ")
        confirm = input()

        if confirm != 'Y':
            print("Canceled !")
            sys.exit(0)

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    print("Processing...")

    if markets:
        for market_id in markets:
            Database.inst().cleanup_ohlc(broker_id=broker_id, market_id=market_id)
    else:
        Database.inst().cleanup_ohlc(broker_id)

    Database.terminate()

    Terminal.inst().info("Cleanup done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
