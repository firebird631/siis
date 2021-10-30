# @date 2018-12-15
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Tom Demark 9 indicator

from strategy.indicator.indicator import Indicator

import logging
logger = logging.getLogger('siis.strategy.indicator')


class CToken(object):

    def __init__(self):
        self.c = 0      # count (9)
        self.d = 0      # direction
        self.p = False  # perfect (8 or 9)

        self.tdst = 0   # tdst price


class CDToken(object):

    def __init__(self):
        self.c = 0         # count-down value
        self.d = 0         # direction
        self.q = False     # qualifier

        self.eigth = 0.0   # price of the eight


class TomDemarkIndicator(Indicator):
    """
    Tom Demark 9 indicator.
    On compare les closes, de la derniere bougie avec celle 4 positions plus tot.
    Donc le min length doit etre de 4+1 (+1 pour trouver le flip).

    @ref https://www.youtube.com/watch?v=fpy6XIZ5i8w&index=19&list=LLFsBV7tmWUGtCS8CRRPv5dQ&t=1686s
    @ref http://practicaltechnicalanalysis.blogspot.com/2013/01/tom-demark-sequential.html
    @ref https://www.mql5.com/en/code/viewcode/8966/130033/MAB_TD_Sequential.mq4
    """

    __slots__ =  '_length', '_c', '_prev_c', '_cd', '_prev_cd', '_agg_cd', '_prev_agg_cd', '_high_low'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_INDEX

    def __init__(self, timeframe, length=9):
        super().__init__("tomdemark", timeframe)

        self._compute_at_close = True  # compute at close
        self._length = length   # periods number for the price SMA

        self._c = CToken()         # last computed count, relative to last/current candle/price
        self._prev_c = CToken()    # previous computed count, relative to previous candle/price (linear, at 1 x step-time)

        self._cd = CDToken()       # last computed count-down, relative to last/current candle/price
        self._prev_cd = CDToken()  # previous computed count-down, relative to previous count-down (not linear, at N x step-time)

        self._agg_cd = CDToken()       # similar as cd but for aggresive variation
        self._prev_agg_cd = CDToken()

        self._high_low = 0.0  # higher or lower of the setup

    @property
    def length(self):
        return self._length
    
    @length.setter
    def length(self, length):
        self._length = length

    @property
    def c(self):
        return self._c

    @property
    def cd(self):
        return self._cd

    @property
    def agg_cd(self):
        return self._agg_cd

    # def compute(self, timestamp, candles):
    #     # data with history
    #     delta = min(len(candles), int((timestamp - self._last_timestamp) / self._timeframe))

    #     # append for the new candles
    #     for x in range(0, delta):
    #         token = TDToken(self._timeframe)
    #         self._tds.append(token)

    #     num = len(self._tds)

    #     # base index (minus one if update the current candle)
    #     base = (delta + 1 if timestamp == self._last_timestamp else delta)

    #     # and complete
    #     tds = self._tds
    #     num_candles = len(candles)

    #     for i in range(num-base, num):
    #         j = num_candles - (num - i)

    #         # logger.info(">", tds[i].c, num, base, num-base, i)
    #         if self._last_timestamp and timestamp >= candles[j].timestamp + self._timeframe and tds[i].c > 0:
    #             # ignore previously computed candles except at first pass
    #             logger.info(tds[i].c, timestamp, candles[j].timestamp, self._timeframe)
    #             logger.error("TD9 compute overlap %s %s %s %s %s !" % (j, num_candles, i, num, delta))
    #             continue

    #         # True low/True high – is the lowest and the highest point for a setup, BUT including gaps before bar 1 and the days after the 9-th bar, qualifying for a setup bar. 

    #         # buy-setup
    #         if (candles[j].close <= candles[j-4].close) and (candles[j-1].close >= candles[j-5].close):
    #             tds[i].d = 1   # momentum flip, buy setup
    #             tds[i].c = 1   # new buy setup
    #             self.hl = candles[j].high

    #         # sell-setup
    #         elif (candles[j].close >= candles[j-4].close) and (candles[j-1].close <= candles[j-5].close):
    #             tds[i].d = -1  # momentum flip, sell setup
    #             tds[i].c = 1   # new sell setup
    #             self.hl = candles[j].low

    #         # buy setup continuation
    #         elif (candles[j].close < candles[j-4].close) and (tds[i-1].d == 1):
    #             tds[i].d = 1
    #             if tds[i-1].c < 9:
    #                 tds[i].c = tds[i-1].c + 1
    #                 self.hl = max(candles[j].high, self.hl)
    #             else:
    #                 # buy-setup begin in buy-setup
    #                 tds[i].c = 1

    #         # sell setup continuation
    #         elif (candles[j].close > candles[j-4].close) and (tds[i-1].d == -1):
    #             tds[i].d = -1
    #             if tds[i-1].c < 9:
    #                 tds[i].c = tds[i-1].c + 1
    #                 self.hl = min(candles[j].low, self.hl)
    #             else:
    #                 # sell-setup begin in sell-setup
    #                 tds[i].c = 1

    #         # 8 or 9 perfect
    #         if tds[i].c >= 8:
    #             if tds[i].d == 1:
    #                 # lower low at count 8 over 6 and 9 over 7
    #                 if candles[j].low < candles[j-2].low:
    #                     tds[i].p = True
    #                 else:
    #                     tds[i].p = False  # can be loose

    #             elif tds[i].d == -1:
    #                 # higher high at count 8 over 6 and 9 over 7
    #                 if candles[j].high > candles[j-2].high:
    #                     tds[i].p = True
    #                 else:
    #                     tds[i].p = False  # can be loose

    #         # combo (buy-setup in buy-setup / sell-setup in sell-setup)
    #         # @todo

    #         #
    #         # count-down
    #         #

    #         if tds[i].cd == 8:
    #             # keep close of the 8 for countdown
    #             self.cd8 = candles[j].close

    #         #
    #         # buy-setup countdown
    #         #

    #         # .cd and .acd pas bon car si on refresh la meme timeframe
    #         # on va compter d'autant plus...

    #         if tds[i-1].d == 1:
    #             # classical countdown
    #             if tds[i].c == 9 and not self.cd:
    #                 # start
    #                 self.cd = 1
    #                 self.cdd = 1

    #                 tds[i].cd = 0
    #                 tds[i].cdd = 1

    #             # aggressive countdown
    #             if tds[i].c == 9 and not self.cd:
    #                 # start
    #                 self.acd = 1
    #                 self.acdd = 1

    #                 tds[i].acd = 0
    #                 tds[i].acdd = 1

    #         # buy-setup countdown
    #         if self.cdd == 1:
    #             if (candles[j].close < candles[j-2].low) and (self.cd >= 1) and (self.cd < 13):
    #                 # continue
    #                 tds[i].cd = self.cd
    #                 tds[i].cdd = self.cdd

    #                 self.cd += 1  # next

    #             # qualifier
    #             if (tds[i].cd == 13) and (candles[j].low <= self.cd8):
    #                 tds[i].cdq = True

    #         # buy-setup countdown aggressive
    #         if self.acdd == 1:
    #             if (candles[j].low < candles[j-2].low) and (self.acd >= 1) and (self.acd < 13):
    #                 # continue
    #                 tds[i].acd = self.acd
    #                 tds[i].acdd = self.acdd

    #                 self.acd += 1  # next

    #             # qualifier
    #             if (tds[i].acd == 13) and (candles[j].low <= self.acd8):
    #                 tds[i].acdq = True

    #         #
    #         # sell-setup countdown
    #         #

    #         if tds[i-1].d == -1:
    #             # classical countdown
    #             if tds[i].c == 9 and not self.cd:
    #                 # start
    #                 self.cd = 1
    #                 self.cdd = 1

    #                 tds[i].cd = 0
    #                 tds[i].cdd = -1

    #             # aggressive countdown
    #             if tds[i].c == 9 and not self.cd:
    #                 # start
    #                 self.acd = 1
    #                 self.acdd = -1

    #                 tds[i].acd = 0
    #                 tds[i].acdd = -1

    #         # sell-setup countdown
    #         if self.cdd == -1:
    #             if (candles[j].close >= candles[j-2].high) and (tds[i-1].cd >= 1) and (tds[i-1].cd < 13):
    #                 # continue
    #                 tds[i].cd = self.cd
    #                 tds[i].cdd = self.cdd

    #                 self.cd += 1  # next

    #             # qualifier
    #             if (tds[i].cd == 13) and (candles[j].high >= self.cd8):
    #                 tds[i].cdq = True

    #         # sell-setup countdown aggressive
    #         if self.acdd == -1:
    #             if (candles[j].high >= candles[j-2].high) and (tds[i-1].acd >= 1) and (tds[i-1].acd < 13):
    #                 # continue
    #                 tds[i].acd = self.acd
    #                 tds[i].acdd = self.acdd

    #                 self.acd += 1  # next                   

    #             # qualifier
    #             if (tds[i].acd == 13) and (candles[j].high >= self.acd8):
    #                 tds[i].acdq = True

    #         #
    #         # TDST is the lowest low of a buy setup, or the highest high of a sell setup
    #         #

    #         if tds[i].c == 9:
    #             tds[i].tdst = self.hl

    #             if self.cd > 0 and tds[i].d != self.cdd:
    #                 # count-down cancellation when buy-setup appears during a sell count-down or a sell-setup appear during a buy count-down.
    #                 tds[i].cd = 0
    #                 tds[i].cdd = 0
    #                 tds[i].cdq = False

    #                 self.cd = 0
    #                 self.cdd = 0
    #                 self.cd8 = 0

    #             if self.acd > 0 and tds[i].d != self.cdd:
    #                 # same for aggressive count-down
    #                 tds[i].acd = 0
    #                 tds[i].acdd = 0
    #                 tds[i].acdq = False

    #                 self.acd = 0
    #                 self.acdd = 0
    #                 self.acd8 = 0

    #         else:
    #             # copy from previous
    #             tds[i].tdst = tds[i-1].tdst

    #         # count-down cancellation on TSDT
    #         if ((tds[i-1].d == 1) and (candles[j].close > tds[i].tdst)) or ((tds[i-1].d == -1) and (candles[j].close < tds[i].tdst)):
    #             tds[i].tdst = 0

    #             tds[i].cd = 0
    #             tds[i].cdd = 0
    #             tds[i].cdq = False

    #             self.cd = 0
    #             self.cdd = 0
    #             self.cd8 = 0

    #             tds[i].acd = 0
    #             tds[i].acdd = 0
    #             tds[i].acdq = False

    #             self.acd = 0
    #             self.acdd = 0
    #             self.acd8 = 0

    #     if len(self._tds) > self._length:
    #         # limit to history size
    #         self._tds = self._tds[-self._length:]

    #     self._last_timestamp = timestamp

    #     return self._tds

    def __td9(self, b, high, low, close):
        # True low/True high – is the lowest and the highest point for a setup, BUT including gaps before bar 1 and the days after the 9-th bar, qualifying for a setup bar. 

        # buy-setup
        if (close[b] <= close[b-4]) and (close[b-1] >= close[b-5]):
            self._c.d = 1   # momentum flip, buy setup
            self._c.c = 1   # new buy setup
            self._high_low = high[b]

        # sell-setup
        elif (close[b] >= close[b-4]) and (close[b-1] <= close[b-5]):
            self._c.d = -1   # momentum flip, sell setup           
            self._c.c = 1    # new sell setup
            self._high_low = low[b]

        # buy setup continuation
        elif (close[b] < close[b-4]) and (self._prev_c.d > 0):
            self._c.d = 1

            if self._prev_c.c < 9:
                self._c.c = self._prev_c.c + 1
                self._high_low = max(high[b], self._high_low)
            else:
                # buy-setup begin after buy-setup
                self._c.c = 1

        # sell setup continuation
        elif (close[b] > close[b-4]) and (self._prev_c.d < 0):
            self._c.d = -1

            if self._prev_c.c < 9:
                self._c.c = self._prev_c.c + 1
                self._high_low = min(low[b], self._high_low)
            else:
                # sell-setup begin in sell-setup
                self._c.c = 1

        # 8 or 9 perfect
        if self._c.c >= 8:
            if self._c.d > 0:
                # lower low at count 8 over 6 and 9 over 7
                if low[b] < low[b-2]:
                    self._c.p = True
                else:
                    self._c.p = False  # can be loose

            elif self._c.d < 0:
                # higher high at count 8 over 6 and 9 over 7
                if high[b] > high[b-2]:
                    self._c.p = True
                else:
                    self._c.p = False  # can be loose

        # combo (buy-setup in buy-setup / sell-setup in sell-setup)
        # @todo

        #
        # count-down
        #

        # retain the price if the 8 count-down
        if self._cd.c == 8:
            self._cd.eight = close[b]

        # similar for aggressive count-down
        if self._agg_cd.c == 8:
            self._agg_cd.eight = close[b]

        #
        # buy-setup countdown
        #

        if self._prev_c.d > 0:
            # classical countdown, start on a nine
            if self._c.c == 9 and self._prev_cd.c == 0:
                # start
                self._cd.c = 1
                self._cd.d = 1

            # aggressive countdown
            if self._c.c == 9 and self._prev_cd.c == 0:
                # start
                self._agg_cd.c = 1
                self._agg_cd.d = 1

        # buy-setup countdown
        if self._cd.d > 0:
            if (close[b] < low[b-2]) and (self._prev_cd.c >= 1) and (self._prev_cd.c < 13):
                # continue
                self._cd.c = self._prev_cd.c + 1
                self._cd.d = 1

            if (self._cd.c == 13) and (low[b] <= self._cd.eight):
                self._cd.q = True

        # buy-setup countdown aggressive
        if self._agg_cd.d == 1:
            if (low[b] < low[b-2]) and (self._prev_agg_cd.c >= 1) and (self._prev_agg_cd.c < 13):
                # continue
                self._agg_cd.c = self._prev_agg_cd.c + 1
                self._agg_cd.d = -1

            # qualifier
            if (self._agg_cd.c == 13) and (low[b] <= self._agg_cd.eight):
                self._agg_cd.q = True

        #
        # sell-setup countdown
        #

        if self._prev_c.d < 0:
            # classical countdown, start on a nine
            if self._c.c == 9 and self._prev_cd.c == 0:
                # start
                self._cd.c = 1
                self._cd.d = -1

            # aggressive countdown
            if self._c.c == 9 and self._prev_cd.c == 0:
                # start
                self._agg_cd.c = 1
                self._agg_cd.d = -1

        # sell-setup countdown
        if self._cd.d < 0:
            if (close[b] >= high[b-2]) and (self._prev_cd.c >= 1) and (self._prev_cd.c < 13):
                # continue
                self._cd.c = self._prev_cd.c + 1
                self._cd.d = -1

            # qualifier
            if (self._cd.c == 13) and (high[b] >= self._cd.eight):
                self._cd.q = True

        # sell-setup countdown aggressive
        if self._agg_cd.d < 0:
            if (high[b] >= high[b-2]) and (self._prev_agg_cd.c >= 1) and (self._prev_agg_cd.c < 13):
                # continue
                self._agg_cd.c = self._prev_agg_cd.c + 1
                self._agg_cd.d = 1

            # qualifier
            if (self._agg_cd.c == 13) and (high[b] >= self._agg_cd.eight):
                self._agg_cd.q = True

        #
        # TDST is the lowest low of a buy setup, or the highest high of a sell setup
        #

        if self._c.c == 9:
            # set TDST if a setup accomplished
            self._c.tdst = self._high_low

            if self._cd.d > 0 and self._c.d != self._cd.d:
                # count-down cancellation when buy-setup appears during a sell count-down or a sell-setup appear during a buy count-down.
                self._cd = CToken()

            if self._agg_cd.d > 0 and self._c.d != self._agg_cd.d:
                # same for aggressive count-down
                self._agg_cd = CToken()
        else:
            # copy from previous
            self._c.tdst = self._prev_c.tdst

        # count-down cancellation on TDST
        if ((self._prev_c.d > 0) and (close[b] > self._c.tdst)) or ((self._prev_c.d < 0) and (close[b] < self._c.tdst)):
            self._cd = CToken()
            self._agg_cd = CToken()

            # TDST canceled too
            self._c.tdst = 0

    def compute(self, timestamp, timestamps, high, low, close):
        # delta of 0 mean overwrite the last
        delta = min(int((timestamp - self._last_timestamp) / self._timeframe), len(timestamps))

        # base index (minus one if update the current candle)
        base = (delta + 1 if timestamp == self._last_timestamp else delta)
        num = len(timestamps)

        for b in range(num-base, num):
            # reset latest
            self._c = CToken()
            self._cd = CDToken()
            self._agg_cd = CDToken()

            # continue with the next non processed candle or the current non closed
            self.__td9(b, high, low, close)

            if timestamps[b] > self._last_timestamp:
                # validate last candle
                self._prev_c = self._c

                if self._cd.c > 0:
                    # validate a count-down only if valid at this candle
                    self._prev_cd = self._cd

                if self._agg_cd.c > 0:
                    # similar of aggressive count-down
                    self._prev_agg_cd = self._agg_cd

        self._last_timestamp = timestamp

        return self
