# @date 2019-12-23
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Importer tool.

import sys
import logging
import traceback
import zipfile

from datetime import datetime, timedelta

from instrument.instrument import Instrument
from common.utils import UTC, TIMEFRAME_FROM_STR_MAP, timeframe_from_str, format_datetime, format_delta

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.importer')
error_logger = logging.getLogger('siis.error.tools.importer')

# format SIIS version 1.0.0 : tick, trade, quote, ohlc
# format MT4 OHLC : tick, ohlc

FORMAT_UNDEFINED = 0
FORMAT_SIIS = 1
FORMAT_MT4 = 2


def import_tick_siis_1_0_0(broker_id, market_id, from_date, to_date, row):
    return 0


def import_trade_siis_1_0_0(broker_id, market_id, from_date, to_date, row):
    return 0


def import_quote_siis_1_0_0(broker_id, market_id, from_date, to_date, row):
    return 0


def import_tick_siis_1_0_0(broker_id, market_id, from_date, to_date, row):
    return 0


def import_ohlc_siis_1_0_0(broker_id, market_id, timeframe, from_date, to_date, row):
    parts = row.split('\t')
    
    dt = datetime.strptime(parts[0], '%Y%m%d %H%M%S').replace(tzinfo=UTC())
    timestamp = int(dt.timestamp() * 1000)

    if from_date and dt < from_date:
        return 0

    if to_date and dt > to_date:
        return 0

    Database.inst().store_market_ohlc((
        broker_id, market_id, timestamp, int(timeframe),
        *parts[1:]))

    return 1


def import_tick_mt4(broker_id, market_id, from_date, to_date, row):
    return 0


def import_ohlc_mt4(broker_id, market_id, timeframe, from_date, to_date, row):
    parts = row.split(',')

    dt = datetime.strptime(parts[0] + ' ' + parts[1], '%Y.%m.%d %H:%M').replace(tzinfo=UTC())
    timestamp = int(dt.timestamp() * 1000)

    if from_date and dt < from_date:
        return 0

    if to_date and dt > to_date:
        return 0

    Database.inst().store_market_ohlc((
        broker_id, market_id, timestamp, int(timeframe),
        parts[2], parts[3], parts[4], parts[5],
        parts[2], parts[3], parts[4], parts[5],
        parts[6]))

    return 1


def unzip_file(filename, tmpdir="/tmp/"):
    target = tmpdir + 'siis_' + filename.split('/')[-1].rstrip(".zip")

    with zipfile.ZipFile(filename, 'r') as zip_ref:
        zip_ref.extractall(target)

    return target


def error_exit(src, msg):
    src.close()
    error_logger.error(msg)

    Database.terminate()
    Terminal.terminate()

    sys.exit(-1)


def do_importer(options):
    Terminal.inst().info("Starting SIIS importer...")
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    filename = options.get('filename')
    detected_format = FORMAT_UNDEFINED

    if filename.endswith(".siis"):
        detected_format = FORMAT_SIIS
    elif filename.endswith(".csv"):
        detected_format = FORMAT_MT4

    timeframe = None

    market_id = ""
    broker_id = ""

    # UTC option dates    
    from_date = options.get('from')
    to_date = options.get('to')

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

    src = open(filename, "rt")

    if detected_format == FORMAT_SIIS:
        # first row gives format details
        header = src.readline()

        if not header.startswith("format=SIIS\t"):
            error_exit(src, "Unsupported file format")

        info = header.split('\t')

        for nfo in info:
            k, v = nfo.split('=')

            if k == "version":
                if v != "1.0.0":
                    error_exit(src, "Unsupported format version")
            elif k == "created":
                pass  # informational only
            elif k == "broker":
                broker_id = v
            elif k == "market":
                market_id = v
            elif k == "from":
                pass  # informational only
            elif k == "to":
                pass  # informational only
            elif k == "timeframe":
                if v != "any":
                    timeframe = timeframe_from_str(v)
                else:
                    timeframe = None

    if detected_format == FORMAT_MT4:
        # need broker, market and timeframe
        broker_id = options.get('broker')
        market_id = options.get('market')

        if not broker_id:
            error_exit(src, "Missing target broker identifier")

        if not market_id or ',' in market_id:
            error_exit(src, "Missing or invalid target market identifier")

        if not timeframe:
            error_exit(src, "Missing target timeframe")

    # limited sub-range
    from_date_str = from_date.strftime("%Y-%m-%dT%H:%M:%SZ") if from_date else None
    to_date_str = to_date.strftime("%Y-%m-%dT%H:%M:%SZ") if to_date else None

    total_count = 0

    try:
        if detected_format == FORMAT_SIIS:
            cur_timeframe = None
            cur_from_date = from_date
            cur_to_date = to_date

            while 1:
                row = src.readline()
                if not row:
                    break

                row = row.rstrip("\n")
                if row.startswith("timeframe="):
                    # specify the timeframe of the next rows
                    k, v = row.split('=')
                    cur_timeframe = timeframe_from_str(v)
                    continue

                if cur_timeframe is None:
                    # need a specified timeframe
                    continue

                if cur_timeframe == Instrument.TF_TICK:
                    total_count += import_tick_siis_1_0_0(broker_id, market_id, cur_from_date, cur_to_date, row)

                elif cur_timeframe > 0:
                    total_count += import_ohlc_siis_1_0_0(broker_id, market_id, cur_timeframe, cur_from_date, cur_to_date, row)

        elif detected_format == FORMAT_MT4:
            cur_timeframe = timeframe
            cur_from_date = from_date
            cur_to_date = to_date

            if cur_timeframe == Instrument.TF_TICK:
                while 1:
                    row = src.readline()
                    if not row:
                        break

                    row = row.rstrip("\n")
                    total_count += import_tick_mt4(broker_id, market_id, cur_from_date, cur_to_date, row)

            elif cur_timeframe > 0:
                while 1:
                    row = src.readline()
                    if not row:
                        break

                    row = row.rstrip("\n")
                    total_count += import_ohlc_mt4(broker_id, market_id, cur_timeframe, cur_from_date, cur_to_date, row)

    except Exception as e:
        error_logger.error(str(e))
    finally:
        src.close()
        src = None

    Terminal.inst().info("Imported %s samples" % (total_count))

    Terminal.inst().info("Flushing database...")
    Terminal.inst().flush() 

    Database.terminate()

    Terminal.inst().info("Importation done!")
    Terminal.inst().flush()

    Terminal.terminate()
    sys.exit(0)
