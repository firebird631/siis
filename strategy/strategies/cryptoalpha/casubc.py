# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy, sub-strategy B.

from strategy.indicator import utils
from strategy.strategysignal import StrategySignal
from monitor.streamable import StreamMemberFloatSerie, StreamMemberSerie, StreamMemberFloatBarSerie, StreamMemberOhlcSerie

from .casub import CryptoAlphaStrategySub

import logging
logger = logging.getLogger('siis.strategy.cryptoalpha')


class CryptoAlphaStrategySubC(CryptoAlphaStrategySub):
    """
    Crypto Alpha strategy, sub-strategy C.
    """

    def __init__(self, strategy_trader, params):
        super().__init__(strategy_trader, params)

        self.rsi_low = params['constants']['rsi_low']
        self.rsi_high = params['constants']['rsi_high']

    def process(self, timestamp):
        candles = self.get_candles()

        if len(candles) < self.depth:
            # not enought samples
            return

        prices = self.price.compute(timestamp, candles)
        volumes = self.volume.compute(timestamp, candles)

        signal = self.process1(timestamp, self.last_timestamp, candles, prices, volumes)

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

    def process1(self, timestamp, last_timestamp, candles, prices, volumes):
        signal = None

        # volume sma, increase signal strength when volume increase over its SMA
        # volume_sma = utils.MM_n(self.depth-1, self.volume.volumes)

        rsi_30_70 = 0  # 1 <30, -1 >70
        rsi_40_60 = 0  # 1 if RSI in 40-60

        stochrsi_20_80 = 0  # 1 <20, -1 >80
        stochrsi_40_60 = 0  # 1 if stochRSI in 40-60
        
        volume_signal = 0
        
        ema_sma_cross = 0
        ema_sma_height = 0

        if self.rsi:
            self.rsi.compute(timestamp, prices)
            rsi = self.rsi.last

            if self.rsi.last < self.rsi_low:
                rsi_30_70 = 1.0
            elif self.rsi.last > self.rsi_high:
                rsi_30_70 = -1.0

            if self.rsi.last > 0.4 and self.rsi.last < 0.6:
                rsi_40_60 = 1

        if self.stochrsi:
            self.stochrsi.compute(timestamp, prices)

            if self.stochrsi.last_k < 0.2:
                stochrsi_20_80 = 1.0
            elif self.stochrsi.last_k > 0.8:
                stochrsi_20_80 = -1.0

            if self.stochrsi.last_k > 0.4 and self.stochrsi.last_k < 0.6:
                stochrsi_40_60 = 1

        # if self.volume.last > volume_sma[-1]:
        #     volume_signal = 1
        # elif self.volume.last < volume_sma[-1]:
        #     volume_signal = -1

        if self.sma and self.ema:
            self.sma.compute(timestamp, prices)
            self.ema.compute(timestamp, prices)

            # ema over sma crossing
            ema_sma_cross = utils.cross((self.ema.prev, self.sma.prev), (self.ema.last, self.sma.last))

            if self.ema.last > self.sma.last:
                ema_sma_height = 1
            elif self.ema.last < self.sma.last:
                ema_sma_height = -1

        if self.atr:
            if self.last_closed:
                self.atr.compute(timestamp, self.price.high, self.price.low, self.price.close)

        if self.pivotpoint:
            if self.pivotpoint.compute_at_close and self.last_closed:
                self.pivotpoint.compute(timestamp, self.price.open, self.price.high, self.price.low, self.price.close)            

        return signal

    def setup_streamer(self, streamer):
        streamer.add_member(StreamMemberSerie('begin'))
        
        streamer.add_member(StreamMemberOhlcSerie('ohlc'))
        streamer.add_member(StreamMemberFloatSerie('price', 0))
        streamer.add_member(StreamMemberFloatBarSerie('volume', 1))

        streamer.add_member(StreamMemberFloatSerie('rsi-low', 2))
        streamer.add_member(StreamMemberFloatSerie('rsi-high', 2))
        streamer.add_member(StreamMemberFloatSerie('rsi', 2))

        streamer.add_member(StreamMemberFloatSerie('stochrsi-low', 3))
        streamer.add_member(StreamMemberFloatSerie('stochrsi-high', 3))
        streamer.add_member(StreamMemberFloatSerie('stochrsi-k', 3))
        streamer.add_member(StreamMemberFloatSerie('stochrsi-d', 3))

        streamer.add_member(StreamMemberFloatSerie('sma', 0))
        streamer.add_member(StreamMemberFloatSerie('ema', 0))
        streamer.add_member(StreamMemberFloatSerie('hma', 0))
        streamer.add_member(StreamMemberFloatSerie('vwma', 0))

        streamer.add_member(StreamMemberFloatSerie('perf', 3))

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

            streamer.member('sma').update(self.sma.smas[i], ts)
            streamer.member('ema').update(self.ema.emas[i], ts)
            # streamer.member('hma').update(self.hma.hmas[i], ts)
            # streamer.member('vwma').update(self.vwma.vwmas[i], ts)

            streamer.member('perf').update(self.strategy_trader._stats['perf']*100, ts)

            streamer.member('end').update(ts)

            # publish per frame
            streamer.publish()

        streamer.last_timestamp = self.last_timestamp
