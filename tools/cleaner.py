# @date 2020-01-02
# @author Frederic SCHERMA
# @license Copyright (c) 2020 Dream Overflow
# Cleaner tools

import sys
import logging
import traceback

from tools.tool import Tool

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.cleaner')
error_logger = logging.getLogger('siis.error.tools.cleaner')


class Cleaner(Tool):
    """
    Clean the database for a specific data set.
    @todo timeframe(s), --from, --to
    """ 

    @classmethod
    def alias(cls):
        return "clean"

    @classmethod
    def help(cls):
        return ("Remove some data from the database.",
                "Specify --broker. Optional : --market, --from and --to date, --timeframe, --objects.")

    @classmethod
    def detailed_help(cls):
        return tuple()

    @classmethod
    def need_identity(cls):
        return False

    def __init__(self, options):
        super().__init__("cleaner", options)

    def check_options(self, options):
        if options.get('broker'):
            return True

        return False

    def init(self, options):
        # database manager
        Database.create(options)
        Database.inst().setup(options)

        # default no initial fetch, opt-in
        if 'object' not in options:
            options['object'] = "ohlc"

        return True

    def run(self, options):
        broker_id = options.get('broker')
        markets = options.get('market').split(',') if options.get('market', None) else None

        if not options.get('no-conf', False):
            sys.stdout.write("Confirm you want to delete [Y/n] ? ")
            confirm = input()

            if confirm != 'Y':
                Terminal.inst().message("Canceled !")
                return True

        Terminal.inst().message("Processing...")

        if markets:
            for market_id in markets:
                Database.inst().cleanup_ohlc(broker_id=broker_id, market_id=market_id)
        else:
            Database.inst().cleanup_ohlc(broker_id)

        return True

    def terminate(self, options):
        Database.terminate()

        return True

    def forced_interrupt(self, options):
        return True


tool = Cleaner
