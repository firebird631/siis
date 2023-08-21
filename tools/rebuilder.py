# @date 2019-09-18
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2017 Dream Overflow
# Ohlc rebuilder from ticks/trades data tool

import sys
import time

from datetime import datetime, timedelta

from common.utils import UTC, TIMEFRAME_FROM_STR_MAP, timeframe_to_str, format_datetime

from terminal.terminal import Terminal
from database.database import Database

from instrument.instrument import Instrument, Candle
from instrument.candlegenerator import CandleGenerator

import logging
logger = logging.getLogger('siis.tools.rebuilder')
error_logger = logging.getLogger('siis.error.tools.rebuilder')


# candles from 1m to 1 week
# GENERATED_TF = [60, 60*3, 60*5, 60*15, 60*30, 60*60, 60*60*2, 60*60*4, 60*60*24, 60*60*24*7]
GENERATED_TF = [60, 60*5, 60*15, 60*30, 60*60, 60*60*2, 60*60*4, 60*60*24, 60*60*24*7]

TICK_STORAGE_DELAY = 0.05  # 50ms
MAX_PENDING_TICK = 10000


# class Rebuilder(Tool):
#     """
#     For generated timeframe it tries to reload the current OHLC for each timeframe generator if exists.
#     """

#     @classmethod
#     def alias(cls):
#         return "rebuild"

#     @classmethod
#     def help(cls):
#         return ("Process the data OHLC and tick/trade/quote rebuild from a timeframe to a multiple target timeframe.",
#                 "Specify --broker, --market, --from or --update, --timeframe, --timeframe, and --target or --cascaded.",
#                 "Optional --to date. Until datetime or now if not specified.",)
#                 "--from or --update are mutually exclusive. If --update is defined it will update from last datetime found from source timeframe.",)

#     @classmethod
#     def detailed_help(cls):
#         return tuple()

#     @classmethod
#     def need_identity(cls):
#         return True

#     def __init__(self, options):
#         super().__init__("rebuilder", options)

#         self._watcher_service = None

#     def check_options(self, options):
#         if not options.get('market') or not options.get('broker'):
#             error_logger.error("--market and --broker parameters must be defined")
#             return False

#         if not options.get('from') and not options.get('update'):
#             error_logger.error("Either --from or --update parameters must be defined")
#             return False

#         if options.get('from') and options.get('update'):            
#             error_logger.error("Exclusive --from or --update parameter")
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
#         markets = options['market'].replace(' ', '').split(',')

#         return True

#     def terminate(self, options):
#         Terminal.inst().info("Flushing database...")
#         Database.terminate()

#         return True

#     def forced_interrupt(self, options):
#         return True


# tool = Rebuilder


def store_ohlc(broker_name, market_id, timeframe, ohlc):
    Database.inst().store_market_ohlc((
        broker_name, market_id, int(ohlc.timestamp*1000.0), int(timeframe),
        str(ohlc.open), str(ohlc.high), str(ohlc.low), str(ohlc.close),
        str(ohlc.spread),
        str(ohlc.volume)))


