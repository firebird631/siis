# @date 2019-12-23
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# SIIS and MT4, MT5 Importer tool.

import sys
import logging
import traceback
import zipfile
import pathlib

from datetime import datetime, timedelta
from tools.tool import Tool

from instrument.instrument import Instrument
from common.utils import UTC, TIMEFRAME_FROM_STR_MAP, timeframe_from_str, timeframe_to_str, format_datetime, format_delta

from terminal.terminal import Terminal
from database.database import Database

import logging
logger = logging.getLogger('siis.tools.importer')
error_logger = logging.getLogger('siis.error.tools.importer')


class Importer(object):  # Tool
    """
    SIIS and MT4, MT5 Importer tool.

    format SIIS version 1.0.0 : tick, trade, quote, ohlc
    format MT4 : tick, ohlc
    format MT5 : tick, ohlc
    """

    def __init__(self):
        self.prev_bid = None
        self.prev_ask = None


FORMAT_UNDEFINED = 0
FORMAT_SIIS = 1
FORMAT_MT4 = 2
FORMAT_MT5 = 3

MT4_TIMEFRAMES = {
    '1': Instrument.TF_1M,
    '2': Instrument.TF_2M,
    '3': Instrument.TF_3M,
    '5': Instrument.TF_5M,
    '10': Instrument.TF_10M,
    '15': Instrument.TF_15M,
    '30': Instrument.TF_30M,
    '60': Instrument.TF_1H,
    '120': Instrument.TF_2H,
    '240': Instrument.TF_4H,
    '1440': Instrument.TF_1D,
    '10080': Instrument.TF_1W
}

MT5_TIMEFRAMES = {
    'M1': Instrument.TF_1M,
    'M2': Instrument.TF_2M,
    'M3': Instrument.TF_3M,
    'M5': Instrument.TF_5M,
    'M10': Instrument.TF_10M,
    'M15': Instrument.TF_15M,
    'M30': Instrument.TF_30M,
    'H1': Instrument.TF_1H,
    'H2': Instrument.TF_2H,
    'H4': Instrument.TF_4H,
    'D1': Instrument.TF_1D,
    'W1': Instrument.TF_1W
}

prev_bid = None
prev_ask = None


def import_tick_siis_1_0_0(broker_id, market_id, from_date, to_date, row):
    parts = row.split('\t')

    dt = datetime.strptime(parts[0], '%Y%m%d %H%M%S%f').replace(tzinfo=UTC())
    timestamp = int(dt.timestamp() * 1000)

    if from_date and dt < from_date:
        return 0

    if to_date and dt > to_date:
        return 0

    Database.inst().store_market_trade((
        broker_id, market_id, timestamp,
        *parts[1:]))

    return 1


def import_trade_siis_1_0_0(broker_id, market_id, from_date, to_date, row):
    return 0


def import_quote_siis_1_0_0(broker_id, market_id, from_date, to_date, row):
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


def import_tick_mt4(self, broker_id, market_id, from_date, to_date, row):
    """
    Date + time MT4 tick

    DATE,TIME,BID,ASK,LAST,VOL
    """
    parts = row.split(',')

    dt = datetime.strptime(parts[0] + ' ' + parts[1], '%Y.%m.%d %H:%M:%S.%f').replace(tzinfo=UTC())
    timestamp = int(dt.timestamp() * 1000)

    if from_date and dt < from_date:
        return 0

    if to_date and dt > to_date:
        return 0

    if parts[2]:
        self.prev_bid = parts[2]
    
    if parts[3]:
        self.prev_ask = parts[3]

    if parts[5]:
        fvol = parts[5]
    else:
        fvol = "1"

    Database.inst().store_market_trade((
        broker_id, market_id, timestamp,
        self.prev_bid, self.prev_ask,
        fvol))

    return 1


