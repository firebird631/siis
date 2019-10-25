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

from instrument.instrument import Tick, Candle, Instrument
from instrument.candlegenerator import CandleGenerator

import logging
logger = logging.getLogger('siis.tools.rebuilder')


# candles from 1m to 1 week
# GENERATED_TF = [60, 60*3, 60*5, 60*15, 60*30, 60*60, 60*60*2, 60*60*4, 60*60*24, 60*60*24*7]
GENERATED_TF = [60, 60*5, 60*15, 60*30, 60*60, 60*60*2, 60*60*4, 60*60*24, 60*60*24*7]

TICK_STORAGE_DELAY = 0.05  # 50ms
MAX_PENDING_TICK = 10000


def format_datetime(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S UTC')


def store_ohlc(broker_name, market_id, timeframe, ohlc):
    Database.inst().store_market_ohlc((
        broker_name, market_id, int(ohlc.timestamp*1000.0), int(timeframe),
        str(ohlc.bid_open), str(ohlc.bid_high), str(ohlc.bid_low), str(ohlc.bid_close),
        str(ohlc.ofr_open), str(ohlc.ofr_high), str(ohlc.ofr_low), str(ohlc.ofr_close),
        str(ohlc.volume)))


def do_rebuilder(options):
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
        logger.error("Invalid timeframe")
        sys.exit(-1)

    from_date = options.get('from')
    to_date = options.get('to')

    if not to_date:
        today = datetime.now().astimezone(UTC())

        if timeframe == Instrument.TF_MONTH:
            to_date = today + timedelta(months=1)
        else:
            to_date = today + timedelta(seconds=timeframe)

        to_date = to_date.replace(microsecond=0)

    if timeframe > 0 and timeframe not in GENERATED_TF:
        logger.error("Timeframe %i is not allowed !" % (timeframe,))
        return

    for market in options['market'].split(','):
        if market.startswith('!') or market.startswith('*'):
            continue

        timestamp = from_date.timestamp()
        to_timestamp = to_date.timestamp()

        progression = 0.0
        prev_update = timestamp
        count = 0
        total_count = 0

        progression_incr = (to_timestamp - timestamp) * 0.01

        tts = 0.0
        prev_tts = 0.0

        generators = []
        from_tf = timeframe

        last_ticks = []
        last_ohlcs = {}

        if timeframe == Instrument.TF_TICK:
            tick_streamer = Database.inst().create_tick_streamer(options['broker'], market, from_date=from_date, to_date=to_date)
        else:
            ohlc_streamer = Database.inst().create_ohlc_streamer(options['broker'], market, timeframe, from_date=from_date, to_date=to_date)
    
        # cascaded generation of candles
        if cascaded:
            for tf in GENERATED_TF:
                if tf > timeframe:
                    # from timeframe greater than initial
                    if tf <= cascaded:
                        # until max cascaded timeframe
                        generators.append(CandleGenerator(from_tf, tf))
                        from_tf = tf

                        # store for generation
                        last_ohlcs[tf] = []
                else:
                    from_tf = tf

        if timeframe > 0:
            last_ohlcs[timeframe] = []

        if timeframe == 0:
            while not tick_streamer.finished():
                ticks = tick_streamer.next(timestamp + Instrument.TF_1M)

                count = len(ticks)
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
                                store_ohlc(options['broker'], market, generator.to_tf, c)

                            last_ohlcs[generator.to_tf] += candles

                        # remove consumed ticks
                        last_ticks = []
                    else:
                        candles = generator.generate_from_candles(last_ohlcs[generator.from_tf])

                        if candles:
                            for c in candles:
                                store_ohlc(options['broker'], market, generator.to_tf, c)

                            last_ohlcs[generator.to_tf] += candles

                        # remove consumed candles
                        last_ohlcs[generator.from_tf] = []

                if timestamp - prev_update >= progression_incr:
                    progression += 1

                    Terminal.inst().info("%i%% on %s, %s ticks/trades for 1 minute, current total of %s..." % (progression, format_datetime(timestamp), count, total_count))

                    prev_update = timestamp
                    count = 0

                if timestamp > to_timestamp:
                    break

                timestamp += Instrument.TF_1M  # by step of 1m

                # calm down the storage of tick, if parsing is faster
                while Database.inst().num_pending_ticks_storage() > TICK_STORAGE_DELAY:
                   time.sleep(TICK_STORAGE_DELAY)  # wait a little before continue

        elif timeframe > 0:
            while not ohlc_streamer.finished():
                ohlcs = ohlc_streamer.next(timestamp + timeframe * 100)  # per 100

                count = len(ohlcs)
                total_count += len(ohlcs)

                for data in ohlcs:
                    if data.timestamp > to_timestamp:
                        break

                    if generators:
                        last_ohlcs[timeframe].append(candle)

                # generate higher candles
                for generator in generators:
                    candles = generator.generate_from_candles(last_ohlcs[generator.from_tf])
                    if candles:
                        for c in candles:
                            store_ohlc(options['broker'], market, generator.to_tf, c)

                        last_ohlcs[generator.to_tf].extend(candles)

                    # remove consumed candles
                    last_ohlcs[generator.from_tf] = []

                prev_tts = tts
                timestamp = tts

                if timestamp - prev_update >= progression_incr:
                    progression += 1

                    Terminal.inst().info("%i%% on %s, %s ticks/trades for 1 minute, current total of %s..." % (progression, format_datetime(timestamp), count, total_count))

                    prev_update = timestamp
                    count = 0

                if timestamp > to_timestamp:
                    break

                if total_count == 0:
                    timestamp += timeframe * 100

    Terminal.inst().info("Flushing database...")
    Terminal.inst().flush() 

    Database.terminate()

    Terminal.inst().info("Rebuild done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
