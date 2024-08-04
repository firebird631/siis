# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Fetcher tool

import sys
import time

from datetime import datetime
from typing import List

from common.utils import UTC, TIMEFRAME_FROM_STR_MAP
from watcher.event import BaseEvent

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

#         if options.get('target-market') and not options.get('target-broker'):
#             error_logger.error("Missing --target-broker name")
#             return False

#         if options.get('target-broker') and not options.get('target-market'):
#             error_logger.error("Missing --target-market identifier(s)")
#             return False

#         if options.get('target-market') and ('!' in options['market'] or '*' in options['market']):
#             error_logger.error("Target market are defined but market list contains special char that are not "
#                                "compatible. It needs an ordered one per one mapping.")
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
#         self._watcher_service = WatcherService(None, options)

#         markets = options['market'].replace(' ', '').split(',')

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


def fetch_events(fetcher, events: List[str], from_date, to_date):
    if "economic" in events:
        countries = []
        currencies = []
        importance = []

        filters = []

        for event in events:
            if event.startswith("country:"):
                countries.append(event.split(':')[1])
            elif event.startswith("currency:"):
                currencies.append(event.split(':')[1])
            elif event.startswith("importance:"):
                importance.append(event.split(':')[1])

        if countries:
            filters.append(('country', countries))
        if currencies:
            filters.append(('currency', currencies))
        if importance:
            filters.append(('importance', importance))

        Terminal.inst().info("Fetch for economic events...")
        fetcher.fetch_events(BaseEvent.EVENT_TYPE_ECONOMIC, from_date, to_date, filters)


def do_fetcher(options):
    Terminal.inst().info("Starting SIIS fetcher using %s identity..." % options['identity'])
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    # want speedup the database inserts
    Database.inst().enable_fetch_mode()

    watcher_service = WatcherService(None, options)
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

    if options.get('target-market') and ('!' in options['market'] or '*' in options['market']):
        error_logger.error("Target market are defined but market list contains special char that are not "
                           "compatible. It needs an ordered one per one mapping.")
        sys.exit(-1)

    if options.get('target-market') and options['market'].count(',') != options['target-market'].count(','):
        error_logger.error("Target market must defines a one per one market identifier. "
                           "Please recheck --market and --target-market parameters.")
        sys.exit(-1)

    if timeframe < 0:
        error_logger.error("Invalid timeframe")
        sys.exit(-1)

    do_update = False
    install_market = options.get('install-market', False)

    if options.get('update'):
        # if options.get('from'):
        #     error_logger.error("Either --from or --update parameters must be defined")
        #     terminate(-1)
        # else:
        do_update = True

    if options.get('delay'):
        delay = float(options['delay'])
    else:
        delay = 0.0

    try:
        fetcher.connect()
    except:
        terminate(-1)

    today = datetime.now().astimezone(UTC())

    if fetcher.connected:
        logger.info("Fetcher authenticated to %s, trying to collect data..." % fetcher.name)

        markets = options['market'].replace(' ', '').split(',') if options.get('market') else []
        target_markets = {}

        if options.get('target-market'):
            # map targets and source because set destroy original order
            targets = options.get('target-market', "").replace(' ', '').split(',')

            for i, market in enumerate(markets):
                target_markets[market] = targets[i]

        broker_id = options['broker']
        target_broker_id = options.get('target-broker')

        # filters only available instruments ('*' and '!' are not compatible with target mapping)
        markets = fetcher.matching_symbols_set(markets, fetcher.available_instruments())

        try:
            if not markets and 'event' in options.get('spec').split(','):
                from_date = options.get('from')
                to_date = options.get('to')
                spec = options.get('spec')

                events = [x for x in spec.split(',') if x != "event"]
                fetch_events(fetcher, events, from_date, to_date)

            for market_id in markets:
                # map if defined
                target_market_id = target_markets.get(market_id)

                if not fetcher.has_instrument(market_id, options.get('spec')):
                    logger.error("Market %s not found !" % market_id)

                # install market or fetch history
                if install_market:
                    fetcher.install_market(market_id)
                else:
                    # reset from initials options
                    from_date = options.get('from')
                    to_date = options.get('to')
                    last = options.get('last')
                    spec = options.get('spec')

                    Terminal.inst().info("Init for %s..." % (market_id,))

                    if do_update:
                        # update from last entry, compute the from datetime
                        if timeframe <= Instrument.TF_TICK:
                            # get last datetime from tick storage and add 1 millisecond
                            if target_broker_id and target_market_id:
                                last_tick = Database.inst().get_last_tick(target_broker_id, target_market_id)
                            else:
                                last_tick = Database.inst().get_last_tick(broker_id, market_id)

                            next_date = datetime.fromtimestamp(last_tick[0] + 0.001, tz=UTC()) if last_tick else None

                            if next_date:
                                from_date = next_date

                            if not from_date:
                                # or fetch the complete current month else use the from date
                                from_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0,
                                                          tzinfo=UTC())
                        else:
                            # get last datetime from OHLCs DB, and always overwrite it because if it was not closed
                            if target_broker_id and target_market_id:
                                last_ohlc = Database.inst().get_last_ohlc(
                                    target_broker_id, target_market_id, timeframe)
                            else:
                                last_ohlc = Database.inst().get_last_ohlc(broker_id, market_id, timeframe)

                            if last_ohlc:
                                # if cascaded is defined, then we need more past data to have a full range
                                # (until 7x1d for the week, until 4x1h for the 4h...)
                                if cascaded:
                                    last_timestamp = Instrument.basetime(cascaded, last_ohlc.timestamp)
                                else:
                                    last_timestamp = last_ohlc.timestamp

                                last_date = datetime.fromtimestamp(last_timestamp, tz=UTC())

                                from_date = last_date

                            if not from_date:
                                # or fetch the complete current month else use the from date
                                from_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0,
                                                          tzinfo=UTC())

                    if target_broker_id and target_market_id:
                        Terminal.inst().info("Update %s from %s to destination %s %s..." % (
                            market_id, from_date, target_broker_id, target_market_id))
                    else:
                        Terminal.inst().info("Update %s from %s..." % (market_id, from_date))

                    fetcher.fetch_and_generate(market_id, timeframe, from_date, to_date, last, spec, cascaded,
                                               target_broker_id=target_broker_id,
                                               target_market_id=target_market_id)

                if delay > 0:
                    time.sleep(delay)

        except Exception as e:
            logger.error(repr(e))
        except KeyboardInterrupt:
            pass
        finally:
            fetcher.disconnect()

    fetcher = None

    terminate(0)
