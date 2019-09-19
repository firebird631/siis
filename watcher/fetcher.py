# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Fetcher interface

import time

from datetime import datetime, timedelta

from common.utils import matching_symbols_set, UTC
from terminal.terminal import Terminal

from instrument.instrument import Tick, Candle, Instrument
from instrument.candlegenerator import CandleGenerator

from notifier.signal import Signal
from config import config
from database.database import Database

import logging
logger = logging.getLogger('siis.fetcher')


class Fetcher(object):
    """
    Fetcher base class.
    Fetch trade if support else candles of a base timeframe, and then generate the higher candle according to
    thie GENERATED_TF list (from 1 sec to 1 week).
    """

    # candles from 1m to 1 week
    GENERATED_TF = [60, 60*5, 60*15, 60*60, 60*60*2, 60*60*4, 60*60*24, 60*60*24*7]

    TICK_STORAGE_DELAY = 0.05  # 50ms
    MAX_PENDING_TICK = 10000

    def __init__(self, name, service):
        super().__init__()

        self._name = name
        self._service = service

        self._available_instruments = set()

        self._last_ticks = []
        self._last_ohlcs = {}

    @property
    def service(self):
        return self._service

    @property
    def name(self):
        return self._name
    
    def has_instrument(self, instrument, fetch_option=""):
        return instrument in self._available_instruments

    def available_instruments(self):
        return self._available_instruments

    def matching_symbols_set(self, configured_symbols, available_symbols):
        """
        Special '*' symbol mean every symbol.
        Starting with '!' mean except this symbol.
        Starting with '*' mean every wildchar before the suffix.

        @param available_symbols List containing any supported markets symbol of the broker. Used when a wildchar is defined.
        """
        return matching_symbols_set(configured_symbols, available_symbols)

    def connect(self):
        pass

    def disconnect(self):
        pass

    @property
    def connected(self):
        return False

    def fetch_and_generate(self, market_id, timeframe, from_date=None, to_date=None, n_last=1000, fetch_option="", cascaded=None):
        if timeframe > 0 and timeframe not in self.GENERATED_TF:
            logger.error("Timeframe %i is not allowed !" % (timeframe,))
            return

        generators = []
        from_tf = timeframe

        self._last_ticks = []
        self._last_ohlcs = {}

        if not from_date and n_last:
            # compute a from date
            today = datetime.now().astimezone(UTC())

            if timeframe == Instrument.TF_MONTH:
                from_date = today - timedelta(months=int(timeframe/Instrument.TF_MONTH)*n_last)
            else:
                from_date = today - timedelta(seconds=timeframe*n_last)

        if not to_date:
            today = datetime.now().astimezone(UTC())

            if timeframe == Instrument.TF_MONTH:
                to_date = today + timedelta(months=1)
            else:
                to_date = today + timedelta(seconds=timeframe)

        # cascaded generation of candles
        if cascaded:
            for tf in Fetcher.GENERATED_TF:
                if tf > timeframe:
                    # from timeframe greater than initial
                    if tf <= cascaded:
                        # until max cascaded timeframe
                        generators.append(CandleGenerator(from_tf, tf))
                        from_tf = tf

                        # store for generation
                        self._last_ohlcs[tf] = []
                else:
                    from_tf = tf

        if timeframe > 0:
            self._last_ohlcs[timeframe] = []

        n = 0
        t = 0

        if timeframe == 0:
            for data in self.fetch_trades(market_id, from_date, to_date, None):
                # store (int timestamp in ms, str bid, str ofr, str volume)
                Database.inst().store_market_trade((self.name, market_id, data[0], data[1], data[2], data[3]))

                if generators:
                    self._last_ticks.append((float(data[0]) * 0.001, float(data[1]), float(data[2]), float(data[3])))

                # generate higher candles
                for generator in generators:
                    if generator.from_tf == 0:
                        candles = generator.generate_from_ticks(self._last_ticks)

                        if candles:
                            for c in candles:
                                self.store_candle(market_id, generator.to_tf, c)

                            self._last_ohlcs[generator.to_tf] += candles

                        # remove consumed ticks
                        self._last_ticks = []
                    else:
                        candles = generator.generate_from_candles(self._last_ohlcs[generator.from_tf])

                        if candles:
                            for c in candles:
                                self.store_candle(market_id, generator.to_tf, c)

                            self._last_ohlcs[generator.to_tf] += candles

                        # remove consumed candles
                        self._last_ohlcs[generator.from_tf] = []

                n += 1
                t += 1

                if n == 1000:
                    n = 0
                    Terminal.inst().info("%i..." % t)
                    Terminal.inst().flush()

                    # calm down the storage of tick, if parsing is faster
                    while Database.inst().num_pending_ticks_storage() > Fetcher.TICK_STORAGE_DELAY:
                        time.sleep(Fetcher.TICK_STORAGE_DELAY)  # wait a little before continue

            logger.info("Fetched %i trades" % t)

        elif timeframe > 0:
            for data in self.fetch_candles(market_id, timeframe, from_date, to_date, None):
                # store (int timestamp ms, str open bid, high bid, low bid, close bid, open ofr, high ofr, low ofr, close ofr, volume)
                Database.inst().store_market_ohlc((
                    self.name, market_id, data[0], int(timeframe),
                    data[1], data[2], data[3], data[4],
                    data[5], data[6], data[7], data[8],
                    data[9]))

                if generators:
                    candle = Candle(float(data[0]) * 0.001, timeframe)

                    candle.set_bid_ohlc(float(data[1]), float(data[2]), float(data[3]), float(data[4]))
                    candle.set_ofr_ohlc(float(data[5]), float(data[6]), float(data[7]), float(data[8]))

                    candle.set_volume(float(data[9]))
                    candle.set_consolidated(True)

                    self._last_ohlcs[timeframe].append(candle)

                # generate higher candles
                for generator in generators:
                    candles = generator.generate_from_candles(self._last_ohlcs[generator.from_tf])
                    if candles:
                        for c in candles:
                            self.store_candle(market_id, generator.to_tf, c)

                        self._last_ohlcs[generator.to_tf].extend(candles)

                    # remove consumed candles
                    self._last_ohlcs[generator.from_tf] = []

                n += 1
                t += 1

                if n == 1000:
                    n = 0
                    Terminal.inst().info("%i..." % t)

        logger.info("Fetched %i candles" % t)

    def fetch_trades(self, market_id, from_date=None, to_date=None, n_last=None):
        """
        Retrieve the historical trades data for a certain a period of date.
        @param market_id Specific name of the market
        @param from_date
        @param to_date
        """
        pass

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        """
        Retrieve the historical candles data for an unit of time and certain a period of date.
        @param market_id Specific name of the market
        @param timeframe Time unit in second.
        @param from_date
        @param to_date
        @param n_last Last n data
        """
        pass

    def store_candle(self, market_id, timeframe, candle):
        Database.inst().store_market_ohlc((
            self.name, market_id, int(candle.timestamp*1000.0), int(timeframe),
            str(candle.bid_open), str(candle.bid_high), str(candle.bid_low), str(candle.bid_close),
            str(candle.ofr_open), str(candle.ofr_high), str(candle.ofr_low), str(candle.ofr_close),
            str(candle.volume)))
