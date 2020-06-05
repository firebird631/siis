# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Forex Alpha strategy, sub-strategy A.

import numpy as np

from strategy.indicator import utils
from strategy.strategysignal import StrategySignal
from monitor.streamable import StreamMemberFloatSerie, StreamMemberSerie, StreamMemberFloatBarSerie, StreamMemberOhlcSerie
from instrument.instrument import Instrument

from terminal.terminal import Terminal

from .fasub import ForexAlphaStrategySub

import logging
logger = logging.getLogger('siis.strategy.forexalpha')


class ForexAlphaStrategySubA(ForexAlphaStrategySub):
    """
    Forex Alpha strategy, sub-strategy A.
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

        prices = self.price.compute(timestamp, candles)
        volumes = self.volume.compute(timestamp, candles)

        signal = self.process_cb(timestamp, self.last_timestamp, candles, prices, volumes)

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

    def process_td9(self, timestamp, last_timestamp, candles, prices, volumes):
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
            self.rsi.compute(timestamp, prices)

            if self.rsi.last < self.rsi_low:
                rsi_30_70 = 1.0
            elif rsi > self.rsi_high:
                rsi_30_70 = -1.0

            if self.rsi.last > 0.4 and self.rsi.last < 0.6:
                rsi_40_60 = 1

        if self.stochrsi:
            self.stochrsi.compute(timestamp, prices)
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

            if prices[-1] > self.bollingerbands.last_ma:
                bb_ma = -1
            elif prices[-1] > self.bollingerbands.last_ma:
                bb_ma = 1

        if self.atr:
            if self.last_closed:
                self.atr.compute(timestamp, self.price.high, self.price.low, self.price.close)

        if self.tomdemark:
            if self.tomdemark.compute_at_close and self.last_closed:
                # last_timestamp
                self.tomdemark.compute(timestamp, self.price.timestamp, self.price.high, self.price.low, self.price.close)

                #
                # setup entry
                #

                # long entry on sell-setup + rsi oversell
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
                        # Terminal.inst().info("Canceled long entry %s c2-c3, p:%s tf:%s" % (self.strategy_trader.instrument.symbol, signal.p, self.tf), view='default')

                #
                # setup completed
                #

                elif (((self.tomdemark.c.c >= 8 and self.tomdemark.c.p) or (self.tomdemark.c.c == 9)) and self.tomdemark.c.d < 0):  # and candles[-1].close > candles[-2].close:
                    if 1:  # stochrsi_20_80 > 1:
                        signal = StrategySignal(self.tf, timestamp)
                        signal.signal = StrategySignal.SIGNAL_EXIT
                        signal.dir = 1
                        signal.p = self.price.close[-1]
                        # Terminal.inst().info("Exit long %s %s c8p-c9 (%s%s)" % (self.strategy_trader.instrument.symbol, self.tf, self.tomdemark.c.c, 'p' if signal.p else ''), view='default')

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
                        #Terminal.inst().info("Abort long %s %s c3-c7 (%s%s)" % (self.strategy_trader.instrument.symbol, self.tf, td.c, 'p' if signal.p else ''), view='default')

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
                        Terminal.inst().info("Entry long %s %s cd13, sl:%s" % (self.strategy_trader.instrument.symbol, self.tf, signal.sl,), view='default')

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

    def process_lin(self, timestamp, last_timestamp, candles, prices, volumes):
        signal = None

        self.score.initialize()

        if self.rsi:
            self.rsi.compute(timestamp, prices)

        if self.sma:
            self.sma.compute(timestamp, prices)

        if self.ema:
            self.ema.compute(timestamp, prices)
        
        if self.vwma:
            self.vwma.compute(timestamp, prices, volumes)

        if self.atr:
            self.atr.compute(timestamp, self.price.high, self.price.low, self.price.close)

        if self.ema.last < self.sma.last:
            if self.rsi.last > 0.5:
                self.score.add(-1, 1)
            elif self.rsi.last < 0.2:
                self.score.add(1, 1)
        else:
            if self.rsi.last > 0.8:
                self.score.add(-1, 1)
            elif self.rsi.last < 0.6:
                self.score.add(1, 1)

        self.score.finalize()

        #
        # signal from score
        #

        if self.score.data[-1] >= self.score_level:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_ENTRY
            signal.dir = 1
            signal.p = candles[-1].close

        if self.score.data[-1] <= -self.score_level:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_EXIT
            signal.dir = 1
            signal.p = candles[-1].close

        if candles:
            # last processed candle timestamp (from last candle is non consolidated else from the next one)
            self.next_timestamp = candles[-1].timestamp if not candles[-1].ended else candles[-1].timestamp + self.tf

        return signal

    def process_td9_ema(self, timestamp, last_timestamp, candles, prices, volumes):
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
            self.rsi.compute(timestamp, prices)

            if self.rsi.last < self.rsi_low:
                rsi_30_70 = 1.0
            elif self.rsi.last > self.rsi_high:
                rsi_30_70 = -1.0

            if self.rsi.last > 0.4 and self.rsi.last < 0.6:
                rsi_40_60 = 1

            rsi_trend = utils.trend_extremum(self.rsi.rsis)

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

        if self.bollingerbands:
            self.bollingerbands.compute(timestamp, prices)

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
            if self.last_closed:
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

        if self.tomdemark:
            if self.tomdemark.compute_at_close and self.last_closed:
                # last_timestamp
                self.tomdemark.compute(timestamp, candles, self.price.high, self.price.low, self.price.close)

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
                        Terminal.inst().info("Canceled long entry %s c2-c3, p:%s tf:%s" % (self.strategy_trader.instrument.symbol, signal.p, self.tf), view='default')

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
                        Terminal.inst().info("Exit long %s %s c8p-c9 (%s%s)" % (self.strategy_trader.instrument.symbol, self.tf, self.tomdemark.c.c, 'p' if signal.p else ''), view='default')

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
                        Terminal.inst().info("Abort long %s %s c3-c7 (%s%s)" % (self.strategy_trader.instrument.symbol, self.tf, self.tomdemark.c.c, 'p' if signal.p else ''), view='default')

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
                        Terminal.inst().info("Entry long %s %s cd13, sl:%s" % (self.strategy_trader.instrument.symbol, self.tf, signal.sl,), view='default')

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

    def process_ch(self, timestamp, last_timestamp, candles, prices, volumes):
        """
        Entry : EMA trend + RSI level + TD9 entry confirmation
        Exit : TD9 or opposite signal
        """
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

        if self.atr:
            if self.last_closed:
                self.atr.compute(timestamp, self.price.high, self.price.low, self.price.close)

        if self.pivotpoint:
            if self.pivotpoint.compute_at_close and self.last_closed:
                self.pivotpoint.compute(timestamp, self.price.open, self.price.high, self.price.low, self.price.close)

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
            if self.tomdemark.compute_at_close and self.last_closed:
                # last_timestamp
                self.tomdemark.compute(timestamp, self.price.timestamp, self.price.high, self.price.low, self.price.close)

                # long entry on sell-setup
                if self.tomdemark.c.c >= 1 and self.tomdemark.c.c <= 6 and self.tomdemark.c.d < 0 and level1_signal > 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                    if self.tomdemark.c.tdst:
                        signal.sl = self.tomdemark.c.tdst

                    if len(self.pivotpoint.resistances[1]):
                        signal.tp = np.max(self.pivotpoint.resistances[1])

                    # Terminal.inst().info("Entry long %s %s" % (self.tomdemark.c.tdst, signal.sl), view='default')

                # short entry on buy-setup
                elif self.tomdemark.c.c >= 1 and self.tomdemark.c.c <= 6 and self.tomdemark.c.d > 0 and level1_signal < 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = -1
                    signal.p = self.price.close[-1]

                    if self.tomdemark.c.tdst:
                        signal.sl = self.tomdemark.c.tdst

                    if len(self.pivotpoint.supports[1]):
                        signal.tp = np.min(self.pivotpoint.supports[1])

                    # Terminal.inst().info("Entry short %s %s" % (self.tomdemark.c.tdst, signal.sl), view='default')

                # aggressive long entry
                elif self.tomdemark.c.c >= 8 and self.tomdemark.c.d > 0 and level1_signal > 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                    if len(self.pivotpoint.resistances[1]):
                        signal.tp = np.max(self.pivotpoint.resistances[1])

                    # td9 cannot provide us a SL, take it from ATR
                    signal.sl = self.atr.stop_loss(signal.dir)

                    # Terminal.inst().info("Aggressive long entry %s %s" % (self.tomdemark.c.tdst, signal.sl), view='default')

                # aggressive long entry
                elif self.tomdemark.c.c >= 8 and self.tomdemark.c.d < 0 and level1_signal < 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = -1
                    signal.p = self.price.close[-1]

                    if len(self.pivotpoint.supports[1]):
                        signal.tp = np.min(self.pivotpoint.supports[1])

                    # td9 cannot provide us a SL, take it from ATR
                    signal.sl = self.atr.stop_loss(signal.dir)

                    # Terminal.inst().info("Aggressive short entry %s %s" % (self.tomdemark.c.tdst, signal.sl), view='default')

                #
                # setup completed
                #

                # sell-setup
                elif self.tomdemark.c.c >= 8 and self.tomdemark.c.d < 0 and level1_signal < 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                    # Terminal.inst().info("Exit long %s %s c8p-c9 (%s%s)" % (self.strategy_trader.instrument.symbol, self.tf, self.tomdemark.c.c, 'p' if signal.p else ''), view='default')

                # buy-setup
                elif self.tomdemark.c.c >= 8 and self.tomdemark.c.d > 0 and level1_signal > 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = -1
                    signal.p = self.price.close[-1]
                    
                    # Terminal.inst().info("Exit short %s %s c8p-c9 (%s%s)" % (self.strategy_trader.instrument.symbol, self.tf, self.tomdemark.c.c, 'p' if signal.p else ''), view='default')

                #
                # setup aborted (@todo how to in this long/short case)
                #

                elif ((self.tomdemark.c.c >= 4 and self.tomdemark.c.c <= 7) and self.tomdemark.c.d < 0) and level1_signal < 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                    # Terminal.inst().info("Abort long %s %s c3-c7 (%s%s)" % (self.strategy_trader.instrument.symbol, self.tf, self.tomdemark.c.c, 'p' if signal.p else ''), view='default')

                elif ((self.tomdemark.c.c >= 4 and self.tomdemark.c.c <= 7) and self.tomdemark.c.d > 0) and level1_signal > 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = -1
                    signal.p = self.price.close[-1]

                    # Terminal.inst().info("Abort long %s %s c3-c7 (%s%s)" % (self.strategy_trader.instrument.symbol, self.tf, self.tomdemark.c.c, 'p' if signal.p else ''), view='default')

                # #
                # # invalidation 2 of opposite setup
                # #

                # elif self.tomdemark.c.c > 2 and self.tomdemark.c.d > 0 and level1_signal < 0:
                #     signal = StrategySignal(self.tf, timestamp)
                #     signal.signal = StrategySignal.SIGNAL_EXIT
                #     signal.dir = 1
                #     signal.p = self.price.close[-1]

                #     Terminal.inst().info("Canceled long entry %s c2-c3, p:%s tf:%s" % (self.strategy_trader.instrument.symbol, signal.p, self.tf), view='default')

        if signal and signal.signal == StrategySignal.SIGNAL_ENTRY:
            # if level1_signal > 0 and len(self.pivotpoint.supports[1]):
            #     # cancel if not below a support (long direction)
            #     if self.price.last >= np.nanmax(self.pivotpoint.supports[1]):
            #         level1_signal = 0

            # if level1_signal < 0 and len(self.pivotpoint.resistances[1]):
            #     # cancel if not above a resistance (short direction)
            #     if self.price.last <= np.nanmin(self.pivotpoint.resistances[1]):
            #         level1_signal = 0

            if level1_signal > 0 and len(self.pivotpoint.supports[1]):
                # cancel if not below a support (long direction)
                if self.price.last >= np.nanmax(self.pivotpoint.supports[1]):
                    level1_signal = 0
                    signal = None

            if level1_signal < 0 and len(self.pivotpoint.resistances[1]):
                # cancel if not below a resistance (short direction)
                if self.price.last <= np.nanmin(self.pivotpoint.resistances[1]):
                    level1_signal = 0
                    signal = None

        return signal

    def process_cb(self, timestamp, last_timestamp, candles, prices, volumes):
        """
        Entry : EMA crossing + TD9 entry confirmation
        Exit : TD9 or opposite signal + EMA trend + RSI level
        """
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

        if self.tf == Instrument.TF_4HOUR:
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

        # if self.bollingerbands:
        #     self.bollingerbands.compute(timestamp, prices)

        #     bb_break = 0
        #     bb_ma = 0

        #     if prices[-1] > self.bollingerbands.last_top:
        #         bb_break = 1
        #     elif prices[-1] < self.bollingerbands.last_bottom:
        #         bb_break = -1

        # #     if prices[-1] > self.bollingerbands.last_ma:
        # #         bb_ma = -1
        # #     elif prices[-1] > self.bollingerbands.last_ma:
        # #         bb_ma = 1

        if self.atr:
            if self.last_closed:
                self.atr.compute(timestamp, self.price.high, self.price.low, self.price.close)

        if self.pivotpoint:
            if self.pivotpoint.compute_at_close and self.last_closed:
                self.pivotpoint.compute(timestamp, self.price.open, self.price.high, self.price.low, self.price.close)

        if self.bsawe:
            if self.last_closed:
                # use OHLC4 as price in place of close
                bsawe = self.bsawe.compute(timestamp, self.price.high, self.price.low, self.price.prices)

                #
                # trend signal
                #

                ema_rsi_signal = 0

                if self.ema.last < self.sma.last:
                    # bear trend
                    if self.rsi.last > 0.5:  # initial: 0.5
                        ema_rsi_signal = -1
                    elif self.rsi.last < 0.2:  # initial: 0.2
                        ema_rsi_signal = 1
                else:
                    # bull trend
                    if self.rsi.last > 0.8:  # initial: 0.8
                        ema_rsi_signal = -1
                    elif self.rsi.last < 0.6:  # initial: 0.6
                        ema_rsi_signal = 1
                #
                # entry computation
                #

                if bsawe > 0 and ema_rsi_signal != -1:
                    # long entry
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                    if self.tomdemark.c.tdst and signal.sl < signal.p:
                        signal.sl = self.tomdemark.c.tdst

                    if len(self.pivotpoint.resistances[2]):
                        tp = np.max(self.pivotpoint.resistances[2])
                        if tp > self.atr.stop_loss(-1):
                            # try with twice (same for short)
                            signal.tp = (tp - signal.p) * 2.0 + signal.p
                            # signal.tp = tp

                elif bsawe < 0 and ema_rsi_signal != 1:
                    # short entry
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = -1
                    signal.p = self.price.close[-1]

                    if self.tomdemark.c.tdst and signal.sl > signal.p:
                        signal.sl = self.tomdemark.c.tdst

                    if len(self.pivotpoint.supports[2]):
                        tp = np.min(self.pivotpoint.supports[2])
                        if tp < self.atr.stop_loss(1):
                            signal.tp = signal.p - (signal.p - tp) * 2.0
                            # signal.tp = tp

        #
        # exit computation
        #

        if self.tomdemark:
            if self.tomdemark.compute_at_close and self.last_closed:
                # last_timestamp
                self.tomdemark.compute(timestamp, self.price.timestamp, self.price.high, self.price.low, self.price.close)

                # only on 5min timeframe, or could manage at strategy only for parent timeframe

                # sell-setup
                if self.tomdemark.c.c >= 8 and self.tomdemark.c.d < 0 and ema_rsi_signal < 0 and self.tf == Instrument.TF_5MIN:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                # buy-setup
                elif self.tomdemark.c.c >= 8 and self.tomdemark.c.d > 0 and ema_rsi_signal > 0 and self.tf == Instrument.TF_5MIN:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = -1
                    signal.p = self.price.close[-1]

                #
                # setup aborted (@todo how to in this long/short case)
                #

                elif ((self.tomdemark.c.c >= 4 and self.tomdemark.c.c <= 7) and self.tomdemark.c.d < 0) and ema_rsi_signal < 0 and self.tf == Instrument.TF_5MIN:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]

                elif ((self.tomdemark.c.c >= 4 and self.tomdemark.c.c <= 7) and self.tomdemark.c.d > 0) and ema_rsi_signal > 0 and self.tf == Instrument.TF_5MIN:
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

            # publish per frame
            streamer.publish()

        streamer.next_timestamp = self.next_timestamp