def import_ohlc_mt4(broker_id, market_id, timeframe, from_date, to_date, row):
    """
    Date + time MT4 OHLC

    DATE,TIME,OPEN,HIGH,LOW,CLOSE,TICKVOL
    """
    parts = row.split(',')

    dt = datetime.strptime(parts[0] + ' ' + parts[1], '%Y.%m.%d %H:%M').replace(tzinfo=UTC())
    timestamp = int(dt.timestamp() * 1000)

    if from_date and dt < from_date:
        return 0

    if to_date and dt > to_date:
        return 0

    if parts[6]:
        fvol = parts[6]
    else:
        fvol = "1"

    Database.inst().store_market_ohlc((
        broker_id, market_id, timestamp, int(timeframe),
        parts[2], parts[3], parts[4], parts[5],
        parts[2], parts[3], parts[4], parts[5],
        fvol))

    return 1


def import_ohlc_mt4_long(broker_id, market_id, timeframe, from_date, to_date, row):
    """
    Date + time + vol + spread MT4 OHLC

    DATE,TIME,OPEN,HIGH,LOW,CLOSE,TICKVOL,VOL,SPREAD
    """
    parts = row.split(',')

    dt = datetime.strptime(parts[0] + ' ' + parts[1], '%Y.%m.%d %H:%M').replace(tzinfo=UTC())
    timestamp = int(dt.timestamp() * 1000)

    if from_date and dt < from_date:
        return 0

    if to_date and dt > to_date:
        return 0

    # vol else tick vol
    tickvol = float(parts[6]) if parts[6] else 0.0
    vol = float(parts[7]) if parts[7] else 0.0

    if vol > 0:
        fvol = parts[7]
    elif tickvol > 0:
        fvol = parts[6]
    else:
        fvol = "1"

    Database.inst().store_market_ohlc((
        broker_id, market_id, timestamp, int(timeframe),
        parts[2], parts[3], parts[4], parts[5],
        parts[2], parts[3], parts[4], parts[5],
        fvol))

    return 1


def import_tick_mt5(self, broker_id, market_id, from_date, to_date, row):
    """
    Date + time MT5 tick

    <DATE>  <TIME>  <BID>   <ASK>   <LAST>  <VOLUME>
    """
    parts = row.split('\t')

    dt = datetime.strptime(parts[0] + ' ' + parts[1], '%Y.%m.%d %H:%M:%S.%f').replace(tzinfo=UTC())
    timestamp = int(dt.timestamp() * 1000)

    if from_date and dt < from_date:
        return 0

    if to_date and dt > to_date:
        return 0

    if parts[2]:
        self.prev_bid = parts[2]

    if parts[3]:
        self.prev_ask = parts[3]

    if parts[5]:
        ltv = parts[5]
    else:
        ltv = "1"  # at least 1 tick mean 1 tick volume, but could depend of what we want

    Database.inst().store_market_trade((
        broker_id, market_id, timestamp,
        self.prev_bid, self.prev_ask,
        ltv))

    return 1


def import_ohlc_mt5(broker_id, market_id, timeframe, from_date, to_date, row):
    """
    Date MT5 OHLC

    <DATE>  <OPEN>  <HIGH>  <LOW>   <CLOSE> <TICKVOL>   <VOL>   <SPREAD>
    """
    parts = row.split('\t')

    dt = datetime.strptime(parts[0], '%Y.%m.%d').replace(tzinfo=UTC())
    timestamp = int(dt.timestamp() * 1000)

    if from_date and dt < from_date:
        return 0

    if to_date and dt > to_date:
        return 0

    # vol else tick vol
    tickvol = float(parts[5]) if parts[5] else 0.0
    vol = float(parts[6]) if parts[6] else 0.0

    if vol > 0:
        fvol = parts[6]
    elif tickvol > 0:
        fvol = parts[5]
    else:
        fvol = "1"

    Database.inst().store_market_ohlc((
        broker_id, market_id, timestamp, int(timeframe),
        parts[1], parts[2], parts[3], parts[4],
        parts[1], parts[2], parts[3], parts[4],
        fvol))

    return 1


