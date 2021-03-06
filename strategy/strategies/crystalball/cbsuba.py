# @date 2019-01-19
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Crystal Bal strategy, sub-strategy A.

from __future__ import annotations

from typing import Union

import numpy as np

from strategy.strategysignal import StrategySignal
from monitor.streamable import StreamMemberFloatSerie, StreamMemberSerie, StreamMemberFloatBarSerie, \
    StreamMemberOhlcSerie

from .cbsub import CrystalBallStrategySub

import logging
logger = logging.getLogger('siis.strategy.crystalball')


class CrystalBallStrategySubA(CrystalBallStrategySub):
    """
    Crystal Ball strategy, sub-strategy A.
    """

    def __init__(self, strategy_trader, params):
        # default indicators
        self.tomdemark = None

        self.rsi = None
        self.atr = None

        self.sma = None
        self.ema = None

        self.bsawe = None
        self.pivotpoint = None

        super().__init__(strategy_trader, params)

        self.rsi_low = params['constants']['rsi_low']
        self.rsi_high = params['constants']['rsi_high']

        self.last_signal = None

    def process(self, timestamp: float) -> Union[StrategySignal, None]:
        candles = self.get_candles()

        if self.tf <= self.strategy_trader.min_traded_timeframe:
            return None

        if len(candles) < self.depth:
            # not enough samples
            return None

        last_timestamp = candles[-1].timestamp

        prices = self.price.compute(timestamp, candles)
        volumes = self.volume.compute(timestamp, candles)

        signal = self.compute(timestamp, last_timestamp, candles, prices, volumes)

        # avoid duplicates signals
        if signal and self.need_signal:
            # self.last_signal = signal
            if (self.last_signal and (signal.signal == self.last_signal.signal) and
                    (signal.dir == self.last_signal.dir) and
                    (signal.basetime() == self.last_signal.basetime())):  # or (signal.ts - self.last_signal.ts) < (self.tf * 0.5):
                # same base time avoid multiple entries on the same candle
                signal = None
            else:
                # retains the last valid signal only if valid
                self.last_signal = signal

        self.complete(candles, timestamp)

        return signal

    def compute(self, timestamp: float, last_timestamp: float, candles, prices, volumes) -> Union[StrategySignal, None]:
        signal = None

        # volume sma, increase signal strength when volume increase over its SMA
        # volume_sma = utils.MM_n(self.depth-1, self.volume.volumes)

        if self.rsi:
            self.rsi.compute(timestamp, prices)

        if self.pivotpoint:
            if self.pivotpoint.compute_at_close and self.last_closed:
                self.pivotpoint.compute(timestamp, self.price.open, self.price.high, self.price.low, self.price.close)

        if self.atr:
            if self.last_closed:
                self.atr.compute(timestamp, self.price.high, self.price.low, self.price.close)

        if self.tomdemark:
            if self.tomdemark.compute_at_close and self.last_closed:
                # last_timestamp
                self.tomdemark.compute(timestamp, self.price.timestamp, self.price.high, self.price.low, self.price.prices)

                # sell-setup
                if self.tomdemark.c.c == 9 and self.tomdemark.c.d < 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                # buy-setup
                elif self.tomdemark.c.c == 9 and self.tomdemark.c.d > 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = -1
                    signal.p = self.price.close[-1]

        if self.bsawe:
            if self.last_closed:
                # use OHLC4 as price in place of close
                bsawe = self.bsawe.compute(timestamp, self.price.high, self.price.low, self.price.prices)

                if bsawe > 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                    if self.tomdemark.c.tdst:
                        signal.sl = self.tomdemark.c.tdst

                    if len(self.pivotpoint.resistances[2]):
                        signal.tp = np.max(self.pivotpoint.resistances[2])

                elif bsawe < 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = -1
                    signal.p = self.price.close[-1]

                    if self.tomdemark.c.tdst:
                        signal.sl = self.tomdemark.c.tdst

                    if len(self.pivotpoint.supports[2]):
                        signal.tp = np.min(self.pivotpoint.supports[2])

        return signal

    def setup_streamer(self, streamer):
        streamer.add_member(StreamMemberSerie('begin'))
        
        streamer.add_member(StreamMemberOhlcSerie('ohlc'))
        streamer.add_member(StreamMemberFloatSerie('price', 0))
        streamer.add_member(StreamMemberFloatBarSerie('volume', 1))

        streamer.add_member(StreamMemberFloatSerie('rsi-low', 2))
        streamer.add_member(StreamMemberFloatSerie('rsi-high', 2))
        streamer.add_member(StreamMemberFloatSerie('rsi', 2))

        # bollinger, triangle, pivotpoint, td9, fibonacci...

        streamer.add_member(StreamMemberSerie('end'))

        streamer.last_timestamp = self.last_timestamp

    def stream(self, streamer):
        delta = min(int((self.last_timestamp - streamer.last_timestamp) / self.tf) + 1, len(self.price.prices))

        for i in range(-delta, 0, 1):
            ts = self.price.timestamp[i]

            streamer.member('begin').update(ts)

            streamer.member('ohlc').update((self.price.open[i], self.price.high[i], self.price.low[i], self.price.close[i]), ts)

            streamer.member('price').update(self.price.prices[i], ts)
            streamer.member('volume').update(self.volume.volumes[i], ts)

            streamer.member('rsi-low').update(self.rsi_low, ts)
            streamer.member('rsi-high').update(self.rsi_high, ts)
            streamer.member('rsi').update(self.rsi.rsis[i], ts)

            # streamer.member('stochrsi-low').update(20, ts)
            # streamer.member('stochrsi-high').update(80, ts)
            # streamer.member('stochrsi-k').update(self.stochrsi.stochrsis[i], ts)
            # streamer.member('stochrsi-d').update(self.stochrsi.stochrsis[i], ts)

            streamer.member('end').update(ts)

            # publish per frame
            streamer.publish()

        streamer.last_timestamp = self.last_timestamp
