# @date 2019-01-19
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Crystal Bal strategy, sub-strategy A.

import numpy as np

from terminal.terminal import Terminal

from strategy.indicator import utils
from strategy.strategysignal import StrategySignal
from monitor.streamable import StreamMemberFloatSerie, StreamMemberSerie, StreamMemberFloatBarSerie, StreamMemberOhlcSerie

from .cbsub import CrystalBallStrategySub

import logging
logger = logging.getLogger('siis.strategy.crystalball')


class CrystalBallStrategySubA(CrystalBallStrategySub):
    """
    Crystal Ball strategy, sub-strategy A.
    """

    def __init__(self, strategy_trader, params):
        super().__init__(strategy_trader, params)

        self.rsi_low = params['constants']['rsi_low']
        self.rsi_high = params['constants']['rsi_high']

        self.last_signal = None

    def process(self, timestamp):
        # candles = self.strategy_trader.instrument.last_candles(self.tf, self.depth)
        candles = self.strategy_trader.instrument.candles_from(self.tf, self.next_timestamp - self.depth*self.tf)

        if self.tf <= self.strategy_trader.min_traded_timeframe:
            return

        if len(candles) < self.depth:
            # not enought samples
            return

        last_timestamp = candles[-1].timestamp

        prices = self.price.compute(last_timestamp, candles)
        volumes = self.volume.compute(last_timestamp, candles)

        signal = self.compute(timestamp, last_timestamp, candles, prices, volumes)

        if candles:
            # last processed candle timestamp (from last candle if non consolidated else from the next one)
            self.next_timestamp = candles[-1].timestamp if not candles[-1].ended else candles[-1].timestamp + self.tf

        # avoid duplicates signals
        if signal and self.need_signal:
            # self.last_signal = signal
            if (self.last_signal and (signal.signal == self.last_signal.signal) and
                    (signal.dir == self.last_signal.dir) and
                    (signal.base_time() == self.last_signal.base_time())):  # or (signal.ts - self.last_signal.ts) < (self.tf * 0.5):
                # same base time avoid multiple entries on the same candle
                signal = None
            else:
                # retains the last valid signal only if valid
                self.last_signal = signal

        return signal

    def compute(self, timestamp, last_timestamp, candles, prices, volumes):
        signal = None

        # volume sma, increase signal strength when volume increase over its SMA
        # volume_sma = utils.MM_n(self.depth-1, self.volume.volumes)

        if self.rsi:
            self.rsi.compute(last_timestamp, prices)

        # if self.volume_ema:
        #     self.volume_ema.compute(last_timestamp, volumes)

        #     if self.volume.last > self.volume_ema.last:
        #         volume_signal = 1
        #     elif self.volume.last < self.volume_ema.last:
        #         volume_signal = -1

        if self.pivotpoint:
            self.pivotpoint.compute(last_timestamp, self.price.open, self.price.high, self.price.low, self.price.close)

        # if self.bollingerbands:
        #     self.bollingerbands.compute(last_timestamp, prices)

        #     bb_break = 0
        #     bb_ma = 0

        #     if prices[-1] > self.bollingerbands.last_top:
        #         bb_break = 1
        #     elif prices[-1] < self.bollingerbands.last_bottom:
        #         bb_break = -1

        #     if prices[-1] > self.bollingerbands.last_ma:
        #         bb_ma = -1
        #     elif prices[-1] > self.bollingerbands.last_ma:
        #         bb_ma = 1

        if self.atr:
            self.atr.compute(last_timestamp, self.price.high, self.price.low, self.price.close)

        if self.bbawe:
            # use OHLC4 as price in place of close
            bbawe = self.bbawe.compute(last_timestamp, self.price.high, self.price.low, self.price.prices)

        if self.tomdemark:
            self.tomdemark.compute(last_timestamp, self.price.timestamp, self.price.high, self.price.low, self.price.prices)

        level1_signal = 0

        if bbawe > 0:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_ENTRY
            signal.dir = 1
            signal.p = self.price.close[-1]

            if self.tomdemark.c.tdst:
                signal.sl = self.tomdemark.c.tdst

            if len(self.pivotpoint.resistances[2]):
                signal.tp = np.max(self.pivotpoint.resistances[2])

        elif bbawe < 0:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_ENTRY
            signal.dir = -1
            signal.p = self.price.close[-1]

            if self.tomdemark.c.tdst:
                signal.sl = self.tomdemark.c.tdst

            if len(self.pivotpoint.supports[2]):
                signal.tp = np.min(self.pivotpoint.supports[2])

        #
        # setup completed
        #

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

        return signal

    def setup_streamer(self, streamer):
        streamer.add_member(StreamMemberSerie('begin'))
        
        streamer.add_member(StreamMemberOhlcSerie('ohlc'))
        streamer.add_member(StreamMemberFloatSerie('price', 0))
        streamer.add_member(StreamMemberFloatBarSerie('volume', 1))

        streamer.add_member(StreamMemberFloatSerie('rsi-low', 2))
        streamer.add_member(StreamMemberFloatSerie('rsi-high', 2))
        streamer.add_member(StreamMemberFloatSerie('rsi', 2))

        streamer.add_member(StreamMemberFloatSerie('perf', 3))

        # bollinger, triangle, pivotpoint, td9, fibonacci...

        streamer.add_member(StreamMemberSerie('end'))

        streamer.next_timestamp = self.next_timestamp

    def stream(self, streamer):
        delta = min(int((self.next_timestamp - streamer.next_timestamp) / self.tf) + 1, len(self.price.prices))

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

            streamer.member('perf').update(self.strategy_trader._stats['perf']*100, ts)

            streamer.member('end').update(ts)

            # push per frame
            streamer.push()

        streamer.next_timestamp = self.next_timestamp