def import_ohlc_mt5_time(broker_id, market_id, timeframe, from_date, to_date, row):
    """
    Date + time MT5 OHLC
    
    <DATE>  <TIME>  <OPEN>  <HIGH>  <LOW>   <CLOSE> <TICKVOL>   <VOL>   <SPREAD>
    """
    parts = row.split('\t')

    dt = datetime.strptime(parts[0] + ' ' + parts[1], '%Y.%m.%d %H:%M:%S').replace(tzinfo=UTC())
    timestamp = int(dt.timestamp() * 1000)

    if from_date and dt < from_date:
        return 0

    if to_date and dt > to_date:
        return 0

    # vol else tick vol
    tickvol = float(parts[6]) if parts[6] else 0.0
    vol = float(parts[7]) if parts[7] else 0.0

    if vol > 0:
        fvol = parts[7]
    elif tickvol > 0:
        fvol = parts[6]
    else:
        fvol = "1"

    Database.inst().store_market_ohlc((
        broker_id, market_id, timestamp, int(timeframe),
        parts[2], parts[3], parts[4], parts[5],
        parts[2], parts[3], parts[4], parts[5],
        fvol))

    return 1


def unzip_file(filename, tmpdir="/tmp/"):
    target = tmpdir + 'siis_' + filename.split('/')[-1].rstrip(".zip")

    with zipfile.ZipFile(filename, 'r') as zip_ref:
        zip_ref.extractall(target)

    return target


def error_exit(src, msg):
    if src:
        src.close()

    error_logger.error(msg)

    Database.terminate()
    Terminal.terminate()

    sys.exit(-1)


