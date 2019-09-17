# @date 2018-09-14
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Market data

import time
import math

from trader.position import Position
from common.utils import truncate, decimal_place


class Market(object):
    """
    Useful market data from instrument.
    @note Ofr is a synonym for ask.

    @todo availables margins levels for IG but its complicated to manage
    @todo rollover fee buts its complicated too
    @todo levarage persistance
    @todo base and quote could be struct with symbol, display, precision, vol24h
    @todo message market (out only)
    """

    TICK_PRICE_TIMEOUT = 60  # in seconds

    TYPE_UNKNOWN = 0
    TYPE_CURRENCY = 1
    TYPE_COMMODITY = 2
    TYPE_INDICE = 3
    TYPE_STOCK = 4
    TYPE_RATE = 5
    TYPE_SECTOR = 6
    TYPE_CRYPTO = 7

    UNIT_AMOUNT = 0
    UNIT_CONTRACTS = 1
    UNIT_SHARES = 2

    CONTRACT_SPOT = 0
    CONTRACT_CFD = 1
    CONTRACT_FUTUR = 2
    CONTRACT_OPTION = 3
    CONTRACT_WARRANT = 4
    CONTRACT_TURBO = 5

    TRADE_BUY_SELL = 1     # no margin no short, only buy (hold) and sell
    TRADE_ASSET = 1        # synonym for buy-sell/spot
    TRADE_SPOT = 1         # synonym for buy-sell/asset
    TRADE_MARGIN = 2       # margin, long and short
    TRADE_IND_MARGIN = 4   # indivisible position, margin, long and short
    TRADE_FIFO = 8         # position are closed in FIFO order

    ORDER_MARKET = 0
    ORDER_LIMIT = 1
    ORDER_STOP_MARKET = 2
    ORDER_STOP_LIMIT = 4
    ORDER_TAKE_PROFIT_MARKET = 8
    ORDER_TAKE_PROFIT_LIMIT = 16
    ORDER_ONE_CANCEL_OTHER = 32
    ORDER_ALL = 32-1

    # Standard month code
    MONTH_CODE = {
        'F': 1,  # january
        'G': 2,
        'H': 3,
        'J': 4,
        'K': 5,
        'M': 6,
        'N': 7,
        'Q': 8,
        'U': 9,
        'V': 10,
        'X': 11,
        'Z': 12
    }

    __slots__ = '_market_id', '_symbol', '_trade', '_orders', '_base', '_base_display', '_base_precision', '_quote', '_quote_display', '_quote_precision', \
                '_expiry', '_is_open', '_contract_size', '_lot_size', '_base_exchange_rate', '_value_per_pip', '_one_pip_means', '_margin_factor', \
                '_size_limits', '_price_limits', '_notional_limits', '_market_type', '_unit_type', '_contract_type', '_vol24h_base', '_vol24h_quote', \
                '_hedging', '_fees', '_fee_currency', '_previous', '_leverages', '_last_update_time', '_bid', '_ofr'

    def __init__(self, market_id, symbol):
        self._market_id = market_id
        self._symbol = symbol

        self._trade = 0
        self._orders = Market.ORDER_ALL

        self._base = ""
        self._base_display = ""     
        self._base_precision = 8   # precision of the decimal on the base

        self._quote = "USD"
        self._quote_display = "$"
        self._quote_precision = 8  # on the quote

        self._expiry = None
        self._is_open = True

        self._contract_size = 1.0
        self._lot_size = 1.0
        self._base_exchange_rate = 1.0
        self._value_per_pip = 1.0
        self._one_pip_means = 1.0
        self._margin_factor = 1.0  # 1.0 / leverage

        self._size_limits = (0.0, 0.0, 0.0, 0)
        self._price_limits = (0.0, 0.0, 0.0, 0)
        self._notional_limits = (0.0, 0.0, 0.0, 0)

        self._market_type = Market.TYPE_UNKNOWN
        self._unit_type = Market.UNIT_CONTRACTS
        self._contract_type = Market.CONTRACT_SPOT

        self._vol24h_base = None
        self._vol24h_quote = None

        self._hedging = False

        self._fees = ([0.0, 0.0], [0.0, 0.0])  # maker 0, taker 1 => fee 0, commission 1
        self._fee_currency = ""

        self._previous = []

        self._leverages = (1,)  # allowed leverages levels

        self._last_update_time = 0.0

        self._bid = 0.0
        self._ofr = 0.0

    @property
    def market_id(self):
        return self._market_id

    @property
    def symbol(self):
        return self._symbol

    #
    # market trade type
    #

    @property
    def trade(self):
        return self._trade

    @trade.setter
    def trade(self, trade):
        self._trade = trade

    @property
    def has_spot(self):
        return self._trade & Market.TRADE_SPOT == Market.TRADE_SPOT

    @property
    def has_margin(self):
        return self._trade & Market.TRADE_MARGIN == Market.TRADE_MARGIN

    @property
    def indivisible_position(self):
        return self._trade & Market.TRADE_IND_MARGIN == Market.TRADE_IND_MARGIN

    @property
    def fifo_position(self):
        return self._trade & Market.TRADE_FIFO == Market.TRADE_FIFO

    @property
    def orders(self):
        return self._orders

    @orders.setter
    def orders(self, flags):
        self._orders = flags

    def set_quote(self, symbol, display, precision=8):
        self._quote = symbol
        self._quote_display = display
        self._quote_precision = precision

    @property
    def quote(self):
        return self._quote

    @property
    def quote_display(self):
        return self._quote_display

    @property
    def quote_precision(self):
        return self._quote_precision

    def set_base(self, symbol, display, precision=8):
        self._base = symbol
        self._base_display = display
        self._base_precision = precision

    @property
    def base(self):
        return self._base

    @property
    def base_display(self):
        return self._base_display

    @property
    def base_precision(self):
        return self._base_precision

    @property
    def expiry(self):
        return self._expiry

    @expiry.setter
    def expiry(self, expiry):
        self._expiry = expiry

    @property
    def bid(self):
        return self._bid

    @bid.setter
    def bid(self, bid):
        self._bid = bid
    
    @property
    def spread(self):
        return self._ofr - self._bid

    @property
    def ofr(self):
        return self._ofr

    @ofr.setter
    def ofr(self, ofr):
        self._ofr = ofr

    @property
    def price(self):
        return (self._bid + self._ofr) * 0.5
    
    @property
    def last_update_time(self):
        return self._last_update_time

    @last_update_time.setter
    def last_update_time(self, last_update_time):
        self._last_update_time = last_update_time

    @property
    def is_open(self):
        return self._is_open

    @is_open.setter
    def is_open(self, is_open):
        self._is_open = is_open

    @property
    def contract_size(self):
        return self._contract_size

    @contract_size.setter
    def contract_size(self, contract_size):
        self._contract_size = contract_size

    @property
    def lot_size(self):
        return self._lot_size

    @lot_size.setter
    def lot_size(self, lot_size):
        self._lot_size = lot_size

    @property
    def base_exchange_rate(self):
        return self._base_exchange_rate

    @base_exchange_rate.setter
    def base_exchange_rate(self, base_exchange_rate):
        self._base_exchange_rate = base_exchange_rate

    @property
    def value_per_pip(self):
        return self._value_per_pip

    @value_per_pip.setter
    def value_per_pip(self, value_per_pip):
        self._value_per_pip = value_per_pip

    @property
    def one_pip_means(self):
        return self._one_pip_means

    @one_pip_means.setter
    def one_pip_means(self, one_pip_means):
        self._one_pip_means = one_pip_means

    @property
    def market_type(self):
        return self._market_type

    @market_type.setter
    def market_type(self, market_type):
        self._market_type = market_type

    @property
    def unit_type(self):
        return self._unit_type

    @unit_type.setter
    def unit_type(self, unit_type):
        self._unit_type = unit_type

    @property
    def contract_type(self):
        return self._contract_type
    
    @contract_type.setter
    def contract_type(self, contract_type):
        self._contract_type = contract_type

    @property
    def margin_factor(self):
        return self._margin_factor

    @margin_factor.setter
    def margin_factor(self, margin_factor):
        self._margin_factor = margin_factor

    @property
    def hedging(self):
        return self._hedging
    
    @hedging.setter
    def hedging(self, hedging):
        self._hedging = hedging

    #
    # fees
    #

    @property
    def maker_fee(self):
        return self._fees[0][0]

    @maker_fee.setter
    def maker_fee(self, maker_fee):
        self._fees[0][0] = maker_fee

    @property
    def taker_fee(self):
        return self._fees[1][0]

    @taker_fee.setter
    def taker_fee(self, taker_fee):
        self._fees[1][0] = taker_fee

    @property
    def maker_commission(self):
        return self._fees[0][1]

    @maker_commission.setter
    def maker_commission(self, commission):
        self._fees[0][1] = commission

    @property
    def taker_commission(self):
        return self._fees[1][1]

    @taker_commission.setter
    def taker_commission(self, commission):
        self._fees[1][1] = commission

    @property
    def fee_currency(self):
        return self._fee_currency

    @fee_currency.setter
    def fee_currency(self, currency):
        self._fee_currency = currency

    #
    # limits
    #

    @property
    def min_size(self):
        return self._size_limits[0]

    @property
    def max_size(self):
        return self._size_limits[1]

    @property
    def step_size(self):
        return self._size_limits[2]

    @property
    def min_notional(self):
        return self._notional_limits[0]

    @property
    def max_notional(self):
        return self._notional_limits[1]

    @property
    def step_notional(self):
        return self._notional_limits[2]

    @property
    def min_price(self):
        return self._price_limits[0]

    @property
    def max_price(self):
        return self._price_limits[1]

    @property
    def step_price(self):
        return self._price_limits[2]

    @property
    def tick_price(self):
        return self._price_limits[2]

    @property
    def min_leverage(self):
        return min(self._leverages)
    
    @property
    def max_leverage(self):
        return max(self._leverages)

    @property
    def leverages(self):
        return self._leverages

    def set_size_limits(self, min_size, max_size, step_size):
        size_precision = decimal_place(step_size) if step_size > 0 else 0
        self._size_limits = (min_size, max_size, step_size, size_precision)

    def set_notional_limits(self, min_notional, max_notional, step_notional):
        notional_precision = decimal_place(step_notional) if step_notional > 0 else 0
        self._notional_limits = (min_notional, max_notional, step_notional, notional_precision)

    def set_price_limits(self, min_price, max_price, step_price):
        price_precision = decimal_place(step_price) if step_price > 0 else 0
        self._price_limits = (min_price, max_price, step_price, price_precision)

    def set_leverages(self, leverages):
        self._leverages = tuple(leverages)

    #
    # volume
    #

    @property
    def vol24h_base(self):
        return self._vol24h_base
    
    @property
    def vol24h_quote(self):
        return self._vol24h_quote
    
    @vol24h_base.setter
    def vol24h_base(self, vol):
        self._vol24h_base = vol

    @vol24h_quote.setter
    def vol24h_quote(self, vol):
        self._vol24h_quote = vol

    #
    # helpers
    #

    def open_exec_price(self, direction):
        """
        Return the execution price if an order open a position.
        It depend of the direction of the order and the market bid/ofr prices.
        If position is long, then returns the market ofr price.
        If position is short, then returns the market bid price.
        """
        if direction == Position.LONG:
            return self._ofr
        elif direction == Position.SHORT:
            return self._bid
        else:
            return self._ofr

    def close_exec_price(self, direction):
        """
        Return the execution price if an order/position is closing.
        It depend of the direction of the order and the market bid/ofr prices.
        If position is long, then returns the market bid price.
        If position is short, then returns the market ofr price.
        """
        if direction == Position.LONG:
            return self._bid
        elif direction == Position.SHORT:
            return self._ofr
        else:
            return self._bid

    #
    # format/adjust
    #

    def adjust_price(self, price):
        """
        Format the price according to the precision.
        @param use_quote True use quote display or quote, False base, None no symbol only price.
        """
        precision = self._price_limits[3] or self._quote_precision
        if not precision:
            precision = decimal_place(self.value_per_pip) or 8

        tick_size = self._price_limits[2] or self.one_pip_means

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / tick_size) * tick_size, precision)

    def format_base_price(self, price):
        """
        Format the base price according to its precision.
        """
        precision = self._base_precision
        if not precision:
            precision = decimal_place(self.one_pip_means) or 8

        tick_size = self.one_pip_means or 1.0

        adjusted_price = truncate(round(price / tick_size) * tick_size, precision)
        formatted_price = "{:0.0{}f}".format(adjusted_price, precision)

        # remove tailing 0s and dot
        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        return formatted_price

    def format_price(self, price):
        """
        Format the price according to its precision.
        """
        precision = self._price_limits[3] or self._quote_precision
        if not precision:
            precision = decimal_place(self.value_per_pip) or 8

        tick_size = self._price_limits[2] or self.one_pip_means

        # adjusted price at precision and by step of tick size
        adjusted_price = truncate(round(price / tick_size) * tick_size, precision)
        formatted_price = "{:0.0{}f}".format(adjusted_price, precision)

        # remove tailing 0s and dot
        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        return formatted_price

    def format_spread(self, spread, shifted=False):
        """
        Format the spread according to the precision.
        @param shifted Shift the spread value by power of 10 based on the tick size.
        """
        precision = self._price_limits[3] or self._quote_precision

        if not precision:
            if use_quote:
                # quote use value per pip
                precision = decimal_place(self.value_per_pip)
            else:
                # base use one pip mean alias tick size
                precision = decimal_place(self.one_pip_means)

            if not precision:
                precision = 8

        tick_size = self._price_limits[2] or self.one_pip_means

        # adjusted spread at precision and by step of pip meaning
        # adjusted_price = truncate(round(spread / tick_size) * tick_size, precision)
        if shifted:
            adjusted_spread = spread * 10**precision
        else:
            adjusted_spread = spread

        formatted_spread = "{:0.0{}f}".format(adjusted_spread, precision)

        # remove tailing 0s and dot
        if '.' in formatted_spread:
            formatted_spread = formatted_spread.rstrip('0').rstrip('.')

        return formatted_spread

    def adjust_quantity(self, quantity, min_is_zero=True):
        """
        From quantity return the floor tradable quantity according to min, max and rounded to step size.
        To make a precise value for trade use format_value from this returned value.

        @param quantity float Quantity to adjust
        @param min_is_zero boolean Default True. If quantity is lesser than min returns 0 else return min size.
        """
        if self.min_size > 0.0 and quantity < self.min_size:
            if min_is_zero:
                return 0.0

            return self.min_size

        if self.max_size > 0.0 and quantity > self.max_size:
            return self.max_size

        if self.step_size > 0:
            precision = self._size_limits[3]
            return max(round(self.step_size * round(quantity / self.step_size), precision), self.min_size)

        # if self.step_size > 0.0:
        #     precision = -int(math.log10(self.step_size))
        #     # return max(round(int(quantity / self.step_size) * self.step_size, precision), self.min_size)
        #     return max(round(self.step_size * round(quantity / self.step_size), precision), self.min_size)

        return quantity

    def format_quantity(self, quantity):
        """
        Return a quantity as str according to the precision of the step size.
        """
        precision = self._size_limits[3] or self._quote_precision
        qty = "{:0.0{}f}".format(truncate(quantity, precision), precision)

        if '.' in qty:
            qty = qty.rstrip('0').rstrip('.')

        return qty

    #
    # ticks local history cache
    #

    def push_price(self):
        """
        Push the last bid/ofr price, base exchange rate and timestamp.
        Keep only TICK_PRICE_TIMEOUT of samples in memory.
        """
        while self._previous and (self._last_update_time - self._previous[0][0]) > self.TICK_PRICE_TIMEOUT:
            self._previous.pop(0)

        self._previous.append((
            self._last_update_time,
            self._bid,
            self._ofr,
            self._base_exchange_rate))

    def recent_price(self, timestamp):
        """
        One minute ticks price history.
        @return Price at timestamp or None.

        @todo Could use a dichotomic search.
        """
        if self._previous:
            if self._previous[0][0] > timestamp:
                return None

            for l in self._previous:
                if timestamp >= l[0]:
                    return (l[1] + l[2]) * 0.5

        return None

    def recent(self, timestamp):
        """
        One minute ticks price history.
        @return tuple(timestamp, bid, ofr, base-exchange-rate) or None

        @todo Could use a dichotomic search.
        """
        if self._previous:
            if self._previous[0][0] > timestamp:
                return None

            for l in self._previous:
                if timestamp >= l[0]:
                    return l

        return None

    def previous(self):
        """
        One minute ticks price history, return the previous entry.
        @return tuple(timestamp, bid, ofr, base-exchange-rate) or None
        """
        return self._previous[-1] if self._previous else None

    def previous_spread(self):
        """
        One minute ticks price history, return the previous entry spread.
        @return float spread or None
        """
        return (self._previous[-1][2] - self._previous[-1][1]) if self._previous else None

    #
    # helpers
    #

    def margin_cost(self, quantity):
        realized_position_cost = quantity * (self._lot_size * self._contract_size)  # in base currency
        margin_cost = realized_position_cost * self._margin_factor / self._base_exchange_rate

        return margin_cost

    def clamp_leverage(self, leverage):
        return max(self._leverages, min(self.self._leverages, leverage))

    def unit_type_str(self):
        if self._unit_type == Market.UNIT_AMOUNT:
            return "amount"
        elif self._unit_type == Market.UNIT_CONTRACTS:
            return "contracts"
        elif self._unit_type == Market.UNIT_SHARES:
            return "shares"

        return "undefined"

    def market_type_str(self):
        if self._market_type == Market.TYPE_CURRENCY:
            return "currency"
        elif self._market_type == Market.TYPE_COMMODITY:
            return "commodity"
        elif self._market_type == Market.TYPE_INDICE:
            return "indice"
        elif self._market_type == Market.TYPE_STOCK:
            return "stock"
        elif self._market_type == Market.TYPE_RATE:
            return "rate"
        elif self._market_type == Market.TYPE_SECTOR:
            return "sector"
        elif self._market_type == Market.TYPE_CRYPTO:
            return "crypto"

        return "undefined"

    def contract_type_str(self):
        if self._contract_type == Market.CONTRACT_SPOT:
            return "spot"
        elif self._contract_type == Market.CONTRACT_CFD:
            return "cfd"
        elif self._contract_type == Market.CONTRACT_FUTUR:
            return "futur"
        elif self._contract_type == Market.CONTRACT_OPTION:
            return "option"
        elif self._contract_type == Market.CONTRACT_WARRANT:
            return "warrant"
        elif self._contract_type == Market.CONTRACT_TURBO:
            return "turbo"

        return "undefined"

    #
    # persistance
    #

    def dumps(self):
        return {}

    def loads(self, data):
        pass
