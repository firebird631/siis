# @date 2018-08-24
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


class ForexAlphaStrategySubB(ForexAlphaStrategySub):
    """
    Forex Alpha strategy, sub-strategy B.
    """

    def __init__(self, data, params):
        super().__init__(data, params)

        if 'scores' in params:
            # for older method
            self.rsi_score_factor = params['scores']['rsi_factor']
            self.rsi_trend_score_factor = params['scores']['rsi_trend_factor']
            self.ema_vwma_cross_score_factor = params['scores']['ema_vwma_cross_factor']
            self.price_vwma_cross_score_factor = params['scores']['price_vwma_factor']
            self.hma_sma_cross_score_factor = params['scores']['hma_sma_cross_factor']
            self.hma_vwma_cross_score_factor = params['scores']['hma_vwma_cross_factor']
            self.ema_vwma_score_bonus = params['scores']['ema_vwma_cross_bonus']
            self.rsi_hma_trend_div_score_factor = params['scores']['rsi_hma_trend_div_factor']
        
        self.rsi_low = params['constants']['rsi_low']
        self.rsi_high = params['constants']['rsi_high']      

    def process(self, timestamp):
        # candles = self.data.instrument.last_candles(self.tf, self.depth)
        candles = self.data.instrument.candles_from(self.tf, self.next_timestamp - self.depth*self.tf)

        if len(candles) < self.depth:
            # not enought samples
            return

        last_timestamp = candles[-1].timestamp

        prices = self.price.compute(last_timestamp, candles)
        volumes = self.volume.compute(last_timestamp, candles)

        signal = self.process1(timestamp, last_timestamp, candles, prices, volumes)

        if candles:
            # last processed candle timestamp (from last candle is non consolidated else from the next one)
            self.next_timestamp = candles[-1].timestamp if not candles[-1].ended else candles[-1].timestamp + self.tf

        # avoid duplicates signals
        if signal:
            # self.last_signal = signal
            if (self.last_signal and (signal.signal == self.last_signal.signal) and
                    (signal.dir == self.last_signal.dir) and
                    (signal.base_time() == self.last_signal.base_time())):
                # same base time avoid multiple entries on the same candle
                signal = None
            else:
                # retains the last valid signal only if valid
                self.last_signal = signal
                
                if self.profiling:
                    # store signal data condition when profiling
                    signal.add_condition('price', self.price.trace())
                    # signal.add_condition('rsi', self.rsi.trace())
                    # signal.add_condition('sma', self.sma.trace())
                    # signal.add_condition('ema', self.ema.trace())
                    # signal.add_condition('stochrsi', self.stochrsi.trace())
                    # signal.add_condition('tomdemark', self.tomdemark.trace())
                    # signal.add_condition('bbawe', self.bbawe.trace())
                    # signal.add_condition('bollinger', self.bollingerbands.trade())

        return signal

    def process1(self, timestamp, last_timestamp, candles, prices, volumes):
        signal = None

        # volume sma, increase signal strength when volume increase over its SMA
        # volume_sma = utils.MM_n(self.depth-1, self.volume.volumes)

        #
        # signals analysis
        #

        rsi_30_70 = 0  # -1 30, 1 70
        rsi_40_60 = 0  # 1 if RSI in 40-60
        volume_signal = 0
        ema_sma_cross = 0
        ema_sma_height = 0

        if self.rsi:
            self.rsi.compute(last_timestamp, prices)

            if self.rsi.last < self.rsi_low:
                rsi_30_70 = 1.0
            elif self.rsi.last > self.rsi_high:
                rsi_30_70 = -1.0

            if self.rsi.last > 0.4 and self.rsi.last < 0.6:
                rsi_40_60 = 1

        # if self.volume.last > volume_sma[-1]:
        #     volume_signal = 1
        # elif self.volume.last < volume_sma[-1]:
        #     volume_signal = -1

        if self.sma and self.ema:
            self.sma.compute(last_timestamp, prices)
            self.ema.compute(last_timestamp, prices)

            # ema over sma crossing
            ema_sma_cross = utils.cross((self.ema.prev, self.sma.prev), (self.ema.last, self.sma.last))

            if self.ema.last > self.sma.last:
                ema_sma_height = 1
            elif self.ema.last < self.sma.last:
                ema_sma_height = -1

        if ema_sma_cross > 0 and rsi_30_70 > 0:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_ENTRY
            signal.dir = 1
            signal.p = candles[-1].close

        elif ema_sma_cross < 0 and rsi_30_70 < 0:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_EXIT
            signal.dir = 1
            signal.p = candles[-1].close

        # TD9 on 1m are not very pertinant on crypto
        # if self.tomdemark:
        #     self.tomdemark.compute(last_timestamp, candles)

        return signal

    # def process_old(self, timestamp):
    #   # candles = self.data.instrument.last_candles(self.tf, self.depth)
    #   candles = self.data.instrument.candles_from(self.tf, self.next_timestamp - self.depth*self.tf)[-self.depth:]

    #   if len(candles) < self.depth:
    #       # not enought samples
    #       return

    #   to_ts = candles[-1].timestamp

    #   prices = self.price.compute(to_ts, candles)[-self.depth:]
    #   volumes = self.volume.compute(to_ts, candles)[-self.depth:]

    #   #
    #   # signals analysis
    #   #

    #   rsi = self.rsi.compute(to_ts, prices)[-self.depth:]
    #   sma = self.sma.compute(to_ts, prices)[-self.depth:]
    #   ema = self.ema.compute(to_ts, prices)[-self.depth:]
    #   vwma = self.vwma.compute(to_ts, prices, volumes)[-self.depth:]
    #   hma = self.hma.compute(to_ts, prices)[-self.depth:]
    #   mmt = [] # self.mmt.compute(to_ts, prices)[-self.depth:]
    #   macd = [] # self.macd.compute(to_ts, prices)[-self.depth:]
    #   stochastic = [] # self.stochastic.compute(to_ts, prices)[-self.depth:]

    #   self.tomdemark.compute(to_ts, candles)

    #   #
    #   # analysis of the results and scorify
    #   #

    #   if len(rsi):
    #       # trend of the rsi
    #       rsi_trend = utils.trend_extremum(rsi)

    #       # 30/70 @todo use Comparator, cross + strength by distance
    #       if rsi[-1] < self.rsi_low:
    #           rsi_score = (self.rsi_low-rsi[-1])  # ++
    #       elif rsi[-1] > self.rsi_high:
    #           rsi_score = (self.rsi_high-rsi[-1])
    #       else:
    #           rsi_score = 0

    #       self.score.add(rsi_score*100, self.rsi_score_factor)

    #       # if trend > 0.33 score it else ignore
    #       #if abs(rsi_trend) > 0.33:
    #       self.score.add(rsi_trend, self.rsi_trend_score_factor)

    #   # ema/vwma distance and crossing
    #   if len(ema) and len(vwma):
    #       # ema-vwma normalized distance
    #       ema_vwma_score = (ema[-1]-vwma[-1]) / prices[-1]
    #       self.score.add(ema_vwma_score, self.ema_vwma_cross_score_factor)

    #       # @todo ema cros vwma using Comparator
    #       # ema_vwma_cross_score = (hma[-1]-sma[-1]) / prices[-1]
    #       # self.score.add(ema_vwma_cross_score, self.ema_vwma_cross_score_factor)
    #       # utils.cross((ema[-1] > vwma[-1]), ())

    #       # ema-vwma + price-vwma give a bonus (@todo is it usefull ?)
    #       if ema[-1] > vwma[-1] and prices[-1] > vwma[-1]:
    #           self.score.add(1, self.ema_vwma_score_bonus)
    #       elif ema[-1] < vwma[-1] and prices[-1] < vwma[-1]:
    #           self.score.add(-1, self.ema_vwma_score_bonus)

    #   # vwma/price distance and crossing
    #   if len(vwma):
    #       # price-vwma normalized distance
    #       price_vwma_score = (prices[-1]-vwma[-1]) / prices[-1]
    #       self.score.add(price_vwma_score, self.price_vwma_cross_score_factor)

    #   # sma/hma distance and crossing
    #   if len(sma) and len(hma):
    #       hma_sma_score = (hma[-1]-sma[-1]) / prices[-1]
    #       self.score.add(hma_sma_score, self.hma_sma_cross_score_factor)

    #   # hma/vwma distance and crossing
    #   if len(hma) and len(vwma):
    #       hma_vwma_score = (hma[-1]-vwma[-1]) / prices[-1]
    #       self.score.add(hma_vwma_score, self.hma_vwma_cross_score_factor)

    #   # hma trend is a fast signal
    #   if len(hma):
    #       # hma trend @todo
    #       hma_trend = utils.trend_extremum(hma)
    #       # self.score.add(hma_trend, self.hma_trend_factor)

    #   # rsi trend and hma divergence
    #   if utils.divergence(rsi_trend, hma_trend):
    #       rsi_hma_div = True
    #       # self.score.add(rsi_trend + hma_trend, -self.rsi_hma_trend_div_score_factor)
    #       # self.score.add(rsi_trend-hma_trend, -self.rsi_hma_trend_div_score_factor)
    #       self.score.add(abs(rsi_trend-hma_trend), self.rsi_hma_trend_div_score_factor)
    #       # self.score.scale(0.2)  # score is weaken (good result)
    #   else:
    #       # self.score.add(rsi_trend + hma_trend, self.rsi_hma_trend_div_score_factor)
    #       rsi_hma_div = False

    #   # volume sma, increase signal strength when volume increase over its SMA
    #   volume_sma = utils.MM_n(self.depth-1, self.volume.volumes)

    #   if self.volume.last > volume_sma[-1]:
    #       self.score.scale(2.0)

    #   self.score.finalize()

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

            streamer.member('perf').update(self.data._stats['perf']*100, ts)

            streamer.member('end').update(ts)

            # push per frame
            streamer.push()

        streamer.next_timestamp = self.next_timestamp
