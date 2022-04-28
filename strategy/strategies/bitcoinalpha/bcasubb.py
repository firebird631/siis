# @date 2019-01-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Bitcoin Alpha strategy, sub-strategy B.

from strategy.indicator import utils
from strategy.strategysignal import StrategySignal
from monitor.streamable import StreamMemberFloatSerie, StreamMemberSerie, StreamMemberFloatBarSerie, \
    StreamMemberOhlcSerie

from .bcasub import BitcoinAlphaStrategySub

import logging
logger = logging.getLogger('siis.strategy.bitcoinalpha')


class BitcoinAlphaStrategySubB(BitcoinAlphaStrategySub):
    """
    Bitcoin Alpha strategy, sub-strategy B.
    """

    def __init__(self, strategy_trader, params):
        super().__init__(strategy_trader, params)

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
        candles = self.get_candles()

        if len(candles) < self.depth:
            # not enough samples
            return

        prices = self.price.compute(timestamp, candles)
        volumes = self.volume.compute(timestamp, candles)

        signal = self.process1(timestamp, self.last_timestamp, candles, prices, volumes)

        # avoid duplicates signals
        if signal and self.need_signal:
            # self.last_signal = signal
            if (self.last_signal and (signal.signal == self.last_signal.signal) and
                    (signal.dir == self.last_signal.dir) and
                    (signal.basetime() == self.last_signal.basetime())):
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

        #
        # signals analysis
        #

        rsi_30_70 = 0  # -1 30, 1 70
        rsi_40_60 = 0  # 1 if RSI in 40-60
        volume_signal = 0
        ema_sma_cross = 0
        ema_sma_height = 0

        if self.rsi:
            self.rsi.compute(timestamp, prices)

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

        if self.sma200:
            self.sma200.compute(timestamp, prices)

        if self.sma55:
            self.sma55.compute(timestamp, prices)

        if self.sma and self.ema:
            self.sma.compute(timestamp, prices)
            self.ema.compute(timestamp, prices)

            # ema over sma crossing
            ema_sma_cross = utils.cross((self.ema.prev, self.sma.prev), (self.ema.last, self.sma.last))

            if self.ema.last > self.sma.last:
                ema_sma_height = 1
            elif self.ema.last < self.sma.last:
                ema_sma_height = -1

        bb_way = 0

        if self.bollingerbands:
            self.bollingerbands.compute(timestamp, prices)

            if self.bollingerbands.last_ma < prices[-1] < self.bollingerbands.last_top:
                bb_way = -1

        if self.mama:
            self.mama.compute(timestamp, self.price.close)

        # if ema_sma_cross > 0 and rsi_30_70 > 0:
        #     self.trend = 1

        # elif ema_sma_cross < 0 and rsi_30_70 < 0:
        #     signal = StrategySignal(self.tf, timestamp)
        #     signal.signal = StrategySignal.SIGNAL_EXIT
        #     signal.dir = 1
        #     signal.p = candles[-1].close
        #     self.trend = -1
        # else:
        #     self.trend = 0

        ema_sma = 0

        # if self.ema.last < self.sma.last:
        #     # bear trend
        #     if self.rsi.last > 0.5:  # initial: 0.5
        #         ema_sma = -1
        #     elif self.rsi.last < 0.2:  # initial: 0.2
        #         ema_sma = 1
        # else:
        #     # bull trend
        #     if self.rsi.last > 0.8:  # initial: 0.8
        #         ema_sma = -1
        #     elif self.rsi.last < 0.6:  # initial: 0.6
        #         ema_sma = 1            

        if ema_sma < 0:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_EXIT
            signal.dir = 1
            signal.p = candles[-1].close

            self.trend = -1

        elif ema_sma > 0:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_EXIT
            signal.dir = -1
            signal.p = candles[-1].close

            self.trend = 1
        else:
            self.trend = 0

        if self.mama:
            cross = self.mama.cross()
            # logger.info("mama cross %s %s %s" % (self.mama.last_fama, self.mama.last_mama, self.mama.trend()))

            if cross > 0:
                self.mama_cross = (1, timestamp, self.price.close[-1])
            elif cross < 0:
                self.mama_cross = (-1, timestamp, self.price.close[-1])

            # or we can try an entry on cross signal
            # @todo

            self.trend = self.mama.trend()

        # can long on upward trend, on dip or on lower of bollinger if range
        # @todo detect dip, bollinger range (flat mama + first bounces)

        self.can_long = self.trend >= 0
        self.can_short = self.trend <= 0

        if self.pivotpoint:
            if self.pivotpoint.compute_at_close and self.last_closed:
                self.pivotpoint.compute(timestamp, self.price.open, self.price.high, self.price.low, self.price.close)

        if self.atr:
            if self.last_closed:
                self.atr.compute(timestamp, self.price.high, self.price.low, self.price.close)

        if self.tomdemark:
            if self.tomdemark.compute_at_close and self.last_closed:
                self.tomdemark.compute(timestamp, self.price.timestamp, self.price.high, self.price.low, self.price.close)

                if self.tomdemark.c.c == 9 and self.tomdemark.c.d < 0:
                    # setup complete and trend change
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                elif self.tomdemark.c.c == 9 and self.tomdemark.c.d > 0:
                    # setup complete and trend change
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = -1
                    signal.p = self.price.close[-1]

                elif 3 <= self.tomdemark.c.c <= 5 and self.tomdemark.c.d > 0:  # and (ema_sma < 0):
                    # cancellation
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                elif 3 <= self.tomdemark.c.c <= 5 and self.tomdemark.c.d < 0:  # and (ema_sma > 0):
                    # cancellation
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

        streamer.add_member(StreamMemberFloatSerie('sma', 0))
        streamer.add_member(StreamMemberFloatSerie('ema', 0))
        streamer.add_member(StreamMemberFloatSerie('hma', 0))
        streamer.add_member(StreamMemberFloatSerie('vwma', 0))
        # streamer.add_member(StreamMemberFloatSerie('mmt', 0))
        # bollinger, pivotpoint, td9, fibonacci,

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

            streamer.member('end').update(ts)

            # publish per frame
            streamer.publish()

        streamer.last_timestamp = self.last_timestamp
