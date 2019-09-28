# @date 2018-10-06
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Simple average price indicator using candle data.

from strategy.indicator.indicator import Indicator
from strategy.indicator.utils import down_sample

import numpy as np


class PriceIndicator(Indicator):
    """
    Simple average price indicator using candle data.
    Always use the average of bid and ofr prices.
    """

    PRICE_CLOSE = 0   # return close price
    PRICE_HLC3 = 1    # return (H+L+C)/3
    PRICE_OHLC4 = 2   # return (O+H+L+C)/4

    __slots__ = '_method', '_prev', '_last', '_prices', '_min', '_max', '_open', '_high', '_low', '_close', '_timestamp'

    @classmethod
    def indicator_type(cls):
        return Indicator.TYPE_TREND

    @classmethod
    def indicator_class(cls):
        return Indicator.CLS_OSCILLATOR

    def __init__(self, timeframe, method=PRICE_CLOSE):
        super().__init__("price", timeframe)

        self._method = method

        self._prev = 0.0
        self._last = 0.0
        self._prices = np.array([])

        self._min = 0
        self._max = 0

        self._open = np.array([])
        self._high = np.array([])
        self._low = np.array([])
        self._close = np.array([])

        self._timestamp = np.array([])

    @property
    def last(self):
        return self._last

    @property
    def prev(self):
        return self._prev

    @property
    def prices(self):
        return self._prices

    @property
    def open(self):
        return self._open

    @property
    def high(self):
        return self._high

    @property
    def low(self):
        return self._low
    
    @property
    def close(self):
        return self._close

    @property
    def timestamp(self):
        return self._timestamp

    @property
    def min(self):
        return self._min
    
    @property
    def max(self):
        return self._max

    @staticmethod
    def Price(method, data):
        prices = []

        if method == PriceIndicator.PRICE_CLOSE:
            # average of bid/ofr close price
            prices = np.array([x.close for x in data])

        elif method == PriceIndicator.PRICE_HLC3:
            h_prices = np.array([x.high for x in data])
            l_prices = np.array([x.low for x in data])
            c_prices = np.array([x.close for x in data])
            
            prices = (h_prices + l_prices + c_prices) / 3.0

        elif method == PriceIndicator.PRICE_OHLC4:
            o_prices = np.array([x.open for x in data])
            h_prices = np.array([x.high for x in data])
            l_prices = np.array([x.low for x in data])
            c_prices = np.array([x.close for x in data])

            prices = (o_prices + h_prices + l_prices + c_prices) / 4.0

        return prices

    @staticmethod
    def Price_sf(method, data, step=1, filtering=False):
        prices = np.array([])

        if method == PriceIndicator.PRICE_CLOSE:
            # average of bid/ofr close price
            c_prices = [x.close for x in data]

            # t_subdata = range(0,len(data),step)
            c_sub_data = down_sample(c_prices, step) if filtering else np.array(c_prices[::step])

            # @todo interpolate sub_data
            prices = c_sub_data

        elif method == PriceIndicator.PRICE_HLC3:
            h_prices = [x.high for x in data]
            l_prices = [x.low for x in data]
            c_prices = [x.close for x in data]

            # t_subdata = range(0,len(data),step)
            h_sub_data = down_sample(h_prices, step) if filtering else np.array(h_prices[::step])
            l_sub_data = down_sample(l_prices, step) if filtering else np.array(l_prices[::step])
            c_sub_data = down_sample(c_prices, step) if filtering else np.array(c_prices[::step])

            # @todo interpolate sub_data
            prices = (h_sub_data + l_sub_data + c_sub_data) / 3.0

        elif method == PriceIndicator.PRICE_OHLC4:
            o_prices = [x.open for x in data]
            h_prices = [x.high for x in data]
            l_prices = [x.low for x in data]
            c_prices = [x.close for x in data]

            # t_subdata = range(0,len(data),step)
            o_sub_data = down_sample(o_prices, step) if filtering else np.array(o_prices[::step])
            h_sub_data = down_sample(h_prices, step) if filtering else np.array(h_prices[::step])
            l_sub_data = down_sample(l_prices, step) if filtering else np.array(l_prices[::step])
            c_sub_data = down_sample(c_prices, step) if filtering else np.array(c_prices[::step])

            # @todo interpolate sub_data
            prices = (o_sub_data + h_sub_data + l_sub_data + c_sub_data) / 4.0

        return prices

    def compute(self, timestamp, candles):
        # @todo could optimize with AVGPRICE, MEDPRICE, TYPPRICE
        self._prev = self._last

        # price = PriceIndicator.Price(self._method, candles)  # , self._step, self._filtering)
        if self._method == PriceIndicator.PRICE_CLOSE:
            # average of bid/ofr close price
            self._prices = np.array([x.close for x in candles])

            self._open = np.array([x.open for x in candles])
            self._high = np.array([x.high for x in candles])
            self._low = np.array([x.low for x in candles])
            self._close = np.array(self._prices)

        elif self._method == PriceIndicator.PRICE_HLC3:
            h_prices = np.array([x.high for x in candles])
            l_prices = np.array([x.low for x in candles])
            c_prices = np.array([x.close for x in candles])

            self._prices = (h_prices + l_prices + c_prices) / 3.0

            self._open = np.array([x.open for x in candles])
            self._high = h_prices
            self._low = l_prices
            self._close = c_prices

        elif self._method == PriceIndicator.PRICE_OHLC4:
            o_prices = np.array([x.open for x in candles])
            h_prices = np.array([x.high for x in candles])
            l_prices = np.array([x.low for x in candles])
            c_prices = np.array([x.close for x in candles])

            self._prices = (o_prices + h_prices + l_prices + c_prices) / 4.0

            self._open = o_prices
            self._high = h_prices
            self._low = l_prices
            self._close = c_prices            

        # if self._open[-1] > 5000 and self.timeframe == 86400:
        #     print(">-2 ", candles[-2], ">-1 ", candles[-1])

        # related timestamps
        self._timestamp = np.array([x.timestamp for x in candles])

        # low/high
        self._min = min(self._prices)
        self._max = max(self._prices)

        self._last = self._prices[-1]
        self._last_timestamp = timestamp

        return self._prices