def do_rebuilder(options):
    Terminal.inst().info("Starting SIIS rebuilder using %s identity..." % options['identity'])
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    # want speedup the database inserts
    Database.inst().enable_fetch_mode()

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
        error_logger.error("Invalid timeframe")
        sys.exit(-1)

    from_date = options.get('from')
    to_date = options.get('to')
    do_update = options.get('update', False)

    broker_id = options['broker']

    if not options.get('market') or not options.get('broker'):
        error_logger.error("--market and --broker parameters must be defined")
        sys.exit(-1)

    if not options.get('from') and not options.get('update'):
        error_logger.error("Either --from or --update parameters must be defined")
        sys.exit(-1)

    if options.get('from') and options.get('update'):
        error_logger.error("Exclusive --from or --update parameter")
        sys.exit(-1)

    if not to_date:
        today = datetime.now().astimezone(UTC())

        if timeframe == Instrument.TF_MONTH:
            to_date = today + timedelta(days=30)
        else:
            to_date = today + timedelta(seconds=timeframe)

        to_date = to_date.replace(microsecond=0)

    if timeframe > 0 and timeframe not in GENERATED_TF:
        error_logger.error("Timeframe %s is not allowed !" % timeframe_to_str(timeframe))
        sys.exit(-1)

    if '!' in options['market'] or '*' in options['market']:
        error_logger.error("Target market are defined but market list contains special char that are not "
                           "compatible. It needs an ordered one per one mapping.")
        sys.exit(-1)

    markets = options['market'].replace(' ', '').split(',')

    for market in markets:
        # need a from datetime and timestamp else compute from last value
        if not from_date and do_update:
            if timeframe == Instrument.TF_TICK:
                # begin from last source tick/trade timestamp
                last_tick = Database.inst().get_last_tick(broker_id, market)
                if last_tick:
                    from_date = datetime.utcfromtimestamp(last_tick[0]).replace(tzinfo=UTC())
            else:
                # begin from last source OHLC timestamp
                last_ohlc = Database.inst().get_last_ohlc(broker_id, market, timeframe)
                if last_ohlc:
                    from_date = datetime.utcfromtimestamp(last_ohlc.timestamp).replace(tzinfo=UTC())

        Terminal.inst().info("Rebuild from %s..." % from_date.strftime("%Y-%m-%dT%H:%M:%SZ"))

        timestamp = from_date.timestamp()
        to_timestamp = to_date.timestamp()

        progression = 0.0
        prev_update = timestamp
        iterate = 0
        count = 0
        total_count = 0

        progression_incr = (to_timestamp - timestamp) * 0.01

        tts = 0.0
        prev_tts = 0.0

        generators = []
        from_tf = timeframe

        last_ticks = []
        last_ohlcs = {}

        # need a source data streamer, either ticks or OHLCs
        if timeframe == Instrument.TF_TICK:
            ohlc_streamer = None
            tick_streamer = Database.inst().create_tick_streamer(broker_id, market,
                                                                 from_date=from_date, to_date=to_date)
        else:
            tick_streamer = None
            ohlc_streamer = Database.inst().create_ohlc_streamer(broker_id, market, timeframe,
                                                                 from_date=from_date, to_date=to_date)

        def load_ohlc(_timestamp: float, _timeframe: float) -> Candle:
            # inner function to retrieve to the last OHLC for each generator
            return Database.inst().get_last_ohlc_at(broker_id, market, _timeframe,
                                                    Instrument.basetime(_timeframe, _timestamp))

        # cascaded generation of candles
        if cascaded:
            for tf in GENERATED_TF:
                if tf > timeframe:
                    # from timeframe greater than initial
                    if tf <= cascaded:
                        # until max cascaded timeframe
                        generator = CandleGenerator(from_tf, tf)
                        generators.append(generator)
                        from_tf = tf

                        # load OHLC at the base timestamp (if exists)
                        generator.current = load_ohlc(timestamp, tf)
                        # Terminal.inst().debug(generator.current)

                        # store for generation
                        last_ohlcs[tf] = []
                else:
                    from_tf = tf

        if options.get('target'):
            target = TIMEFRAME_FROM_STR_MAP.get(options.get('target'))

            if timeframe > 0 and target % timeframe != 0:
                logger.error("Timeframe %s is not a multiple of %s !" % (
                    timeframe_to_str(target), timeframe_to_str(timeframe)))
                sys.exit(-1)

            generator = CandleGenerator(timeframe, target)
            generators.append(generator)

            # load OHLC at the base timestamp (if exists)
            generator.current = load_ohlc(timestamp, target)
            # Terminal.inst().debug(generator.current)

            # store for generation
            last_ohlcs[target] = []

        if timeframe > 0:
            last_ohlcs[timeframe] = []

        if timeframe == 0:
            while not tick_streamer.finished():
                ticks = tick_streamer.next(timestamp + Instrument.TF_1M)

                iterate += 1
                count += len(ticks)
                total_count += len(ticks)

                for data in ticks:
                    if data[0] > to_timestamp:
                        break

                    if generators:
                        last_ticks.append(data)

                # generate higher candles
                for generator in generators:
                    if generator.from_tf == 0:
                        candles = generator.generate_from_ticks(last_ticks)

                        if candles:
                            for c in candles:
                                store_ohlc(broker_id, market, generator.to_tf, c)

                            last_ohlcs[generator.to_tf] += candles

                        # remove consumed ticks
                        last_ticks = []
                    else:
                        candles = generator.generate_from_candles(last_ohlcs[generator.from_tf])

                        if candles:
                            for c in candles:
                                store_ohlc(broker_id, market, generator.to_tf, c)

                            last_ohlcs[generator.to_tf] += candles

                        # remove consumed candles
                        last_ohlcs[generator.from_tf] = []

                if timestamp - prev_update >= progression_incr:
                    progression += 1

                    Terminal.inst().info("%i%% on %s, %s ticks/trades for last %s minutes, current total of %s..." % (
                        progression, format_datetime(timestamp), count, iterate, total_count))

                    prev_update = timestamp
                    count = 0
                    iterate = 0

                if timestamp > to_timestamp:
                    break

                timestamp += Instrument.TF_1M  # by step of 1m

                # calm down the storage of tick, if parsing is faster
                while Database.inst().num_pending_ticks_storage() > TICK_STORAGE_DELAY:
                    time.sleep(TICK_STORAGE_DELAY)  # wait a little before continue

            if progression < 100:
                Terminal.inst().info("100%% on %s, %s ticks/trades for last %s minutes, current total of %s..." % (
                    format_datetime(timestamp), count, iterate, total_count))

        elif timeframe > 0:
            while not ohlc_streamer.finished():
                ohlcs = ohlc_streamer.next(timestamp + timeframe * 100)  # per 100

                iterate += 1
                count += len(ohlcs)
                total_count += len(ohlcs)

                for data in ohlcs:
                    if data.timestamp > to_timestamp:
                        break

                    if generators:
                        last_ohlcs[timeframe].append(data)

                    tts = data.timestamp

                    if not prev_tts:
                        prev_tts = tts

                    prev_tts = tts
                    timestamp = tts

                # generate higher candles
                for generator in generators:
                    candles = generator.generate_from_candles(last_ohlcs[generator.from_tf])
                    if candles:
                        for c in candles:
                            store_ohlc(options['broker'], market, generator.to_tf, c)

                        last_ohlcs[generator.to_tf].extend(candles)

                    # remove consumed candles
                    last_ohlcs[generator.from_tf] = []

                if timestamp - prev_update >= progression_incr:
                    progression += 1

                    Terminal.inst().info("%i%% on %s, %s OHLCs for last bulk of %s OHLCs, current total of %s..." % (
                        progression, format_datetime(timestamp), count, iterate*100, total_count))

                    prev_update = timestamp
                    count = 0
                    iterate = 0

                if timestamp > to_timestamp:
                    break

                if count == 0:
                    timestamp += timeframe * 100

            if progression < 100:
                Terminal.inst().info("100%% on %s,  %s OHLCs for last bulk of %s OHLCs, current total of %s..." % (
                    format_datetime(timestamp), count, iterate*100, total_count))

    Terminal.inst().info("Flushing database...")
    Terminal.inst().flush() 

    Database.terminate()

    Terminal.inst().info("Rebuild done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
