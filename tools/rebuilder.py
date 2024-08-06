# @date 2019-09-18
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2017 Dream Overflow
# Ohlc rebuilder from ticks/trades data tool

import sys
import time

from datetime import datetime, timedelta
from typing import List, Optional

from common.utils import UTC, TIMEFRAME_FROM_STR_MAP, timeframe_to_str, format_datetime
from instrument.bar import BarBase
from instrument.bargeneratorbase import BarGeneratorBase
from instrument.rangebargenerator import RangeBarGenerator

from terminal.terminal import Terminal
from database.database import Database

from instrument.instrument import Instrument, Candle
from instrument.timeframebargenerator import TimeframeBarGenerator

import logging
logger = logging.getLogger('siis.tools.rebuilder')
error_logger = logging.getLogger('siis.error.tools.rebuilder')


# candles from 1m to 1 week
GENERATED_TF = [60, 60*5, 60*15, 60*30, 60*60, 60*60*2, 60*60*4, 60*60*24, 60*60*24*7]

BAR_STORAGE_DELAY = 0.05  # 50ms
MAX_PENDING_BARS = 10000

# @todo volume profile generation


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


def store_range_bar(broker_name, market_id, bar_size, bar):
    Database.inst().store_market_range_bar((
        broker_name, market_id, int(bar.timestamp * 1000.0), int(bar.duration * 1000.0), int(bar_size),
        str(bar.open), str(bar.high), str(bar.low), str(bar.close),
        str(bar.volume)))


