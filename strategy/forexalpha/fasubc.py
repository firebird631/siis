# @date 2019-02-16
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Forex Alpha strategy, sub-strategy B.

from strategy.indicator import utils
from strategy.strategysignal import StrategySignal
from monitor.streamable import StreamMemberFloatSerie, StreamMemberSerie, StreamMemberFloatBarSerie, StreamMemberOhlcSerie

from terminal.terminal import Terminal

from .fasub import ForexAlphaStrategySub

import logging
logger = logging.getLogger('siis.strategy.forexalpha')


class ForexAlphaStrategySubC(ForexAlphaStrategySub):
    """
    Forex Alpha strategy, sub-strategy C.
    """

    def __init__(self, strategy_trader, params):
        super().__init__(strategy_trader, params)

        if 'scores' in params:
            # for older method
            self.rsi_score_factor = params['scores']['rsi_factor']
            self.rsi_trend_score_factor = params['scores']['rsi_trend_factor']
            self.sma_ema_cross_score_factor = params['scores']['sma_ema_cross_factor']
            self.ema_vwma_cross_score_factor = params['scores']['ema_vwma_cross_factor']
            self.price_vwma_cross_score_factor = params['scores']['price_vwma_factor']
            self.ema_vwma_score_bonus = params['scores']['ema_vwma_cross_bonus']
            self.rsi_ema_trend_div_score_factor = params['scores']['rsi_ema_trend_div_factor']
        
        self.rsi_low = params['constants']['rsi_low']
        self.rsi_high = params['constants']['rsi_high']

    def process(self, timestamp):
        candles = self.get_candles()

        if len(candles) < self.depth:
            # not enought samples
            return

        to_ts = candles[-1].timestamp

        prices = self.price.compute(to_ts, candles)[-self.depth:]
        volumes = self.volume.compute(to_ts, candles)[-self.depth:]

        signal = self.process1(timestamp, to_ts, candles, prices, volumes)

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

        self.complete(candles)

        return signal

    def process1(self, timestamp, to_ts, candles, prices, volumes):
        signal = None

        # volume sma, increase signal strength when volume increase over its SMA
        # volume_sma = utils.MM_n(self.depth-1, self.volume.volumes)

        rsi = 0
        rsi_30_70 = 0  # 1 <30, -1 >70
        rsi_40_60 = 0  # 1 if RSI in 40-60

        stochrsi = 0
        stochrsi_20_80 = 0  # 1 <20, -1 >80
        stochrsi_40_60 = 0  # 1 if stochRSI in 40-60
        
        volume_signal = 0
        
        ema_sma_cross = 0
        ema_sma_height = 0

        if self.rsi:
            self.rsi.compute(to_ts, prices)[-1]

            if self.rsi.last < self.rsi_low:
                rsi_30_70 = 1.0
            elif self.rsi.last > self.rsi_high:
                rsi_30_70 = -1.0

            if self.rsi.last > 0.4 and self.rsi.last < 0.6:
                rsi_40_60 = 1

        if self.stochrsi:
            stochrsi = self.stochrsi.compute(to_ts, prices)[0][-1]

            if stochrsi < 0.2:
                stochrsi_20_80 = 1.0
            elif stochrsi > 0.8:
                stochrsi_20_80 = -1.0

            if stochrsi > 0.4 and stochrsi < 0.6:
                stochrsi_40_60 = 1

        # if self.volume.last > volume_sma[-1]:
        #     volume_signal = 1
        # elif self.volume.last < volume_sma[-1]:
        #     volume_signal = -1

        if self.sma and self.ema:
            sma = self.sma.compute(to_ts, prices)[-2:]
            ema = self.ema.compute(to_ts, prices)[-2:]

            # ema over sma crossing
            ema_sma_cross = utils.cross((ema[-2], sma[-2]), (ema[-1], sma[-1]))

            if ema[-1] > sma[-1]:
                ema_sma_height = 1
            elif ema[-1] < sma[-1]:
                ema_sma_height = -1

        if self.atr:
            self.atr.compute(to_ts, self.price.high, self.price.low, self.price.close)

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

        # stochastic, bollinger, triangle, score, pivotpoint, td9, fibonacci...

        streamer.add_member(StreamMemberSerie('end'))

        streamer.next_timestamp = self.next_timestamp

    def stream(self, streamer):
        delta = min(int((self.next_timestamp - streamer.next_timestamp) / self.tf) + 1, len(self.price.prices))

        for i in range(-delta, 0, 1):
            ts = self.price.timestamp[i]

            streamer.member('begin').update(ts)

            streamer.member('ohlc').update((float(self.price.open[i]),
                    float(self.price.high[i]), float(self.price.low[i]), float(self.price.close[i])), ts)

            streamer.member('price').update(float(self.price.prices[i]), ts)
            streamer.member('volume').update(float(self.volume.volumes[i]), ts)

            streamer.member('rsi-low').update(self.rsi_low, ts)
            streamer.member('rsi-high').update(self.rsi_high, ts)
            streamer.member('rsi').update(float(self.rsi.rsis[i]), ts)

            # streamer.member('stochrsi-low').update(20, ts)
            # streamer.member('stochrsi-high').update(80, ts)
            # streamer.member('stochrsi-k').update(float(self.stochrsi.stochrsis[i]), ts)
            # streamer.member('stochrsi-d').update(float(self.stochrsi.stochrsis[i]), ts)

            streamer.member('sma').update(float(self.sma.smas[i]), ts)
            streamer.member('ema').update(float(self.ema.emas[i]), ts)
            # streamer.member('hma').update(float(self.hma.hmas[i]), ts)
            # streamer.member('vwma').update(float(self.vwma.vwmas[i]), ts)

            streamer.member('perf').update(self.strategy_trader._stats['perf']*100, ts)

            streamer.member('end').update(ts)

            # push per frame
            streamer.push()

        streamer.next_timestamp = self.next_timestamp
