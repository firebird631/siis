#!/usr/bin/python3
import sys
import subprocess
import pathlib

import pytz
from datetime import datetime

MODE = "tick"
BROKER = "ig.com"
BASE_PATH = "/mnt/storage/Data/market/ig.com/MT5"
FROM = datetime.strptime("2018-01-01T00:00", "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.utc)
TO = datetime.strptime("2020-01-03T23:59", "%Y-%m-%dT%H:%M").replace(tzinfo=pytz.utc)

MARKETS = {
    "CS.D.AUDNZD.MINI.IP": "AUDNZD",
    "CS.D.AUDUSD.MINI.IP": "AUDUSD",
    "CS.D.EURCAD.MINI.IP": "EURCAD",
    "CS.D.EURCHF.MINI.IP": "EURCHF",
    "CS.D.EURGBP.MINI.IP": "EURGBP",
    "CS.D.EURJPY.MINI.IP": "EURJPY",
    "CS.D.EURUSD.MINI.IP": "EURUSD",
    # "IX.D.DAX.IFMM.IP": "GER30",
    "CS.D.GBPUSD.MINI.IP": "GBPUSD",
    # "IX.D.NASDAQ.IFE.IP": "NAS100",
    # "IX.D.SPTRD.IFE.IP": "SPX500",
    # "IX.D.DOW.IFE.IP": "US30",
    "CS.D.USDCHF.MINI.IP": "USDCHF",
    "CS.D.USDJPY.MINI.IP": "USDJPY",
    # "CS.D.CFDSILVER.CFM.IP": "XAGUSD",
    "CS.D.CFEGOLD.CFE.IP": "XAUUSD",
    # @todo WTI
}

GENERATE_TFS = {
    "1m": ("2019-12-25T00:00:00", "t"),
    "3m": ("2019-12-25T00:00:00", "1m"),
    "5m": ("2019-12-15T00:00:00", "1m"),
    "15m": ("2019-12-01T00:00:00", "5m"),
    "30m": ("2019-10-01T00:00:00", "15m"),
    "1h": ("2019-07-01T00:00:00", "30m"),
    "2h": ("2019-07-01T00:00:00", "1h"),
    "4h": ("2019-01-01T00:00:00", "2h"),
    "1d": ("2017-01-01T00:00:00", "4h"),
    "1w": ("2010-01-01T00:00:00", "1d"),
    "1M": ("2000-01-01T00:00:00", "1d")
}

FILES_INITIAL = {
    "AUDNZD": "AUDNZD_201801020002_202001032354.csv",
    "AUDUSD": "AUDUSD_201801020003_202001032354.csv",
    "EURCAD": "EURCAD_201801020001_202001032354.csv",
    "EURCHF": "EURCHF_201801020001_202001032354.csv",
    "EURGBP": "EURGBP_201801020000_202001032354.csv",
    "EURJPY": "EURJPY_201801020001_202001032354.csv",
    "EURUSD": "EURUSD_201801020000_202001032354.csv",
    # "GER30": "",
    "GBPUSD": "GBPUSD_201801020001_202001032354.csv",
    # "NAS100": "",
    # "SPX500": "",
    # "US30": "",
    "USDCHF": "USDCHF_201801020005_202001032354.csv",
    "USDJPY": "USDJPY_201801020001_202001032354.csv",
    "XAGUSD": "XAGUSD_201801020900_202001032354.csv",
    "XAUUSD": "XAUUSD_201801020900_202001032354.csv"
}

FILES_NEXT = {
    "AUDNZD": "AUDNZD_202001060001_202001102354.csv",
    "AUDUSD": "AUDUSD_202001060002_202001102354.csv",
    "EURCAD": "EURCAD_202001060001_202001102354.csv",
    "EURCHF": "EURCHF_202001060002_202001102354.csv",
    "EURGBP": "EURGBP_202001060002_202001102354.csv",
    "EURJPY": "EURJPY_202001060002_202001102354.csv",
    "EURUSD": "EURUSD_202001060002_202001102354.csv",
    # "GER30": "",
    "GBPUSD": "GBPUSD_202001060002_202001102354.csv",
    # "NAS100": "",
    # "SPX500": "",
    # "US30": "",
    "USDCHF": "USDCHF_202001060002_202001102355.csv",
    "USDJPY": "USDJPY_202001060002_202001102354.csv",
    "XAGUSD": "XAGUSD_202001060105_202001102354.csv",
    "XAUUSD": "XAUUSD_202001060105_202001102354.csv"
}

# second to minutes
TFS_TO_MT5 = {
    "1m": "M1",
    "3m": "M3",
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
    "2h": "H2",
    "4h": "H4",
    "1d": "D1",
    "1w": "W1",
    "1M": "??"
}


def import_mt5_tick(market, symbol, from_to):
    """One file of tick"""
    # @todo from/to list from glob
    src_path = pathlib.Path(BASE_PATH, symbol)

    if not src_path.exists():
        print("! Missing path for %s" % symbol)
        return

    dt_from = from_to[0]

    print("Import %s in %s from tick" % (market, src_path))
    with subprocess.Popen(["python", "siis.py", "real", "--import",
                           "--broker=%s" % BROKER,
                           "--market=%s" % market,
                           "--timeframe=t", "--from=%s" % dt_from.strftime("%Y-%m-%dT%H:%M"),
                           "--filename=%s/%s_%s_%s.csv" % (
                src_path, symbol, FROM, TO)]) as p:
        p.wait()
        print("-- Done")

    # build OHLCs
    for to_tf, (lfrom, from_tf) in GENERATE_TFS.items():
        print("+ Rebuild %s OHLCs from %s for %s" % (to_tf, from_tf, market))
        with subprocess.Popen(["python", "siis.py", "real", "--rebuild",
                               "--broker=%s" % BROKER,
                               "--market=%s" % market,
                               "--timeframe=%s" % from_tf,
                               "--target=%s" % to_tf,
                               "--from=%s" % lfrom]) as p:

            p.wait()
            print("-- Done")


def import_mt5_tick_files(market, symbol, dt_from, dt_to, files):
    """One file of tick"""
    src_path = pathlib.Path(BASE_PATH, symbol)

    if not src_path.exists():
        print("! Missing path for %s" % symbol)
        return

    filename = "%s/%s" % (src_path, FILES_INITIAL[symbol])
    # filename = "%s/%s_%s_%s.csv" % (src_path, symbol, dt_from.strftime("%Y%m%d%H%M"), dt_to.strftime("%Y%m%d%H%M"))

    print("Import %s in %s from tick" % (market, src_path))
    with subprocess.Popen(["python", "siis.py", "real", "--import",
                           "--broker=%s" % BROKER,
                           "--market=%s" % market,
                           "--timeframe=t",
                           "--from=%s" % dt_from.strftime("%Y-%m-%dT%H:%M"),
                           "--filename=%s" % filename]) as p:

        p.wait()
        print("-- Done")

    # build OHLCs
    for to_tf, (_, from_tf) in GENERATE_TFS.items():
        print("+ Rebuild %s OHLCs from %s for %s" % (to_tf, from_tf, market))
        with subprocess.Popen(["python", "siis.py", "real", "--rebuild",
                               "--broker=%s" % BROKER,
                               "--market=%s" % market,
                               "--timeframe=%s" % from_tf,
                               "--target=%s" % to_tf,
                               "--from=%s" % dt_from.strftime("%Y-%m-%dT%H:%M"),
                               "--to=%s" % dt_to.strftime("%Y-%m-%dT%H:%M")]) as p:

            p.wait()
            print("-- Done")


if __name__ == "__main__":
    for arg in sys.argv:
        if arg.startswith('--mode='):
            # overrides
            MODE = arg.split('=')[1]
        elif arg.startswith('--path'):
            # overrides
            BASE_PATH = arg.split('=')[1]

    if MODE == "tick":
        for _market, _symbol in MARKETS.items():
            # use unique file
            import_mt5_tick(_market, _symbol, [(FROM, TO)])

    elif MODE == "tick-bt":
        for _market, _symbol in MARKETS.items():
            # use unique file
            import_mt5_tick_files(_market, _symbol, FROM, TO, FILES_INITIAL)

    elif MODE == "tick-lw":
        for _market, _symbol in MARKETS.items():
            # use unique file
            import_mt5_tick_files(_market, _symbol, FROM, TO, FILES_NEXT)
