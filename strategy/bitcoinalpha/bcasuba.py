# @date 2019-01-19
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Bitcoin Alpha strategy, sub-strategy A.

import numpy as np

from terminal.terminal import Terminal

from strategy.indicator import utils
from strategy.strategysignal import StrategySignal
from monitor.streamable import StreamMemberFloatSerie, StreamMemberSerie, StreamMemberFloatBarSerie, StreamMemberOhlcSerie

from .bcasub import BitcoinAlphaStrategySub

import logging
logger = logging.getLogger('siis.strategy.cryptoalpha')


class BitcoinAlphaStrategySubA(BitcoinAlphaStrategySub):
    """
    Bitcoin Alpha strategy, sub-strategy A.
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

        last_timestamp = candles[-1].timestamp

        prices = self.price.compute(timestamp, candles)
        volumes = self.volume.compute(timestamp, candles)

        signal = self.process4(timestamp, last_timestamp, candles, prices, volumes)

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

        self.complete(candles)

        return signal

    def process1(self, timestamp, to_ts, candles, prices, volumes):
        signal = None

        # volume sma, increase signal strength when volume increase over its SMA
        volume_sma = utils.MM_n(self.depth-1, self.volume.volumes)

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

        signal = StrategySignal(self.tf, timestamp)

        if self.volume.last > volume_sma[-1]:
            volume_signal = 1
        elif self.volume.last < volume_sma[-1]:
            volume_signal = -1

        if self.sma and self.ema:
            sma = self.sma.compute(to_ts, prices)[-2:]
            ema = self.ema.compute(to_ts, prices)[-2:]

            # ema over sma crossing
            ema_sma_cross = utils.cross((ema[-2], sma[-2]), (ema[-1], sma[-1]))

            if ema[-1] > sma[-1]:
                ema_sma_height = 1
            elif ema[-1] < sma[-1]:
                ema_sma_height = -1

        if self.tomdemark:
            td = self.tomdemark.compute(to_ts, self.price.timestamp, self.price.high, self.price.low, self.price.close)[-1]

            #
            # setup entry
            #

            # long entry on sell-setup + rsi oversell
            if (td.c == 2 or td.c == 3) and td.d < 0 and candles[-1].close > candles[-2].close:
                # if rsi < 0.6: # (ema_sma_height > 0 and rsi_40_60 > 0):  # or rsi_30_70 < 0:  # 1
                if stochrsi_20_80 > 0 or rsi_30_70 > 0:
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = candles[-1].close
                    signal.sl = td.tdst or candles[-1].low - candles[-1].height

                    # 1.618 fibo
                    # signal.tp = (self.price.max - self.price.min) * 1.618 + self.price.close
                    #logger.info("> entry long %s c2-c3, c:%s p:%s sl:%s tp:%s" % (self.tf, td.c, signal.p, signal.sl, signal.tp))

            # short entry on buy-setup + rsi overbuy
            elif (td.c > 1 and td.c < 4) and td.d > 0 and candles[-1].close < candles[-2].close:
                if stochrsi_20_80 < 0 or rsi_30_70 < 0:
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = -1
                    signal.p = candles[-1].close
                    signal.sl = td.tdst or candles[-1].high + candles[-1].height

                    # 1.618 fibo
                    # signal.tp = self.price.close - (self.price.max - self.price.min) * 1.618
                    # logger.info("> entry short c2-c3, p:%s sl:%s tp:%s" % (signal.p, signal.sl, signal.tp))

            #
            # invalidation (3-7)
            #

            # elif td.c >= 3 and td.c <= 7:
            #     # if td.d > 0:  # and candles[-1].close < candles[-2].low:            
            #     if td.d < 0:  # and candles[-1].close < candles[-2].low:
            #         # short cancelation (excess of volume and ema under sma)
            #         pass

            #     # elif td.d < 0 and candles[-1].close < candles[-2].close:
            #     elif td.d > 0: # and candles[-1].close < candles[-2].close:
            #         # long cancelation (excess of volume and ema under sma)
            #         # if ema_sma_height < 0 or rsi_40_60 > 0:
            #         # if stochrsi_20_80 < 0:  # and volume_signal > 0:
            #         # if ema_sma_height < 0 and volume_signal > 0:
            #             # logger.info("> rsi_30_70 %s / rsi_40_60 %s / ema_sma_height %s / volume_signal %s" % (rsi_30_70, rsi_40_60, ema_sma_height, volume_signal))
            #             signal.signal = StrategySignal.SIGNAL_EXIT  # CANCEL
            #             signal.dir = 1
            #             signal.p = candles[-1].close
            #             logger.info("> canceled long entry c2-c3, p:%s" % (signal.p,))

            #
            # setup completed
            #

            elif (td.c == 8 and td.p) or td.c == 9:
                if td.d < 0:  # and candles[-1].close > candles[-2].close:
                    #if stochrsi_20_80 > 1:
                        signal.signal = StrategySignal.SIGNAL_EXIT
                        signal.dir = 1
                        signal.p = candles[-1].close
                        # logger.info("> Exit long %s c8p-c9 (%s%s)" % (self.tf, td.c, 'p' if signal.p else ''))

                elif td.d > 0:  # and candles[-1].close < candles[-2].close:
                    # if stochrsi_20_80 < 0:
                        signal.signal = StrategySignal.SIGNAL_EXIT
                        signal.dir = -1
                        signal.p = candles[-1].close
                        # logger.info("> Exit short %s c8p-c9 (%s%s)" % (self.tf, td.c, 'p' if signal.p else ''))

            #
            # CD entry
            #

            if td.cd >= 1 and td.cd <= 3:
                # count-down sell-setup + rsi oversell
                if td.cdd < 0:  # and candles[-1].close > candles[-2].high:
                # if rsi_30_70 > 0:
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = candles[-1].close
                    signal.sl = td.tdst

                    self.score.add(1.0, 1.0, 'td9-cd')
                    logger.info("> Entry long %s cd13, sl:%s" % (self.tf, signal.sl,))

                # count-down buy-setup + rsi overbuy
                elif td.cdd > 0:  # and candles[-1].close < candles[-2].low:
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = -1
                    signal.p = candles[-1].close
                    logger.info("> cancel entry long %s (sell ct13), p:%s" % (self.tf, signal.p,))

                    # # if rsi_30_70 < 0:
                    #     # signal.signal = StrategySignal.SIGNAL_ENTRY
                    #     # signal.dir = -1
                    #     # signal.p = candles[-1].close
                    #     # signal.sl = td.tdst

                    #     # self.score.add(-1.0, 1.0, 'td9-cd')
                    #     logger.info("> entry short cd13")
                    #     pass

            #
            # CD13 setup
            #

            elif td.cd == 13:
                logger.info(td.cd)
                # count-down sell-setup completed
                if td.cdd < 0:
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.p = candles[-1].close
                    signal.dir = 1

                    logger.info("> Exit long cd13")

                # count-down buy-setup completed
                elif td.cdd > 0:
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.p = candles[-1].close
                    signal.dir = -1

                    logger.info("> Exit short cd13")
                    pass

        return signal

    def process4(self, timestamp, last_timestamp, candles, prices, volumes):
        signal = None

        # volume sma, increase signal strength when volume increase over its SMA
        volume_sma = utils.MM_n(self.depth-1, self.volume.volumes)

        rsi_30_70 = 0  # 1 <30, -1 >70
        rsi_40_60 = 0  # 1 if RSI in 40-60
        rsi_trend = 0

        stochrsi_20_80 = 0  # 1 <20, -1 >80
        stochrsi_40_60 = 0  # 1 if stochRSI in 40-60
        
        volume_signal = 0
        
        ema_sma_cross = 0
        ema_sma_height = 0

        if self.tf == 4*60*60:
            self.sma200.compute(timestamp, prices)
            self.sma55.compute(timestamp, prices)

        if self.rsi:
            self.rsi.compute(timestamp, prices)

            if self.rsi.last < self.rsi_low:
                rsi_30_70 = 1.0
            elif self.rsi.last > self.rsi_high:
                rsi_30_70 = -1.0

            if self.rsi.last > 0.4 and self.rsi.last < 0.6:
                rsi_40_60 = 1

            rsi_trend = utils.trend_extremum(self.rsi.rsis)

        # if self.stochrsi:
        #     self.stochrsi.compute(timestamp, prices)

        #     if self.stochrsi.last_k < 0.2:
        #         stochrsi_20_80 = 1.0
        #     elif self.stochrsi.last_k > 0.8:
        #         stochrsi_20_80 = -1.0

        #     if self.stochrsi.last_k > 0.4 and self.stochrsi.last_k < 0.6:
        #         stochrsi_40_60 = 1

        # if self.volume_ema:
        #     self.volume_ema.compute(timestamp, volumes)

        #     if self.volume.last > self.volume_ema.last:
        #         volume_signal = 1
        #     elif self.volume.last < self.volume_ema.last:
        #         volume_signal = -1

        if self.sma and self.ema:
            self.sma.compute(timestamp, prices)
            self.ema.compute(timestamp, prices)

            # ema over sma crossing
            ema_sma_cross = utils.cross((self.ema.prev, self.sma.prev), (self.ema.last, self.sma.last))

            if self.ema.last > self.sma.last:
                ema_sma_height = 1
            elif self.ema.last < self.sma.last:
                ema_sma_height = -1

        if self.bollingerbands:
            self.bollingerbands.compute(timestamp, prices)

            bb_break = 0
            bb_ma = 0

            if prices[-1] > self.bollingerbands.last_top:
                bb_break = 1
            elif prices[-1] < self.bollingerbands.last_bottom:
                bb_break = -1

        #     if prices[-1] > self.bollingerbands.last_ma:
        #         bb_ma = -1
        #     elif prices[-1] > self.bollingerbands.last_ma:
        #         bb_ma = 1

        if self.bsawe:
            bsawe = self.bsawe.compute(timestamp, self.price.high, self.price.low, self.price.close)

        if self.atr:
            self.atr.compute(timestamp, self.price.high, self.price.low, self.price.close)

        level1_signal = 0

        if self.ema.last < self.sma.last:
            # bear trend
            if self.rsi.last > 0.5:  # initial: 0.5
                level1_signal = -1
            elif self.rsi.last < 0.2:  # initial: 0.2
                level1_signal = 1
        else:
            # bull trend
            if self.rsi.last > 0.8:  # initial: 0.8
                level1_signal = -1
            elif self.rsi.last < 0.6:  # initial: 0.6
                level1_signal = 1

        if bsawe > 0:# and level1_signal > 0:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_ENTRY
            signal.dir = 1
            signal.p = self.price.close[-1]

            # if self.tomdemark.c.tdst:
            #     signal.sl = self.tomdemark.c.tdst

        elif bsawe < 0:# and level1_signal < 0:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_ENTRY
            signal.dir = -1
            signal.p = self.price.close[-1]

            # if self.tomdemark.c.tdst:
            #     signal.sl = self.tomdemark.c.tdst

        if self.tomdemark:
            self.tomdemark.compute(timestamp, self.price.timestamp, self.price.high, self.price.low, self.price.close)

            #
            # setup completed
            #

            # sell-setup
            # if self.tomdemark.c.c == 9 and self.tomdemark.c.d < 0:
            #     signal = StrategySignal(self.tf, timestamp)
            #     signal.signal = StrategySignal.SIGNAL_EXIT
            #     signal.dir = 1
            #     signal.p = self.price.close[-1]

            # # buy-setup
            # elif self.tomdemark.c.c == 9 and self.tomdemark.c.d > 0:
            #     signal = StrategySignal(self.tf, timestamp)
            #     signal.signal = StrategySignal.SIGNAL_EXIT
            #     signal.dir = -1
            #     signal.p = self.price.close[-1]

            # if signal and signal.signal == StrategySignal.SIGNAL_ENTRY:
            #     # if level1_signal > 0 and len(self.pivotpoint.supports[1]):
            #     #     # cancel if not below a support (long direction)
            #     #     if self.price.last >= np.nanmax(self.pivotpoint.supports[1]):
            #     #         level1_signal = 0

            #     # if level1_signal < 0 and len(self.pivotpoint.resistances[1]):
            #     #     # cancel if not above a resistance (short direction)
            #     #     if self.price.last <= np.nanmin(self.pivotpoint.resistances[1]):
            #     #         level1_signal = 0

            #     if level1_signal > 0 and len(self.pivotpoint.supports[1]):
            #         # cancel if not below a support (long direction)
            #         if self.price.last >= np.nanmax(self.pivotpoint.supports[1]):
            #             level1_signal = 0
            #             signal = None

            #     if level1_signal < 0 and len(self.pivotpoint.resistances[1]):
            #         # cancel if not below a resistance (short direction)
            #         if self.price.last <= np.nanmin(self.pivotpoint.resistances[1]):
            #             level1_signal = 0
            #             signal = None

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

            streamer.member('sma').update(self.sma.smas[i], ts)
            streamer.member('ema').update(self.ema.emas[i], ts)
            # streamer.member('hma').update(self.hma.hmas[i], ts)
            # streamer.member('vwma').update(self.vwma.vwmas[i], ts)

            streamer.member('perf').update(self.strategy_trader._stats['perf']*100, ts)

            streamer.member('end').update(ts)

            # push per frame
            streamer.push()

        streamer.next_timestamp = self.next_timestamp
