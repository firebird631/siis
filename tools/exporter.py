# @date 2019-12-23
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Exporter tool.

import sys
import logging
import traceback
import time

from datetime import datetime, timedelta

from instrument.instrument import Instrument
from common.utils import UTC, TIMEFRAME_FROM_STR_MAP, timeframe_to_str, format_datetime, format_delta

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.exporter')

EXPORT_VERSION = "1.0.0"

# candles from 1m to 1 month
EXPORT_TF = [60, 60*3, 60*5, 60*15, 60*30, 60*60, 60*60*2, 60*60*4, 60*60*24, 60*60*24*7, 60*60*24*30]


def write_ohlc(ohlc, dst):
    pass


def export_ohlcs(broker_id, market_id, timeframe, from_date, to_date, dst):
    last_ohlcs = {}

    ohlc_streamer = Database.inst().create_ohlc_streamer(broker_id, market_id, timeframe, from_date=from_date, to_date=to_date, buffer_size=100)
    timestamp = from_date.timestamp()
    to_timestamp = to_date.timestamp()
    progression = 0.0
    prev_update = timestamp
    count = 0
    total_count = 0

    progression_incr = (to_timestamp - timestamp) * 0.01

    tts = 0.0
    prev_tts = 0.0

    while not ohlc_streamer.finished():
        ohlcs = ohlc_streamer.next(timestamp + timeframe * 100)  # per 100

        count = len(ohlcs)
        total_count += len(ohlcs)

        for ohlc in ohlcs:
            dst.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
                ohlc.timestamp,
                ohlc.bid_open, ohlc.bid_high, ohlc.bid_low, ohlc.bid_close,
                ohlc.ofr_open, ohlc.ofr_high, ohlc.ofr_low, ohlc.ofr_close,
                ohlc.volume))

            tts = ohlc.timestamp

            if not prev_tts:
                prev_tts = tts

            prev_tts = tts
            timestamp = tts

            if timestamp > to_timestamp:
                break

        if timestamp - prev_update >= progression_incr:
            progression += 1

            Terminal.inst().info("%i%% on %s, %s for last 100 candles, current total of %s..." % (progression, format_datetime(timestamp), count, total_count))

            prev_update = timestamp
            count = 0

        if timestamp > to_timestamp:
            break

        if total_count == 0:
            timestamp += timeframe * 100

    if progression < 100:
        Terminal.inst().info("100%% on %s, %s for last 100 candles, current total of %s..." % (format_datetime(timestamp), count, total_count))
    
    Terminal.inst().info("Last candle datetime is %s" % (format_datetime(tts),))


def export_ticks(broker_id, market_id, from_date, to_date, dst):
    last_ticks = []

    tick_streamer = Database.inst().create_tick_streamer(broker_id, market_id, from_date=from_date, to_date=to_date)
    timestamp = from_date.timestamp()
    to_timestamp = to_date.timestamp()
    progression = 0.0
    prev_update = timestamp
    count = 0
    total_count = 0

    progression_incr = (to_timestamp - timestamp) * 0.01

    tts = 0.0
    prev_tts = 0.0

    while not tick_streamer.finished():
        ticks = tick_streamer.next(timestamp + Instrument.TF_1M)

        count = len(ticks)
        total_count += len(ticks)

        for data in ticks:
            dst.write("%s\t%s\t%s\t%s\n" % (data[0], data[1], data[2], data[3]))

            if not prev_tts:
                prev_tts = tts

            prev_tts = tts

            if tts > to_timestamp:
                break

        if timestamp - prev_update >= progression_incr:
            progression += 1

            Terminal.inst().info("%i%% on %s, %s ticks/trades for 1 minute, current total of %s..." % (progression, format_datetime(timestamp), count, total_count))

            prev_update = timestamp
            count = 0

        if timestamp > to_timestamp:
            break

        timestamp += Instrument.TF_1M  # by step of 1m

    if progression < 100:
        Terminal.inst().info("100%% on %s, %s ticks/trades for 1 minute, current total of %s..." % (format_datetime(timestamp), count, total_count))
    
    Terminal.inst().info("Last tick datetime is %s" % (format_datetime(tts),))


def do_exporter(options):
    Terminal.inst().info("Starting SIIS exporter...")
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    broker_id = options['broker']
    market_id = options['market']

    timeframe = None

    from_date = options.get('from')
    to_date = options.get('to')

    filename = options.get('filename')

    if not to_date:
        today = datetime.now().astimezone(UTC())

        if timeframe == Instrument.TF_MONTH:
            to_date = today + timedelta(months=1)
        else:
            to_date = today + timedelta(seconds=timeframe)

        to_date = to_date.replace(microsecond=0)

    if not options.get('timeframe'):
        timeframe = None
    else:
        if options['timeframe'] in TIMEFRAME_FROM_STR_MAP:
            timeframe = TIMEFRAME_FROM_STR_MAP[options['timeframe']]
        else:
            try:
                timeframe = int(options['timeframe'])
            except:
                pass

    try:
        # exporting data...
        if timeframe is None:
            for market in options['market'].split(','):
                if market.startswith('!') or market.startswith('*'):
                    continue

                dst = open("%s-%s-%s.siis" % (filename, broker_id, market), "wt")

                # write file header
                dst.write("SIIS\tversion=%s\tutc=%s\tbroker=%s\tmarket=%s\tfrom=%s\tto=%s\ttimeframe=any\n" % (
                    EXPORT_VERSION, int(time.time()*1000), broker_id, market, from_date, to_date, timeframe))

                for tf in GENERATED_TF:
                    Terminal.inst().info("Exporting %s OHLC %s..." % (market, timeframe_to_str(tf)))

                    export_ohlcs(options['broker'], market, tf, from_date, to_date, dst)

                dst.close()
                dst = None

        elif timeframe == Instrument.TF_TICK:
            for market in options['market'].split(','):
                if market.startswith('!') or market.startswith('*'):
                    continue

                dst = open("%s-%s-%s.siis" % (filename, broker_id, market), "wt")

                # write file header
                dst.write("SIIS\tversion=%s\tutc=%s\tbroker=%s\tmarket=%s\tfrom=%s\tto=%s\ttimeframe=t\n" % (
                    EXPORT_VERSION, int(time.time()*1000), broker_id, market, from_date, to_date))

                Terminal.inst().info("Exporting %s ticks/trades..." % (market,))

                export_ticks(options['broker'], market, from_date, to_date, dst)

                dst.close()
                dst = None

        elif timeframe > 0:
            # particular ohlc
            for market in options['market'].split(','):
                if market.startswith('!') or market.startswith('*'):
                    continue

                dst = open("%s-%s-%s.siis" % (filename, broker_id, market), "wt")

                # write file header
                dst.write("SIIS\tversion=%s\tutc=%s\tbroker=%s\tmarket=%s\tfrom=%s\tto=%s\ttimeframe=%s\n" % (
                    EXPORT_VERSION, int(time.time()*1000), broker_id, market, from_date, to_date, timeframe_to_str(timeframe)))

                Terminal.inst().info("Exporting %s OHLC %s..." % (market, timeframe_to_str(timeframe)))

                export_ohlcs(options['broker'], market, timeframe, from_date, to_date, dst)

                dst.close()
                dst = None

    except KeyboardInterrupt:
        pass
    finally:
        pass

    Database.terminate()

    Terminal.inst().info("Exportation done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
