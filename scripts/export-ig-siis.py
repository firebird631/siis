#!/usr/bin/python3
import sys
import subprocess
import pathlib

BROKER = "ig.com"
DST_PATH = "/mnt/storage/Data/market/ig.com/siis"
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
    "CS.D.CFDSILVER.CFM.IP": "XAGUSD",
    "CS.D.CFEGOLD.CFE.IP": "XAUUSD"
}

EXPORT_TF = {
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


def export_any(market, symbol, prefix="full"):
    """Unique file for any timeframes"""
    dst_path = pathlib.Path(DST_PATH, market)

    if not dst_path.exists():
        dst_path.mkdir(parents=True)

    lfrom = "2000-01-01T00:00:00"

    print("Export %s in %s from %s to %s" % (market, "any", lfrom, dst_path))
    with subprocess.Popen(["python", "siis.py", "real", "--export", "--broker=%s" % BROKER, "--market=%s" % market, "--from=%s" % lfrom,
            "--filename=%s/%s" % (dst_path, prefix)]):

        print("-- Done")


def export(market, symbol, prefix="full"):
    """Distinct file per timeframe"""
    for tf, lfrom in EXPORT_TF.items():
        dst_path = pathlib.Path(DST_PATH, market)

        if not dst_path.exists():
            dst_path.mkdir(parents=True)

        print("Export %s in %s from %s to %s" % (market, tf, lfrom, dst_path))
        with subprocess.Popen(["python", "siis.py", "real", "--export", "--broker=%s" % BROKER, "--market=%s" % market, "--from=%s" % lfrom,
                "--filename=%s/%s" % (dst_path, prefix), "--timeframe=%s" % tf]):

            print("-- Done")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # overrides
        DST_PATH = sys.argv[1]

    if len(sys.argv) > 2:
        # overrides
        PREFIX = sys.argv[2]

    for market, symbol in MARKETS.items():
        # use unique file
        export_any(market, symbol, PREFIX)
