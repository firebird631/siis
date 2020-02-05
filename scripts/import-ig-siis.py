#!/usr/bin/python3
import sys
import subprocess
import pathlib

BROKER = "ig.com"
BASE_PATH = "/mnt/storage/Data/market/ig.com/dumps"
PREFIX = "full"

MARKETS = {
    "CS.D.AUDNZD.MINI.IP": "AUDNZD",
    "CS.D.AUDUSD.MINI.IP": "AUDUSD",
    "CS.D.EURCAD.MINI.IP": "EURCAD",
    "CS.D.EURCHF.MINI.IP": "EURCHF",
    "CS.D.EURGBP.MINI.IP": "EURGBP",
    "CS.D.EURUSD.MINI.IP": "EURUSD",
    "IX.D.DAX.IFMM.IP": "GER30",
    "CS.D.GBPUSD.MINI.IP": "GBPUSD",
    "IX.D.NASDAQ.IFE.IP": "NAS100",
    "IX.D.SPTRD.IFE.IP": "SPX500",
    "IX.D.DOW.IFE.IP": "US30",
    "CS.D.USDCHF.MINI.IP": "USDCHF",
    "CS.D.USDJPY.MINI.IP": "USDJPY",
    # "CS.D.CFDSILVER.CFM.IP": "XAGUSD",
    "CS.D.CFEGOLD.CFE.IP": "XAUUSD"
    # @todo WTI
}

IMPORT_TFS = {
    "1m": "2017-12-25T00:00:00",
    "3m": "2019-12-25T00:00:00",
    "5m": "2019-12-15T00:00:00",
    "15m": "2019-12-01T00:00:00",
    "30m": "2019-10-01T00:00:00",
    "1h": "2019-07-01T00:00:00",
    "2h": "2019-07-01T00:00:00",
    "4h": "2019-01-01T00:00:00",
    "1d": "2017-01-01T00:00:00",
    "1w": "2010-01-01T00:00:00",
    "1M": "2000-01-01T00:00:00"
}


def import_siis_any(market, symbol, prefix="full"):
    """Unique file for any timeframes"""
    src_path = pathlib.Path(BASE_PATH, market)

    if not src_path.exists():
        print("! Missing path for %s" % market)
        return

    print("Import %s in %s from %s" % (market, "any", src_path))
    with subprocess.Popen(["python", "siis.py", "real", "--import", "--filename=%s/full-%s-%s-any.siis" % (src_path, BROKER, market)]):
        print("-- Done")


def import_siis(market, symbol, prefix="full"):
    """Distinct file per timeframe"""
    for tf, lfrom in IMPORT_TFS.items():
        src_path = pathlib.Path(BASE_PATH, market)

        if not src_path.exists():
            print("! Missing path for %s" % market)
            return

        print("Import %s in %s from %s" % (market, tf, src_path))
        with subprocess.Popen(["python", "siis.py", "real", "--import", "--filename=%s/full-%s-%s-%s.siis" % (src_path, BROKER, market, tf)]):
            print("-- Done")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # overrides
        BASE_PATH = sys.argv[1]

    if len(sys.argv) > 2:
        # overrides
        PREFIX = sys.argv[2]

    for market, symbol in MARKETS.items():
        # use unique file
        import_siis_any(market, symbol, PREFIX)