def do_importer(options):
    tool = Importer()

    Terminal.inst().info("Starting SIIS importer...")
    Terminal.inst().flush()

    # database manager
    Database.create(options)
    Database.inst().setup(options)

    # want speedup the database inserts
    Database.inst().enable_fetch_mode()

    filename = options.get('filename')
    detected_format = FORMAT_UNDEFINED
    detected_timeframe = None
    
    is_mtx_tick = False
    is_mtx_time = False
    is_mtx_long = False

    pathname = pathlib.Path(filename)
    if not pathname.exists():
        error_exit(None, "File %s does not exists" % pathname.name)

    timeframe = None

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

    if filename.endswith(".siis"):
        detected_format = FORMAT_SIIS
    elif filename.endswith(".csv"):
        # detect the format from the first row
        row = src.readline().rstrip('\n')
        if row.count('\t') > 0:
            # tabular based file, might be MT5, with an header row
            if row.count('\t') == 5 and row == "<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>":
                # ticks
                detected_format = FORMAT_MT5
                detected_timeframe = Instrument.TF_TICK
                is_mtx_tick = True
                is_mtx_time = True
                is_mtx_long = False

            elif row.count('\t') == 7 and row == "<DATE>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>":
                # has not time col, true vol and spread
                detected_format = FORMAT_MT5
                is_mtx_tick = False
                is_mtx_time = False
                is_mtx_long = True

                # from filename try to detect the timeframe
                parts = pathname.name.split('_')
                if len(parts) >= 2:
                    detected_timeframe = MT5_TIMEFRAMES.get(parts[1])

            elif row.count('\t') == 8 and row == "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>":
                # has time col, true vol and spread
                detected_format = FORMAT_MT5
                is_mtx_tick = False
                is_mtx_time = True
                is_mtx_long = True

                # from filename try to detect the timeframe
                parts = pathname.name.split('_')
                if len(parts) >= 2:
                    detected_timeframe = MT5_TIMEFRAMES.get(parts[1])

            # ignore the header line
        elif row.count(',') > 0:
            # comma based file, might be MT4, without header row
            if row.count(',') == 4:
                # ticks
                detected_format = FORMAT_MT4
                detected_timeframe = Instrument.TF_TICK
                
                is_mtx_tick = True
                is_mtx_time = True
                is_mtx_long = False

            elif row.count(',') == 6:
                # has always time col
                detected_format = FORMAT_MT4

                is_mtx_tick = False
                is_mtx_time = True
                is_mtx_long = False

                # from filename try to detect the timeframe
                parts = pathname.name.split('.')
                if len(parts) > 0:
                    for mt_tf, tf in MT4_TIMEFRAMES.items():
                        if parts[0].endswith(mt_tf):
                            detected_timeframe = tf
                            break

            elif row.count(',') == 8:
                # has true vol and spread cols
                detected_format = FORMAT_MT4

                is_mtx_tick = False
                is_mtx_time = True
                is_mtx_long = True

                # from filename try to detect the timeframe
                parts = pathname.name.split('.')
                if len(parts) > 0:
                    for mt_tf, tf in MT4_TIMEFRAMES.items():
                        if parts[0].endswith(mt_tf):
                            detected_timeframe = tf
                            break

            # reset because first row is data
            src.seek(0, 0)

    if detected_format == FORMAT_UNDEFINED:
         error_exit(src, "Unknown file format")

    if detected_format in (FORMAT_MT4, FORMAT_MT5):
        if detected_timeframe is not None and timeframe is None:
            Terminal.inst().message("Auto-detected timeframe %s" % timeframe_to_str(detected_timeframe))

        if detected_timeframe and timeframe and detected_timeframe != timeframe:
            error_exit(src, "Auto-detected timeframe %s is different of specified timeframe %s" % (
                timeframe_to_str(detected_timeframe), timeframe_to_str(timeframe)))

    market_id = ""
    broker_id = ""

    # UTC option dates    
    from_date = options.get('from')
    to_date = options.get('to')

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
    else:
        # need broker, market and timeframe
        broker_id = options.get('broker')
        market_id = options.get('market')

        if not broker_id:
            error_exit(src, "Missing target broker identifier")

        if not market_id or ',' in market_id:
            error_exit(src, "Missing or invalid target market identifier")

        if timeframe is None:
            if is_mtx_tick:
                timeframe = Instrument.TF_TICK
            elif detected_timeframe:
                timeframe = detected_timeframe
            else:
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
            cur_timeframe = timeframe if not is_mtx_tick else Instrument.TF_TICK
            cur_from_date = from_date
            cur_to_date = to_date

            if cur_timeframe == Instrument.TF_TICK:
                while 1:
                    row = src.readline()
                    if not row:
                        break

                    row = row.rstrip("\n")
                    total_count += import_tick_mt4(tool, broker_id, market_id, cur_from_date, cur_to_date, row)

            elif cur_timeframe > 0:
                if is_mtx_long:
                    while 1:
                        row = src.readline()
                        if not row:
                            break

                        row = row.rstrip("\n")
                        total_count += import_ohlc_mt4_long(broker_id, market_id, cur_timeframe, cur_from_date, cur_to_date, row)
                else:
                    while 1:
                        row = src.readline()
                        if not row:
                            break

                        row = row.rstrip("\n")
                        total_count += import_ohlc_mt4(broker_id, market_id, cur_timeframe, cur_from_date, cur_to_date, row)

        elif detected_format == FORMAT_MT5:
            cur_timeframe = timeframe if not is_mtx_tick else Instrument.TF_TICK
            cur_from_date = from_date
            cur_to_date = to_date

            if cur_timeframe == Instrument.TF_TICK:
                while 1:
                    row = src.readline()
                    if not row:
                        break

                    row = row.rstrip("\n")
                    total_count += import_tick_mt5(tool, broker_id, market_id, cur_from_date, cur_to_date, row)

            elif cur_timeframe > 0:
                if is_mtx_time:
                    while 1:
                        row = src.readline()
                        if not row:
                            break

                        row = row.rstrip("\n")
                        total_count += import_ohlc_mt5_time(broker_id, market_id, cur_timeframe, cur_from_date, cur_to_date, row)
                else:
                    while 1:
                        row = src.readline()
                        if not row:
                            break

                        row = row.rstrip("\n")
                        total_count += import_ohlc_mt5(broker_id, market_id, cur_timeframe, cur_from_date, cur_to_date, row)

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
