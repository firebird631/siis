#!/usr/bin/python3
import sys
import subprocess
import pathlib

YEAR = "2020"
MODE = "ohlc"
BROKER = "ig.com"
BASE_PATH = "/mnt/storage/Data/market/dukascopy.com/tickstory.com"

MARKETS = {
    # "CS.D.AUDNZD.MINI.IP": "AUDNZD",
    # "CS.D.AUDUSD.MINI.IP": "AUDUSD",
    # "CS.D.EURCAD.MINI.IP": "EURCAD",
    # "CS.D.EURCHF.MINI.IP": "EURCHF",
    # "CS.D.EURGBP.MINI.IP": "EURGBP",
    # "CS.D.EURJPY.MINI.IP": "EURJPY",
    # "CS.D.EURUSD.MINI.IP": "EURUSD",
    "IX.D.DAX.IFMM.IP": "DEUIDXEUR",
    # "CS.D.GBPUSD.MINI.IP": "GBPUSD",
    # "IX.D.NASDAQ.IFE.IP": "NAS100",
    # "IX.D.SPTRD.IFE.IP": "SPX500",
    # "IX.D.DOW.IFE.IP": "US30",
    # "CS.D.USDCHF.MINI.IP": "USDCHF",
    # "CS.D.USDJPY.MINI.IP": "USDJPY",
    # "CS.D.CFDSILVER.CFM.IP": "XAGUSD",
    # "CS.D.CFEGOLD.CFE.IP": "XAUUSD",
    # @todo WTI
}

IMPORT_TFS = {
    "1m": "2020-01-06T00:00:00",
    # "3m": "2019-12-25T00:00:00",
    "5m": "2020-01-06T00:00:00",
    "15m": "2020-01-06T00:00:00",
    "30m": "2020-01-06T00:00:00",
    "1h": "2020-01-06T00:00:00",
    # "2h": "2020-01-06T00:00:00",
    "4h": "2020-01-06T00:00:00",
    "1d": "2020-01-06T00:00:00",
    "1w": "2020-01-06T00:00:00",
    # "1M": "2020-01-01T00:00:00",
}

# second to minutes
TFS_TO_MT = {
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
    # "1M": "43200"
}


# bar format (MT5 bar) {BarBeginTime:yyyyMMdd},{BarBeginTime:HH:mm:ss},{Open},{High},{Low},{Close},{BarTickCount},{BarTickCount},{BarMaxSpreadInt}
# ticker format  (MT5 tick)

def import_mt5_ohlc(market, symbol, year):
    """Distinct file per timeframe"""
    for tf, lfrom in IMPORT_TFS.items():
        src_path = pathlib.Path(BASE_PATH, symbol, year)

        if not src_path.exists():
            print("! Missing path for %s %s" % (symbol, year))
            return

        print("Import %s in %s from %s/%s%s.csv" % (market, tf, src_path, symbol, TFS_TO_MT[tf]))
        with subprocess.Popen(["python", "siis.py", "real", "--import", "--broker=%s" % BROKER, "--market=%s" % market,
                "--timeframe=%s" % tf, "--from=%s" % lfrom, "--filename=%s/%s%s.csv" % (src_path, symbol, TFS_TO_MT[tf])]) as p:
            p.wait()
            print("-- Done")

    # build 3m and 2h
    print("+ Rebuild 3m OHLCs from 1m for %s" % market)
    with subprocess.Popen(["python", "siis.py", "real", "--rebuild", "--broker=%s" % BROKER, "--market=%s" % market,
            "--timeframe=1m", "--target=3m", "--from=%s" % IMPORT_TFS['1m']]) as p:
        p.wait()
        print("-- Done")

    print("+ Rebuild 2h OHLCs from 1h for %s" % market)
    with subprocess.Popen(["python", "siis.py", "real", "--rebuild", "--broker=%s" % BROKER, "--market=%s" % market,
            "--timeframe=1h", "--target=2h", "--from=%s" % IMPORT_TFS['1h']]) as p:
        p.wait()
        print("-- Done")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # overrides
        BASE_PATH = sys.argv[1]

    if len(sys.argv) > 2:
        # overrides
        MODE = sys.argv[2]

    if len(sys.argv) > 3:
        # overrides
        YEAR = sys.argv[3]

    if MODE == "ohlc":
        for market, symbol in MARKETS.items():
            # use unique file
            import_mt5_ohlc(market, symbol, YEAR)
