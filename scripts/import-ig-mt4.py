#!/usr/bin/python3
import sys
import subprocess
import pathlib

MODE = "ohlc"
BROKER = "ig.com"
BASE_PATH = "/mnt/storage/Data/market/ig.com/MT4"

MARKETS = {
    "CS.D.AUDNZD.MINI.IP": "AUDNZD",
    "CS.D.AUDUSD.MINI.IP": "AUDUSD",
    "CS.D.EURCAD.MINI.IP": "EURCAD",
    "CS.D.EURCHF.MINI.IP": "EURCHF",
    "CS.D.EURGBP.MINI.IP": "EURGBP",
    "CS.D.EURJPY.MINI.IP": "EURJPY",
    "CS.D.EURUSD.MINI.IP": "EURUSD",
    "IX.D.DAX.IFMM.IP": "GER30",
    "CS.D.GBPUSD.MINI.IP": "GBPUSD",
    "IX.D.NASDAQ.IFE.IP": "NAS100",
    "IX.D.SPTRD.IFE.IP": "SPX500",
    "IX.D.DOW.IFE.IP": "US30",
    "CS.D.USDCHF.MINI.IP": "USDCHF",
    "CS.D.USDJPY.MINI.IP": "USDJPY",
    # "CS.D.CFDSILVER.CFM.IP": "XAGUSD",
    "CS.D.CFEGOLD.CFE.IP": "XAUUSD",
    # @todo WTI
}

IMPORT_TFS = {
    "1m": "2019-12-25T00:00:00",
    # "3m": "2019-12-25T00:00:00",
    "5m": "2019-12-15T00:00:00",
    "15m": "2019-12-01T00:00:00",
    "30m": "2019-10-01T00:00:00",
    "1h": "2019-07-01T00:00:00",
    # "2h": "2019-07-01T00:00:00",
    "4h": "2019-01-01T00:00:00",
    "1d": "2017-01-01T00:00:00",
    "1w": "2010-01-01T00:00:00",
    "1M": "2000-01-01T00:00:00"
}

# second to minutes
TFS_TO_MT4 = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "2h": "120",
    "4h": "240",
    "1d": "1440",
    "1w": "10080",
    "1M": "43200"
}


def import_mt4_ohlc(market, symbol):
    """Distinct file per timeframe"""
    for tf, lfrom in IMPORT_TFS.items():
        src_path = pathlib.Path(BASE_PATH, symbol)

        if not src_path.exists():
            print("! Missing path for %s" % symbol)
            return

        print("Import %s in %s from %s" % (market, tf, src_path))
        with subprocess.Popen(["python", "siis.py", "real", "--import",
                               "--broker=%s" % BROKER,
                               "--market=%s" % market,
                               "--timeframe=%s" % tf,
                               "--from=%s" % lfrom,
                               "--filename=%s/%s%s.csv" % (src_path, symbol, TFS_TO_MT4[tf])]) as p:
            p.wait()
            print("-- Done")

    # build 3m and 2h
    print("+ Rebuild 3m OHLCs from 1m for %s" % market)
    with subprocess.Popen(["python", "siis.py", "real", "--rebuild",
                           "--broker=%s" % BROKER,
                           "--market=%s" % market,
                           "--timeframe=1m",
                           "--target=3m",
                           "--from=%s" % IMPORT_TFS['1m']]) as p:
        p.wait()
        print("-- Done")

    print("+ Rebuild 2h OHLCs from 1h for %s" % market)
    with subprocess.Popen(["python", "siis.py", "real", "--rebuild",
                           "--broker=%s" % BROKER,
                           "--market=%s" % market,
                           "--timeframe=1h",
                           "--target=2h",
                           "--from=%s" % IMPORT_TFS['1h']]) as p:
        p.wait()
        print("-- Done")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # overrides
        BASE_PATH = sys.argv[1]

    if len(sys.argv) > 2:
        # overrides
        MODE = sys.argv[2]

    if MODE == "ohlc":
        for _market, _symbol in MARKETS.items():
            # use unique file
            import_mt4_ohlc(_market, _symbol)
