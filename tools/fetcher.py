# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Fetcher tool

import sys
import logging
import traceback

from datetime import datetime, timedelta

from common.utils import UTC, TIMEFRAME_FROM_STR_MAP

from watcher.service import WatcherService
from instrument.instrument import Instrument

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.fetcher')
error_logger = logging.getLogger('siis.error.tools.fetcher')


# class Fetcher(Tool):
#     """
#     Make a connection and fetch the market data in local DB.
#     """ 

#     @classmethod
#     def alias(cls):
#         return "fetch"

#     @classmethod
#     def help(cls):
#         return ("Process the data OHLC and tick/trade/quote fetcher.",
#                 "Specify --broker, --market, --timeframe, --from and --to date.",
#                 " Optional : --cascaded, --from or --update.")

#     @classmethod
#     def detailed_help(cls):
#         return tuple()

#     @classmethod
#     def need_identity(cls):
#         return True

#     def __init__(self, options):
#         super().__init__("fetcher", options)

#         self._watcher_service = None

#     def check_options(self, options):
#         if not options.get('market') or not options.get('broker'):
#             return False

#         if not options.get('to'):
#             return False

#         if not options.get('from') or not options.get('update'):
#             return False

#         if options.get('from') and options.get('update'):            
#             error_logger.error("Either --from or --update parameters must be defined")
#             return False

#         return True

#     def init(self, options):
#         # database manager
#         Database.create(options)
#         Database.inst().setup(options)

#         # want speedup the database inserts
#         Database.inst().enable_fetch_mode()

#         return True

#     def run(self, options):
#         Terminal.inst().info("Starting watcher's service...")
#         self._watcher_service = WatcherService(options)

#         markets = options['market'].split(',')

#         fetcher = watcher_service.create_fetcher(options, options['broker'])
#         if fetcher:
#             fetcher.connect()

#             for market_id in markets:
#                 pass  # @todo merge here

#             fetcher.disconnect()

#         return True

#     def terminate(self, options):
#         self._watcher_service.terminate()

#         Terminal.inst().info("Flushing database...")
#         Database.terminate()

#         return True

#     def forced_interrupt(self, options):
#         return True


# tool = Fetcher



def terminate(code=0):
    Terminal.inst().info("Flushing database...")
    Terminal.inst().flush() 

    Database.terminate()

    Terminal.inst().info("Fetch done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(code)


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
        timeframe = Instrument.TF_TICK  # default to tick
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
        error_logger.error("Invalid timeframe")
        sys.exit(-1)

    do_update = False

    if options.get('update'):
        # if options.get('from'):
        #     error_logger.error("Either --from or --update parameters must be defined")
        #     terminate(-1)
        # else:
        do_update = True

    try:
        fetcher.connect()
    except:
        terminate(-1)

    today = datetime.now().astimezone(UTC())

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
                        if do_update:
                            # update from last entry, compute the from datetime
                            if timeframe <= Instrument.TF_TICK:
                                # get last datetime from tick storage and add 1 millisecond
                                last_tick = Database.inst().get_last_tick(options['broker'], market_id)
                                next_date = datetime.fromtimestamp(last_tick[0] + 0.001, tz=UTC()) if last_tick else None

                                if next_date:
                                    options['from'] = next_date

                                elif not options.get('from'):
                                    # or fetch the complete current month else use the from date
                                    options['from'] = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC())
                            else:
                                # get last datetime from OHLCs DB, and always overwrite it because if it was not closed
                                last_ohlc = Database.inst().get_last_ohlc(options['broker'], market_id, timeframe)

                                if last_ohlc:
                                    # if cascaded is defined, then we need more past data to have a full range
                                    # (until 7x1d for the week, until 4x1h for the 4h...)
                                    if cascaded:
                                        last_timestamp = Instrument.basetime(cascaded, last_ohlc.timestamp)
                                    else:
                                        last_timestamp = last_ohlc.timestamp

                                    last_date = datetime.fromtimestamp(last_timestamp, tz=UTC())
                                    options['from'] = last_date

                                elif not options.get('from'):
                                    # or fetch the complete current month else use the from date
                                    options['from'] = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC())

                        fetcher.fetch_and_generate(market_id, timeframe,
                            options.get('from'), options.get('to'), options.get('last'),
                            options.get('spec'), cascaded)

        except KeyboardInterrupt:
            pass
        finally:
            fetcher.disconnect()

    fetcher = None

    terminate(0)
