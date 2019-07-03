# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy, sub-strategy A.

import numpy as np

from strategy.indicator import utils
from strategy.strategysignal import StrategySignal
from monitor.streamable import StreamMemberFloatSerie, StreamMemberSerie, StreamMemberFloatBarSerie, StreamMemberCandleSerie

from terminal.terminal import Terminal

from .casub import CryptoAlphaStrategySub

import logging
logger = logging.getLogger('siis.strategy.cryptoalpha')


class CryptoAlphaStrategySubA(CryptoAlphaStrategySub):
    """
    Crypto Alpha strategy, sub-strategy A.
    """

    def __init__(self, data, params):
        self.atr = None
        self.stochrsi = None

        super().__init__(data, params)

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

        signal = self.process4(timestamp, last_timestamp, candles, prices, volumes)

        if candles:
            # last processed candle timestamp (from last candle if non consolidated else from the next one)
            self.next_timestamp = candles[-1].timestamp if not candles[-1].ended else candles[-1].timestamp + self.tf

        # avoid duplicates signals
        if signal:
            # self.last_signal = signal
            if (self.last_signal and (signal.signal == self.last_signal.signal) and
                    (signal.dir == self.last_signal.dir) and
                    (signal.base_time() == self.last_signal.base_time())):  # or (signal.ts - self.last_signal.ts) < (self.tf * 0.5):
                # same base time avoid multiple entries on the same candle
                signal = None
            else:
                # retains the last valid signal only if valid
                self.last_signal = signal

                if self.profiling:
                    # store signal data condition when profiling
                    signal.add_condition('price', self.price.trace())
                    signal.add_condition('rsi', self.rsi.trace())
                    # signal.add_condition('sma', self.sma.trace())
                    # signal.add_condition('ema', self.ema.trace())
                    # signal.add_condition('stochrsi', self.stochrsi.trace())
                    # signal.add_condition('tomdemark', self.tomdemark.trace())
                    # signal.add_condition('bollinger', self.bollingerbands.trade())

        return signal

    def process1(self, timestamp, last_timestamp, candles, prices, volumes):
        signal = None

        # volume sma, increase signal strength when volume increase over its SMA
        # volume_sma = utils.MM_n(self.depth-1, self.volume.volumes)

        rsi = 0
        rsi_30_70 = 0  # 1 <30, -1 >70
        rsi_40_60 = 0  # 1 if RSI in 40-60
        # rsi_trend = 0

        stochrsi = 0
        stochrsi_20_80 = 0  # 1 <20, -1 >80
        stochrsi_40_60 = 0  # 1 if stochRSI in 40-60
        
        volume_signal = 0
        
        ema_sma_cross = 0
        ema_sma_height = 0

        if self.rsi:
            self.rsi.compute(last_timestamp, prices)

            if self.rsi.last < self.rsi_low:
                rsi_30_70 = 1.0
            elif rsi > self.rsi_high:
                rsi_30_70 = -1.0

            if self.rsi.last > 0.4 and self.rsi.last < 0.6:
                rsi_40_60 = 1

        if self.stochrsi:
            self.stochrsi.compute(last_timestamp, prices)
            stochrsi = self.stochrsi.last_k

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
            self.sma.compute(last_timestamp, prices)
            self.ema.compute(last_timestamp, prices)

            # ema over sma crossing
            ema_sma_cross = utils.cross((self.ema.prev, self.sma.prev), (self.ema.last, self.sma.last))

            if self.ema.last > self.sma.last:
                ema_sma_height = 1
            elif self.ema.last < self.sma.last:
                ema_sma_height = -1

        if self.bollingerbands:

            self.bollingerbands.compute(last_timestamp, prices)

            bb_break = 0
            bb_ma = 0

            if prices[-1] > self.bollingerbands.last_top:
                bb_break = 1
            elif prices[-1] < self.bollingerbands.last_bottom:
                bb_break = -1

            if prices[-1] > self.bollingerbands.last_ma:
                bb_ma = -1
            elif prices[-1] > self.bollingerbands.last_ma:
                bb_ma = 1

        if self.atr:
            self.atr.compute(last_timestamp, self.price.high, self.price.low, self.price.close)

        if self.tomdemark:
            self.tomdemark.compute(last_timestamp, candles, self.price.high, self.price.low, self.price.close)

            #
            # setup entry
            #

            # long entry on sell-setup + rsi oversell
            # soit on rentre prudent sur une 2 ou 3 au dessus de la precedent, et en plus rsi ou stochrsi oversell
            # soit on rentre bourrin sur une 1 avec close plus haute
            # soit on rentre semi bourrin sur une 2 seulement rien, d'autre
            # soit on rentre semi prudent sur une 2 au dessus de la precente, et rien de plus
            # soit on rentrer sur une 2 après une 9 du meme setup, avec close au dessus de la 9
            # on peut aussi renter selon bollinger
            #   - bollinger dans le nuage
            #   - bollinger break down avec stochRSI or RSI basse
            if (self.tomdemark.c.c == 2 and self.tomdemark.c.d < 0 and self.price.close[-1] > self.price.close[-2]) or (self.tomdemark.c.c == 3):  # avec td3            
                # # if (td.c == 1 and td.d < 0 and candles[-1].close > candles[-2].close):
                # if (td.c == 2 and td.d < 0 and candles[-1].close > candles[-2].close):
                # if ((td.c == 2 or td.c == 3) and td.d < 0 and candles[-1].close > candles[-2].close):
                # if ((td.c == 2 or td.c == 3) and td.d < 0) and candles[-1].close > candles[-2].close:
                # if bb_break == 0:
                # if (bb_break == 0 and bb_ma < 0):  # test with aggressive + bb
                # if (stochrsi_20_80 > 0 or rsi_30_70 > 0):
                # if (ema_sma_height > 0 or rsi_30_70 > 0) and bb_break >= 0:
                # if (bb_break == 0 and bb_ma < 0) and (stochrsi_20_80 > 0 or rsi_30_70 > 0):  # used with average case but not with aggressive
                # if (bb_break == 0 and bb_ma < 0) and (ema_sma_height > 0 or rsi_30_70 > 0):  #  and volume_signal > 0:
                # if (stochrsi_20_80 > 0 or rsi_30_70 > 0):  # la classique mais prend des risk, a voir avec un bon SL peut-être
                # if (rsi_trend > 0) and (ema_sma_height > 0 or rsi_30_70 > 0):  # protege de perte mais rate des gains
                # if (ema_sma_height > 0 or rsi_30_70 > 0):  #  and volume_signal > 0:  # C4
                # if ema_sma_height > 0:  # C5
                # if ema_sma_height > 0 and bb_break >= 0 and rsi_trend > 0:  # C6
                # if ema_sma_height > 0 and bb_break >= 0 and stochrsi_20_80 > 0:
                # if 1:  # C1
                # if rsi_trend > 0 and bb_break > 0:  # pas mal evite des entrees foireuses mais pas assez de profits
                # if (stochrsi_20_80 > 0 or rsi_30_70 > 0):  # la classique mais prend des risk, il faut un bon stop-loss
                if (ema_sma_height > 0 or rsi_30_70 > 0) and bb_break <= 0:
                    # if rsi_trend and (stochrsi_20_80 > 0 or rsi_30_70 > 0):
                    # if (stochrsi_20_80 > 0 and rsi_30_70 > 0):
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                    if self.tomdemark.c.tdst:
                        signal.sl = self.tomdemark.c.tdst

                    # Terminal.inst().info("Entry %s %s" % (self.tomdemark.c.tdst, signal.sl), view='default')

            # aggressive entry
            if ((self.tomdemark.c.c == 9 or (self.tomdemark.c.c == 8 and self.tomdemark.c.p)) and self.tomdemark.c.d > 0):
                # if stochrsi_20_80 > 0 and rsi_30_70 > 0 and candles[-1].close > candles[-2].close:  # C1 -
                # if 1:  # C4 +++
                # if stochrsi_20_80 > 0 and candles[-1].close > candles[-2].close:  # C3  ++
                # if rsi_30_70 > 0 and candles[-1].close > candles[-2].close:  # C5  ??
                # if ema_sma_height > 0 and bb_break >= 0 and rsi_trend > 0:  # C6 ??
                # if ema_sma_height > 0 and bb_break >= 0 and stochrsi_20_80 > 0:  # C7 ??
                # if (ema_sma_height > 0 or rsi_30_70 > 0):  # C2 +
                # if stochrsi_20_80 > 0 and candles[-1].close > candles[-2].close:  # C3  ++
                if (stochrsi_20_80 > 0 or rsi_30_70 > 0):  # C8 ??
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                    # Terminal.inst().info("Aggressive entry %s %s" % (self.tomdemark.c.tdst, signal.sl), view='default')

            #
            # invalidation 2 of opposite setup
            #

            # @todo or if a >= 3 <= 7 close below the previous candle close
            # can make loss in bull run
            # second condition might be optimized
            elif (self.tomdemark.c.c == 2 and self.tomdemark.c.d > 0 and self.price.close[-1] < self.price.close[-2]) or (self.tomdemark.c.c == 3 and self.tomdemark.c.d > 0):
                # elif td.c == 3 and td.d > 0:  # and candles[-1].close < candles[-2].close:
                # long cancelation on buy-setup formation 
                # if ema_sma_height < 0 or rsi_40_60 > 0:  # (excess of volume and ema under sma)
                # if stochrsi_20_80 < 0:  # and volume_signal > 0:
                # if bb_break < 0:
                # if (rsi_trend < 0):  # C2
                # if 1:  # C1 +
                # if (bb_break == 0 and bb_ma < 0):  # C3 ++
                if ema_sma_height < 0:  #  and volume_signal > 0:
                    # Terminal.inst().info("rsi_30_70 %s / rsi_40_60 %s / ema_sma_height %s / volume_signal %s" % (rsi_30_70, rsi_40_60, ema_sma_height, volume_signal), view='default')
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT  # CANCEL
                    signal.dir = 1
                    signal.p = self.price.close[-1]
                    # Terminal.inst().info("Canceled long entry %s c2-c3, p:%s tf:%s" % (self.data.instrument.symbol, signal.p, self.tf), view='default')

            #
            # setup completed
            #

            elif (((self.tomdemark.c.c >= 8 and self.tomdemark.c.p) or (self.tomdemark.c.c == 9)) and self.tomdemark.c.d < 0):  # and candles[-1].close > candles[-2].close:
                if 1:  # stochrsi_20_80 > 1:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]
                    # Terminal.inst().info("Exit long %s %s c8p-c9 (%s%s)" % (self.data.instrument.symbol, self.tf, self.tomdemark.c.c, 'p' if signal.p else ''), view='default')

            #
            # setup aborted
            #

            elif ((self.tomdemark.c.c >= 2 and self.tomdemark.c.c <= 7) and self.tomdemark.c.d < 0) and self.price.close[-1] < self.price.close[-2]:  # C1
                # if stochrsi_20_80 < 0 or rsi_30_70 < 0:  # bearish stoch OR rsi  # C1
                if stochrsi_20_80 < 0 and rsi_30_70 < 0:  # bearish stoch AND rsi (seems better)  # C2
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]
                    #Terminal.inst().info("Abort long %s %s c3-c7 (%s%s)" % (self.data.instrument.symbol, self.tf, td.c, 'p' if signal.p else ''), view='default')

            #
            # CD entry
            #

            if self.tomdemark.cd.c > 1:
                Terminal.inst().info("CD%s" % self.tomdemark.cd.c)

            if self.tomdemark.cd.c == 1:
                # count-down buy-setup + rsi oversell
                Terminal.inst().info("CD1")
                if self.tomdemark.c.d < 0:  # and candles[-1].close > candles[-2].high:
                    # if rsi_30_70 > 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = self.price.last
                    signal.sl = self.tomdemark.c.tdst
                    Terminal.inst().info("Entry long %s %s cd13, sl:%s" % (self.data.instrument.symbol, self.tf, signal.sl,), view='default')

            #
            # CD13 setup
            #

            elif self.tomdemark.cd.c == 13:
                # count-down sell-setup completed
                if self.tomdemark.cd.d < 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.p = self.price.close[-1]
                    signal.dir = 1
                    Terminal.inst().info("Exit long cd13", view='default')

        return signal

    def process3(self, timestamp, last_timestamp, candles, prices, volumes):
        signal = None

        # volume sma, increase signal strength when volume increase over its SMA
        # volume_sma = utils.MM_n(self.depth-1, self.volume.volumes)

        rsi_30_70 = 0  # 1 <30, -1 >70
        rsi_40_60 = 0  # 1 if RSI in 40-60
        rsi_trend = 0

        stochrsi_20_80 = 0  # 1 <20, -1 >80
        stochrsi_40_60 = 0  # 1 if stochRSI in 40-60
        
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

            rsi_trend = utils.trend_extremum(self.rsi.rsis)

        if self.stochrsi:
            self.stochrsi.compute(last_timestamp, prices)

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
            self.sma.compute(last_timestamp, prices)
            self.ema.compute(last_timestamp, prices)

            # ema over sma crossing
            ema_sma_cross = utils.cross((self.ema.prev, self.sma.prev), (self.ema.last, self.sma.last))

            if self.ema.last > self.sma.last:
                ema_sma_height = 1
            elif self.ema.last < self.sma.last:
                ema_sma_height = -1

        if self.bollingerbands:
            self.bollingerbands.compute(last_timestamp, prices)

            bb_break = 0
            bb_ma = 0

            if prices[-1] > self.bollingerbands.last_top:
                bb_break = 1
            elif prices[-1] < self.bollingerbands.last_bottom:
                bb_break = -1

            if prices[-1] > self.bollingerbands.last_ma:
                bb_ma = -1
            elif prices[-1] > self.bollingerbands.last_ma:
                bb_ma = 1

        if self.atr:
            self.atr.compute(last_timestamp, self.price.high, self.price.low, self.price.close)

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

        if self.tomdemark:
            self.tomdemark.compute(last_timestamp, candles, self.price.high, self.price.low, self.price.close)

            #
            # setup entry
            #

            # long entry on sell-setup + rsi oversell
            if (self.tomdemark.c.c == 2 and self.tomdemark.c.d < 0 and self.price.close[-1] > self.price.close[-2]) or (self.tomdemark.c.c == 3):  # avec td3
                # if (td.c == 1 and td.d < 0 and candles[-1].close > candles[-2].close):
                # if (td.c == 2 and td.d < 0 and candles[-1].close > candles[-2].close):
                # if ((td.c == 2 or td.c == 3) and td.d < 0 and candles[-1].close > candles[-2].close):
                # if ((td.c == 2 or td.c == 3) and td.d < 0) and candles[-1].close > candles[-2].close:
                # if bb_break == 0:
                # if (bb_break == 0 and bb_ma < 0):  # test with aggressive + bb
                # if (stochrsi_20_80 > 0 or rsi_30_70 > 0):
                # if (ema_sma_height > 0 or rsi_30_70 > 0) and bb_break >= 0:
                # if (bb_break == 0 and bb_ma < 0) and (stochrsi_20_80 > 0 or rsi_30_70 > 0):  # used with average case but not with aggressive
                # if (bb_break == 0 and bb_ma < 0) and (ema_sma_height > 0 or rsi_30_70 > 0):  #  and volume_signal > 0:
                # if (stochrsi_20_80 > 0 or rsi_30_70 > 0):  # la classique mais prend des risk, a voir avec un bon SL peut-être
                # if (rsi_trend > 0) and (ema_sma_height > 0 or rsi_30_70 > 0):  # protege de perte mais rate des gains
                # if (ema_sma_height > 0 or rsi_30_70 > 0):  #  and volume_signal > 0:  # C4
                # if ema_sma_height > 0:  # C5
                # if ema_sma_height > 0 and bb_break >= 0 and rsi_trend > 0:  # C6
                # if ema_sma_height > 0 and bb_break >= 0 and stochrsi_20_80 > 0:
                # if 1:  # C1
                # if rsi_trend > 0 and bb_break > 0:  # pas mal evite des entrees foireuses mais pas assez de profits
                if level1_signal > 0:
                    # if (stochrsi_20_80 > 0 or rsi_30_70 > 0):  # la classique mais prend des risk, il faut un bon stop-loss
                    # if rsi_trend and (stochrsi_20_80 > 0 or rsi_30_70 > 0):
                    # if (stochrsi_20_80 > 0 and rsi_30_70 > 0):
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                    if self.tomdemark.c.tdst:
                        signal.sl = self.tomdemark.c.tdst

                    Terminal.inst().info("Entry %s %s" % (self.tomdemark.c.tdst, signal.sl), view='default')

            # aggressive entry
            if self.tomdemark.c.c == 9 and self.tomdemark.c.d > 0:
                # if ((self.tomdemark.c.c == 9 or (self.tomdemark.c.c == 8 and self.tomdemark.c.p)) and self.tomdemark.c.d > 0):
                # if stochrsi_20_80 > 0 and rsi_30_70 > 0 and candles[-1].close > candles[-2].close:  # C1 -
                # if 1:  # C4 +++
                # if stochrsi_20_80 > 0 and candles[-1].close > candles[-2].close:  # C3  ++
                # if rsi_30_70 > 0 and candles[-1].close > candles[-2].close:  # C5  ??
                # if ema_sma_height > 0 and bb_break >= 0 and rsi_trend > 0:  # C6 ??
                # if ema_sma_height > 0 and bb_break >= 0 and stochrsi_20_80 > 0:  # C7 ??
                # if (ema_sma_height > 0 or rsi_30_70 > 0):  # C2 +
                # if 1:
                # if stochrsi_20_80 > 0 and candles[-1].close > candles[-2].close:  # C3  ++
                # if (stochrsi_20_80 > 0 or rsi_30_70 > 0):  # C8 ??
                if level1_signal > 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                    Terminal.inst().info("Aggressive entry %s %s" % (self.tomdemark.c.tdst, signal.sl), view='default')

            #
            # invalidation 2 of opposite setup
            #

            # @todo or if a >= 3 <= 7 close below the previous candle close
            # can make loss in bull run
            # second condition might be optimized
            elif (self.tomdemark.c.c == 2 and self.tomdemark.c.d > 0 and self.price.close[-1] < self.price.close[-2]) or (self.tomdemark.c.c == 3 and self.tomdemark.c.d > 0):
                # elif td.c == 3 and td.d > 0:  # and self.price.close < self.price.close:
                # long cancelation on buy-setup formation 
                # if ema_sma_height < 0 or rsi_40_60 > 0:  # (excess of volume and ema under sma)
                # if stochrsi_20_80 < 0:  # and volume_signal > 0:
                # if bb_break < 0:
                # if (rsi_trend < 0):  # C2
                # if ema_sma_height < 0:  #  and volume_signal > 0:
                if 1:  # C1 +
                    # if level1_signal < 0:
                    # if (bb_break == 0 and bb_ma < 0):  # C3 ++
                    # Terminal.inst().info("rsi_30_70 %s / rsi_40_60 %s / ema_sma_height %s / volume_signal %s" % (rsi_30_70, rsi_40_60, ema_sma_height, volume_signal), view='default')
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT  # CANCEL
                    signal.dir = 1
                    signal.p = self.price.close[-1]
                    Terminal.inst().info("Canceled long entry %s c2-c3, p:%s tf:%s" % (self.data.instrument.symbol, signal.p, self.tf), view='default')

            #
            # setup completed
            #

            elif (((self.tomdemark.c.c >= 8 and self.tomdemark.c.p) or (self.tomdemark.c.c == 9)) and self.tomdemark.c.d < 0):  # and self.price.close[-1] > self.price.close[-2]:
                # if 1:  # stochrsi_20_80 > 1:
                if 1: # if level1_signal < 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]
                    Terminal.inst().info("Exit long %s %s c8p-c9 (%s%s)" % (self.data.instrument.symbol, self.tf, self.tomdemark.c.c, 'p' if signal.p else ''), view='default')

            #
            # setup aborted
            #

            elif ((self.tomdemark.c.c >= 2 and self.tomdemark.c.c <= 7) and self.tomdemark.c.d < 0) and self.price.close[-1] < self.price.close[-2]:  # C1
                # if stochrsi_20_80 < 0 or rsi_30_70 < 0:  # bearish stoch OR rsi  # C1
                # if stochrsi_20_80 < 0 and rsi_30_70 < 0:  # bearish stoch AND rsi (seems better)  # C2
                if 1:  # level1_signal < 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]
                    Terminal.inst().info("Abort long %s %s c3-c7 (%s%s)" % (self.data.instrument.symbol, self.tf, self.tomdemark.c.c, 'p' if signal.p else ''), view='default')

            #
            # CD entry
            #

            if self.tomdemark.cd.c >= 1 and self.tomdemark.cd.c <= 3:
                # count-down buy-setup + rsi oversell
                if self.tomdemark.cd.d < 0:  # and self.price.close[-1] > self.price.high[-2]:
                    # if rsi_30_70 > 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = self.price.close[-1]
                    signal.sl = self.tomdemark.c.tdst
                    Terminal.inst().info("Entry long %s %s cd13, sl:%s" % (self.data.instrument.symbol, self.tf, signal.sl,), view='default')

            #
            # CD13 setup
            #

            elif self.tomdemark.cd.c == 13:
                # count-down sell-setup completed
                if self.tomdemark.cd.d < 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.p = self.price.close[-1]
                    signal.dir = 1
                    Terminal.inst().info("Exit long cd13", view='default')

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

        if self.rsi:
            self.rsi.compute(last_timestamp, prices)

            if self.rsi.last < self.rsi_low:
                rsi_30_70 = 1.0
            elif self.rsi.last > self.rsi_high:
                rsi_30_70 = -1.0

            if self.rsi.last > 0.4 and self.rsi.last < 0.6:
                rsi_40_60 = 1

            rsi_trend = utils.trend_extremum(self.rsi.rsis)

        # if self.stochrsi:
        #     self.stochrsi.compute(last_timestamp, prices)

        #     if self.stochrsi.last_k < 0.2:
        #         stochrsi_20_80 = 1.0
        #     elif self.stochrsi.last_k > 0.8:
        #         stochrsi_20_80 = -1.0

        #     if self.stochrsi.last_k > 0.4 and self.stochrsi.last_k < 0.6:
        #         stochrsi_40_60 = 1

        # if self.volume_ema:
        #     self.volume_ema.compute(last_timestamp, volumes)

        #     if self.volume.last > self.volume_ema.last:
        #         volume_signal = 1
        #     elif self.volume.last < self.volume_ema.last:
        #         volume_signal = -1

        if self.sma and self.ema:
            self.sma.compute(last_timestamp, prices)
            self.ema.compute(last_timestamp, prices)

            # ema over sma crossing
            ema_sma_cross = utils.cross((self.ema.prev, self.sma.prev), (self.ema.last, self.sma.last))

            if self.ema.last > self.sma.last:
                ema_sma_height = 1
            elif self.ema.last < self.sma.last:
                ema_sma_height = -1

        if self.pivotpoint:
            self.pivotpoint.compute(last_timestamp, self.price.open, self.price.high, self.price.low, self.price.close)

        if self.bollingerbands:
            self.bollingerbands.compute(last_timestamp, prices)

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

        if self.bbawe:
            bbawe = self.bbawe.compute(last_timestamp, self.price.high, self.price.low, self.price.close)

        if self.atr:
            self.atr.compute(last_timestamp, self.price.high, self.price.low, self.price.close)

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

        if bbawe > 0 and level1_signal >= 0:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_ENTRY
            signal.dir = 1
            signal.p = self.price.close[-1]

            # Terminal.inst().info("Entry long %s %s" % (self.data.instrument.symbol, self.tf), view='content')

            if self.tomdemark.c.tdst:
                signal.sl = self.tomdemark.c.tdst

        elif bbawe < 0 and level1_signal < 0:
            # exit signal
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_EXIT
            signal.dir = 1
            signal.p = self.price.close[-1]
            # signal = None

        if self.tomdemark:
            self.tomdemark.compute(last_timestamp, candles, self.price.high, self.price.low, self.price.close)

            if self.tomdemark.c.c >= 9 and self.tomdemark.c.d < 0 and level1_signal < 0:
                # setup complete and trend change
                signal = StrategySignal(self.tf, timestamp)
                signal.signal = StrategySignal.SIGNAL_EXIT
                signal.dir = 1
                signal.p = self.price.close[-1]

                # Terminal.inst().info("Exit long %s %s c8p-c9 (%s%s)" % (self.data.instrument.symbol, self.tf, self.tomdemark.c.c, 'p' if signal.p else ''), view='content')
                signal = None

            elif self.tomdemark.c.c >= 2 and self.tomdemark.c.d > 1:
                # cancelation
                signal = StrategySignal(self.tf, timestamp)
                signal.signal = StrategySignal.SIGNAL_EXIT
                signal.dir = 1
                signal.p = self.price.close[-1]

        return signal

    def setup_streamer(self, streamer):
        streamer.add_member(StreamMemberSerie('begin'))
        
        streamer.add_member(StreamMemberCandleSerie('candle'))
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

            streamer.member('candle').update((self.price.open[i], self.price.high[i], self.price.low[i], self.price.close[i]), ts)

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

            streamer.member('perf').update(self.data._stats['perf']*100, ts)

            streamer.member('end').update(ts)

            # push per frame
            streamer.push()

        streamer.next_timestamp = self.next_timestamp