def do_rebuilder(options):
    Terminal.inst().info("Starting SIIS rebuilder using %s identity..." % options['identity'])
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    # want speedup the database inserts
    Database.inst().enable_fetch_mode()

    src_timeframe = -1

    if not options.get('timeframe'):
        src_timeframe = 60  # default to 1min
    else:
        if options['timeframe'] in TIMEFRAME_FROM_STR_MAP:
            src_timeframe = TIMEFRAME_FROM_STR_MAP[options['timeframe']]
        else:
            try:
                src_timeframe = int(options['timeframe'])
            except ValueError:
                pass

    if src_timeframe < 0:
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

        if src_timeframe == Instrument.TF_MONTH:
            to_date = today + timedelta(days=30)
        else:
            to_date = today + timedelta(seconds=src_timeframe)

        to_date = to_date.replace(microsecond=0)

    if src_timeframe > 0 and src_timeframe not in GENERATED_TF:
        error_logger.error("Timeframe %s is not allowed !" % timeframe_to_str(src_timeframe))
        sys.exit(-1)

    if '!' in options['market'] or '*' in options['market']:
        error_logger.error("Target market are defined but market list contains special char that are not "
                           "compatible. It needs an ordered one per one mapping.")
        sys.exit(-1)

    markets = options['market'].replace(' ', '').split(',')

    #
    # optional options
    #

    try:
        tick_scale = float(options.get('tick-scale', 1.0))
    except ValueError:
        error_logger.error("Tick-scale must be a decimal number !")
        sys.exit(-1)

    #
    # parse target and cascaded parameters
    #

    if not options.get('cascaded'):
        cascaded_bar = None
        cascaded_type = None
    else:
        cascaded_bar = None
        cascaded_type = None

        if options['cascaded'] in TIMEFRAME_FROM_STR_MAP:
            cascaded_bar = TIMEFRAME_FROM_STR_MAP[options['cascaded']]
            cascaded_type = "timeframe"
        elif options['cascaded'].endswith('rb'):
            try:
                cascaded_bar = int(options['cascaded'][0:-2])
                cascaded_type = "range-bar"
            except ValueError:
                pass
        elif options['cascaded'].endswith('rvb'):
            try:
                cascaded_bar = int(options['cascaded'][0:-3])
                cascaded_type = "reversal-bar"
            except ValueError:
                pass
        elif options['cascaded'].endswith('tb'):
            try:
                cascaded_bar = int(options['cascaded'][0:-2])
                cascaded_type = "tick-bar"
            except ValueError:
                pass
        elif options['cascaded'].endswith('vb'):
            try:
                cascaded_bar = int(options['cascaded'][0:-2])
                cascaded_type = "volume-bar"
            except ValueError:
                pass

        if not cascaded_type:
            error_logger.error("Cascaded %s is not allowed !" % options.get('cascaded'))
            sys.exit(-1)

    if not options.get('target'):
        target_bar = None
        target_type = None
    else:
        # target timeframe or bar
        target_bar = None
        target_type = None
        
        if options['target'] in TIMEFRAME_FROM_STR_MAP:
            target_bar = TIMEFRAME_FROM_STR_MAP.get(options['target'])
            target_type = "timeframe"
        elif options['target'].endswith('rb'):
            try:
                target_bar = int(options['target'][0:-2])
                target_type = "range-bar"
            except ValueError:
                pass
        elif options['target'].endswith('rvb'):
            try:
                target_bar = int(options['target'][0:-3])
                target_type = "reversal-bar"
            except ValueError:
                pass
        elif options['target'].endswith('tb'):
            try:
                target_bar = int(options['target'][0:-2])
                target_type = "tick-bar"
            except ValueError:
                pass
        elif options['target'].endswith('vb'):
            try:
                target_bar = int(options['target'][0:-2])
                target_type = "volume-bar"
            except ValueError:
                pass

        if not target_type:
            error_logger.error("Target %s is not allowed !" % options.get('target'))
            sys.exit(-1)

    if src_timeframe > 0 and ((cascaded_bar and cascaded_type != "timeframe") or
                              (target_bar and target_type != "timeframe")):
        error_logger.error(
            "Incompatibility with source timeframe (OHLC bar) and target %s !" % (cascaded_type or target_type))
        sys.exit(-1)

    if cascaded_bar and cascaded_type != "timeframe":
        error_logger.error("Cascaded mode is only compatible with timeframe bars !")
        sys.exit(-1)

    #
    # processing for each market, one at time
    #

    for market in markets:
        # need a from datetime and timestamp else compute from last value of the greatest target
        if do_update:
            if cascaded_bar:
                # higher timeframe
                test_bar = cascaded_bar
                test_bar_type = cascaded_type
            else:
                test_bar = target_bar
                test_bar_type = target_type

            if test_bar_type == "timeframe":
                last_ohlc = Database.inst().get_last_ohlc(broker_id, market, test_bar)
            elif test_bar_type == "range-bar":
                last_ohlc = Database.inst().get_last_range_bar(broker_id, market, test_bar)
            else:
                last_ohlc = None

            if last_ohlc:
                from_date = datetime.utcfromtimestamp(last_ohlc.timestamp).replace(tzinfo=UTC())
                # Terminal.inst().debug(last_ohlc.volume)

        if not from_date:
            error_logger.error("Unable to find a previous bar for %s !" % market)
            continue

        Terminal.inst().info("Rebuild for %s from %s..." % (market, from_date.strftime("%Y-%m-%dT%H:%M:%SZ")))

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

        timeframe_generators: List[TimeframeBarGenerator] = []   # one or multiple timeframe generators
        bar_generator: Optional[BarGeneratorBase] = None  # or a single non-temporal generator (BarBaseGenerator)
        from_tf = src_timeframe

        last_ticks = []
        last_bars = {}

        # need a source data streamer, either ticks or OHLCs
        if src_timeframe == Instrument.TF_TICK:
            ohlc_streamer = None
            tick_streamer = Database.inst().create_tick_streamer(broker_id, market,
                                                                 from_date=from_date, to_date=to_date)
        else:
            tick_streamer = None
            ohlc_streamer = Database.inst().create_ohlc_streamer(broker_id, market, src_timeframe,
                                                                 from_date=from_date, to_date=to_date)

        def load_ohlc(_timestamp: float, _timeframe: float) -> Candle:
            # inner function to retrieve to the last OHLC for each generator
            return Database.inst().get_last_ohlc_at(broker_id, market, _timeframe,
                                                    Instrument.basetime(_timeframe, _timestamp))

        def store_bar(bar_type: str, last_bar: BarBase):
            if bar_type == "range-bar":
                store_range_bar(broker_id, market, bar_generator.size, last_bar)

        def finalize_timeframe_generators():
            # need to complete with the current OHLC and store them
            for _generator in timeframe_generators:
                if _generator.from_tf > 0:
                    # retrieve the 'from' generator and update from its current candle
                    for gen in timeframe_generators:
                        if gen.to_tf == _generator.from_tf:
                            _candles = _generator.generate_from_candles([gen.current], False)
                            if _candles:
                                for _c in _candles:
                                    store_ohlc(broker_id, market, _generator.to_tf, _c)
                            break

                if _generator.current:
                    # and store current candle
                    store_ohlc(broker_id, market, _generator.to_tf, _generator.current)

        def finalize_bar_generator():
            # need to complete with the current OHLC and store them
            if bar_generator:
                if bar_generator.current:
                    store_bar(target_type, bar_generator.current)

        # cascaded generation of candles
        if cascaded_bar:
            for tf in GENERATED_TF:
                if tf > src_timeframe:
                    # from timeframe greater than initial
                    if tf <= cascaded_bar:
                        # until max cascaded timeframe
                        generator = TimeframeBarGenerator(from_tf, tf)
                        timeframe_generators.append(generator)
                        from_tf = tf

                        # load OHLC at the base timestamp (if exists)
                        # not loaded but preferred to regenerate because else volume are accumulated again
                        # else it will need to know the exact last timestamp of used base timeframe,
                        # and it is not possible to find this information otherwise than to store it somewhere
                        # generator.current = load_ohlc(timestamp, tf)
                        # Terminal.inst().debug(generator.current)

                        # store for generation
                        last_bars[tf] = []
                else:
                    from_tf = tf

        if target_bar:
            if target_type == "timeframe":
                if src_timeframe > 0 and target_bar % src_timeframe != 0:
                    logger.error("Timeframe %s is not a multiple of %s !" % (
                        timeframe_to_str(target_bar), timeframe_to_str(src_timeframe)))
                    sys.exit(-1)

                generator = TimeframeBarGenerator(src_timeframe, target_bar)
                timeframe_generators.append(generator)

                # load OHLC at the base timestamp (if exists) or rebuild for its base timestamp (more simple case)
                # @see line 297 for reason of comment
                # generator.current = load_ohlc(timestamp, target)
                # Terminal.inst().debug(generator.current)

                # store for generating
                last_bars[target_bar] = []

            elif target_type == "range-bar":
                # single range-bar at time
                bar_generator = RangeBarGenerator(target_bar, tick_scale)

                # store for generating
                last_bars[target_bar] = []

        if src_timeframe > 0:
            last_bars[src_timeframe] = []

        #
        # generate from a source of ticks/trades
        #

        if src_timeframe == 0:
            while not tick_streamer.finished():
                ticks = tick_streamer.next(timestamp + Instrument.TF_1M)

                iterate += 1
                count += len(ticks)
                total_count += len(ticks)

                for data in ticks:
                    if data[0] > to_timestamp:
                        break

                    if timeframe_generators or bar_generator:
                        last_ticks.append(data)

                if bar_generator:
                    # generate non-temporal bar series
                    new_bars = bar_generator.generate_from_ticks(last_ticks)
                    if new_bars:
                        for new_bar in new_bars:
                            store_bar(target_type, new_bar)

                        # not necessary to keep in memory the new bar

                    # remove consumed ticks
                    last_ticks = []

                elif timeframe_generators:
                    # generate higher candles
                    for generator in timeframe_generators:
                        if generator.from_tf == 0:
                            new_bars = generator.generate_from_ticks(last_ticks)
                            if new_bars:
                                for bar in new_bars:
                                    store_ohlc(broker_id, market, generator.to_tf, bar)

                                last_bars[generator.to_tf] += new_bars

                            # remove consumed ticks
                            last_ticks = []
                        else:
                            new_bars = generator.generate_from_candles(last_bars[generator.from_tf])
                            if new_bars:
                                for bar in new_bars:
                                    store_ohlc(broker_id, market, generator.to_tf, bar)

                                last_bars[generator.to_tf] += new_bars

                            # remove consumed candles
                            last_bars[generator.from_tf] = []

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

                # calm down the storage of OHLCs/bars, if generation is faster
                while Database.inst().num_pending_bars_storage() > MAX_PENDING_BARS:
                    time.sleep(BAR_STORAGE_DELAY)

            # complete the lasts non-ended bars
            if bar_generator:
                finalize_bar_generator()
            elif timeframe_generators:
                finalize_timeframe_generators()

            if progression < 100:
                Terminal.inst().info("100%% on %s, %s ticks/trades for last %s minutes, current total of %s..." % (
                    format_datetime(timestamp), count, iterate, total_count))

        #
        # generate from a source of timeframe bars
        # this mode only works with a target/cascaded of timeframes only
        #

        elif src_timeframe > 0:
            while not ohlc_streamer.finished():
                new_bars = ohlc_streamer.next(timestamp + src_timeframe * 100)  # per 100

                iterate += 1
                count += len(new_bars)
                total_count += len(new_bars)

                for data in new_bars:
                    if data.timestamp > to_timestamp:
                        break

                    if timeframe_generators:
                        last_bars[src_timeframe].append(data)

                    tts = data.timestamp

                    if not prev_tts:
                        prev_tts = tts

                    prev_tts = tts
                    timestamp = tts

                # generate higher candles
                for generator in timeframe_generators:
                    new_bars = generator.generate_from_candles(last_bars[generator.from_tf])
                    if new_bars:
                        for bar in new_bars:
                            store_ohlc(options['broker'], market, generator.to_tf, bar)

                        last_bars[generator.to_tf].extend(new_bars)

                    # remove consumed candles
                    last_bars[generator.from_tf] = []

                if timestamp - prev_update >= progression_incr:
                    progression += 1

                    Terminal.inst().info("%i%% on %s, %s OHLCs for last bulk of %s OHLCs, current total of %s..." % (
                        progression, format_datetime(timestamp), count, iterate*100, total_count))

                    prev_update = timestamp
                    count = 0
                    iterate = 0

                if timestamp > to_timestamp:
                    # last timestamp is over to_date, stop here
                    break

                if len(new_bars) == 0:
                    # no date for this frame, jump to next one
                    timestamp += src_timeframe * 100

                # calm down the storage of OHLCs, if generation is faster
                while Database.inst().num_pending_bars_storage() > MAX_PENDING_BARS:
                    time.sleep(BAR_STORAGE_DELAY)

            # complete the lasts non-ended bars
            finalize_timeframe_generators()

            if progression < 100:
                Terminal.inst().info("100%% on %s,  %s OHLCs for last bulk of %s OHLCs, current total of %s..." % (
                    format_datetime(timestamp), count, iterate*100, total_count))

    #
    # termination
    #

    Terminal.inst().info("Flushing database...")
    Terminal.inst().flush() 

    Database.terminate()

    Terminal.inst().info("Rebuild done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
