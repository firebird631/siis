# @date 2020-01-02
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2020 Dream Overflow
# Cleaner tools

import sys

from common.utils import timeframe_from_str
from tools.tool import Tool

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.cleaner')
error_logger = logging.getLogger('siis.error.tools.cleaner')


class Cleaner(Tool):
    """
    Clean the database for a specific data set.
    """ 

    @classmethod
    def alias(cls):
        return "clean"

    @classmethod
    def help(cls):
        return ("Remove some data from the database.",
                "Specify --broker, --spec and --market.",
                "Optional : --from date, --to date, --timeframe.")

    @classmethod
    def detailed_help(cls):
        return tuple()

    @classmethod
    def need_identity(cls):
        return False

    def __init__(self, options):
        super().__init__("cleaner", options)

        self._timeframe = None
        self._from_date = None
        self._to_date = None
        self._bar_size = None

    def check_options(self, options):
        if not options.get('broker'):
            Terminal.inst().message("Missing broker identifier !")
            return False

        if not options.get('market'):
            Terminal.inst().message("Missing market identifier !")
            return False

        # default no initial fetch, opt-in
        if not options.get('spec'):
            Terminal.inst().message("Missing spec (market,liquidation,ohlc,range-bar) !")
            return False

        if options['spec'] == 'ohlc':
            if 'timeframe' not in options:
                Terminal.inst().message("Missing timeframe !")
                return False

            try:
                self._timeframe = timeframe_from_str(options['timeframe'])
            except ValueError:
                Terminal.inst().message("Invalid timeframe format for OHLC (example 4h) !")
                return False

            if self._timeframe <= 0:
                Terminal.inst().message("Invalid timeframe for OHLC !")
                return False

        if options['spec'] == 'range-bar':
            if 'timeframe' not in options:
                Terminal.inst().message("Missing timeframe with range-bar size format (example 30rb) !")
                return False

            try:
                self._bar_size = int(options['timeframe'][:-2])
            except ValueError:
                Terminal.inst().message("Invalid timeframe format for range-bar size (example 30rb) !")
                return False

        self._from_date = options.get('from')
        self._to_date = options.get('to')

        return True

    def init(self, options):
        # database manager
        Database.create(options)
        Database.inst().setup(options)

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
                if options['spec'] == 'ohlc':
                    Database.inst().cleanup_ohlc(broker_id=broker_id, market_id=market_id,
                                                 timeframe=self._timeframe,
                                                 from_date=self._from_date, to_date=self._to_date)

                elif options['spec'] == 'range-bar':
                    Database.inst().cleanup_range_bar(broker_id=broker_id, market_id=market_id,
                                                      bar_size=self._bar_size,
                                                      from_date=self._from_date, to_date=self._to_date)

        return True

    def terminate(self, options):
        Database.terminate()

        return True

    def forced_interrupt(self, options):
        return True

    #
    # clean bars methods
    #

    def clean_ohlc_bars(self, broker_id: str, market_id: str, timeframe: float, from_ts: float, to_ts: float):
        pass

    def clean_range_bars(self, broker_id: str, market_id: str, bar_size: int, from_ts: float, to_ts: float):
        pass


tool = Cleaner
