# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Crypto Alpha strategy, sub-strategy A.

import numpy as np

from strategy.indicator import utils
from strategy.strategysignal import StrategySignal
from monitor.streamable import StreamMemberFloatSerie, StreamMemberSerie, StreamMemberFloatBarSerie, StreamMemberOhlcSerie

from .casub import CryptoAlphaStrategySub

import logging
logger = logging.getLogger('siis.strategy.cryptoalpha')


class CryptoAlphaStrategySubA(CryptoAlphaStrategySub):
    """
    Crypto Alpha strategy, sub-strategy A.
    """

    def __init__(self, strategy_trader, params):
        self.stochrsi = None

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

        signal = self.process4(timestamp, self.last_timestamp, candles, prices, volumes)

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

        if self.tomdemark:
            # last_timestamp
            self.tomdemark.compute(timestamp, self.price.timestamp, self.price.high, self.price.low, self.price.close)

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
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT  # CANCEL
                    signal.dir = 1
                    signal.p = self.price.close[-1]

            #
            # setup completed
            #

            elif (((self.tomdemark.c.c >= 8 and self.tomdemark.c.p) or (self.tomdemark.c.c == 9)) and self.tomdemark.c.d < 0):  # and candles[-1].close > candles[-2].close:
                if 1:  # stochrsi_20_80 > 1:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT
                    signal.dir = 1
                    signal.p = self.price.close[-1]

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

            #
            # CD entry
            #

            if self.tomdemark.cd.c == 1:
                # count-down buy-setup + rsi oversell
                if self.tomdemark.c.d < 0:  # and candles[-1].close > candles[-2].high:
                    # if rsi_30_70 > 0:
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_ENTRY
                    signal.dir = 1
                    signal.p = self.price.last
                    signal.sl = self.tomdemark.c.tdst

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
            # last_timestamp
            self.tomdemark.compute(timestamp, self.price.timestamp, self.price.high, self.price.low, self.price.close)

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
                    signal = StrategySignal(self.tf, timestamp)
                    signal.signal = StrategySignal.SIGNAL_EXIT  # CANCEL
                    signal.dir = 1
                    signal.p = self.price.close[-1]

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

        ema_sma = 0

        if self.ema.last < self.sma.last:
            # bear trend
            if self.rsi.last > 0.5:  # initial: 0.5
                ema_sma = -1
            elif self.rsi.last < 0.2:  # initial: 0.2
                ema_sma = 1
        else:
            # bull trend
            if self.rsi.last > 0.8:  # initial: 0.8
                ema_sma = -1
            elif self.rsi.last < 0.6:  # initial: 0.6
                ema_sma = 1

        # @todo dip, bounce or trend...

        if bsawe > 0 and ema_sma > 0:
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_ENTRY
            signal.dir = 1
            signal.p = self.price.close[-1]

        elif bsawe < 0 and ema_sma < 0:
            # exit signal
            signal = StrategySignal(self.tf, timestamp)
            signal.signal = StrategySignal.SIGNAL_EXIT
            signal.dir = 1
            signal.p = self.price.close[-1]

        if self.tomdemark:
            # last_timestamp
            self.tomdemark.compute(timestamp, self.price.timestamp, self.price.high, self.price.low, self.price.close)

            if 0: # self.tomdemark.c.c >= 8 and self.tomdemark.c.d < 0 and (ema_sma < 0 or bsawe < 0):
                # setup complete and trend change
                signal = StrategySignal(self.tf, timestamp)
                signal.signal = StrategySignal.SIGNAL_EXIT
                signal.dir = 1
                signal.p = self.price.close[-1]

            elif 2 <= self.tomdemark.c.c <= 5 and self.tomdemark.c.d > 0 and (ema_sma < 0 and bsawe < 0):
                # cancelation
                signal = StrategySignal(self.tf, timestamp)
                signal.signal = StrategySignal.SIGNAL_EXIT
                signal.dir = 1
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
