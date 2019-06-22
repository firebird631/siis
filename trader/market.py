# @date 2018-09-14
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Market data

import time
import math

from trader.position import Position
from common.utils import truncate


class Market(object):
    """
    Useful market data from instrument.
    @note Ofr is a synonym for ask.

    IG : https://labs.ig.com/rest-trading-api-reference/service-detail?id=528

    @todo availables margins levels (min, max... others level or step) but its complicated depending of the broker (BitMex, 1broker)
    @todo rollover fee buts the structure is complicated depending of the broker, so this should be an approximation of the rate
    @todo save maker/taker fee and commission into the DB
    @todo from watcher define if the market support or not hedging for each market (save it into DB)
    """

    ROLLOVER_TIME = 60  # in seconds

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

    TRADE_BUY_SELL = 0     # no margin no short, only buy (hold) and sell
    TRADE_ASSET = 0        # synonym for buy-sell/spot
    TRADE_SPOT = 0         # synonym for buy-sell/asset
    TRADE_MARGIN = 1       # margin, long and short
    TRADE_IND_MARGIN = 2   # indivisible position, margin, long and short

    # or could have a OrderPolicy because not everywhere same concepts
    ORDER_MARKET = 0
    ORDER_LIMIT = 1
    ORDER_STOP_MARKET = 2
    ORDER_STOP_LIMIT = 4
    ORDER_TAKE_PROFIT_MARKET = 8
    ORDER_TAKE_PROFIT_LIMIT = 16
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

    def __init__(self, market_id, symbol):
        self._market_id = market_id
        self._symbol = symbol

        self._trade = Market.TRADE_MARGIN
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

        self._min_size = 0.0
        self._max_size = 0.0
        self._step_size = 1.0
        self._min_notional = 0.0

        self._market_type = Market.TYPE_UNKNOWN
        self._unit_type = Market.UNIT_CONTRACTS

        self._bid = 0.0
        self._ofr = 0.0
        self._last_update_time = time.time()

        self._vol24h_base = None
        self._vol24h_quote = None

        self._hedging = False

        self._maker_fee = 0.0
        self._taker_fee = 0.0

        self._commission = 0.0

        self._previous = []

    @property
    def market_id(self):
        return self._market_id

    @property
    def symbol(self):
        return self._symbol

    @property
    def trade(self):
        return self._trade

    @trade.setter
    def trade(self, trade):
        self._trade = trade

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
    def margin_factor(self):
        return self._margin_factor

    @margin_factor.setter
    def margin_factor(self, margin_factor):
        self._margin_factor = margin_factor

    @property
    def hedging(self):
        return self._hedging
    
    @hedging.setter
    def hedging(self, is_hedging_supported):
        self._hedging = is_hedging_supported

    #
    # fees
    #

    @property
    def maker_fee(self):
        return self._maker_fee

    @maker_fee.setter
    def maker_fee(self, maker_fee):
        self._maker_fee = maker_fee

    @property
    def taker_fee(self):
        return self._taker_fee

    @taker_fee.setter
    def taker_fee(self, taker_fee):
        self._taker_fee = taker_fee

    @property
    def commission(self):
        return self._commission

    @commission.setter
    def commission(self, commission):
        self._commission = commission

    #
    # size
    #

    @property
    def min_size(self):
        return self._min_size

    @property
    def max_size(self):
        return self._max_size

    @property
    def step_size(self):
        return self._step_size

    @property
    def min_notional(self):
        return self._min_notional

    def set_size_limits(self, min_size, max_size, step_size, min_notional):
        self._min_size = min_size
        self._max_size = max_size
        self._step_size = step_size
        self._min_notional = min_notional

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
        if direction == Position.POSITION_LONG:
            return self._ofr
        elif direction == Position.POSITION_SHORT:
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
        if direction == Position.POSITION_LONG:
            return self._bid
        elif direction == Position.POSITION_SHORT:
            return self._ofr
        else:
            return self._bid

    def adjust_price(self, price, use_quote=True):
        """
        Format the price according to the precision.
        @param use_quote True use quote display or quote, False base, None no symbol only price.
        """
        if use_quote:
            precision = self._quote_precision
        else:
            precision = self._base_precision

        if not precision:
            if use_quote:
                # quote use value per pip
                precision = -int(math.log10(self.value_per_pip))
            else:
                # base use one pip mean alias tick size
                precision = -int(math.log10(self.one_pip_means))

            if not precision:
                precision = 8

        # adjusted price at precision and by step of pip meaning
        return truncate(int(truncate(price, precision) / self.one_pip_means) * self.one_pip_means, precision)

    def format_price(self, price, use_quote=True, display_symbol=False):
        """
        Format the price according to the precision.
        @param use_quote True use quote display or quote, False base, None no symbol only price.
        """
        if use_quote:
            precision = self._quote_precision
        else:
            precision = self._base_precision

        if not precision:
            if use_quote:
                # quote use value per pip
                precision = -int(math.log10(self.value_per_pip))
            else:
                # base use one pip mean alias tick size
                precision = -int(math.log10(self.one_pip_means))

            if not precision:
                precision = 8

        # adjusted price at precision and by step of pip meaning
        adjusted_price = truncate(int(truncate(price, precision) / self.one_pip_means) * self.one_pip_means, precision)
        formatted_price = "{:0.0{}f}".format(adjusted_price, precision)

        # remove tailing 0s and dot
        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        if not display_symbol:
            return formatted_price

        if use_quote:
            return "%s%s" % (formatted_price, self._quote_display or self._quote)
        else:
            return "%s%s" % (formatted_price, self._base_display or self._base)

    def adjust_quantity(self, quantity, min_is_zero=True):
        """
        From quantity return the floor tradable quantity according to min, max and rounded to step size.
        To make a precise value for trade use format_value from this returned value.

        @param quantity float Quantity to adjust
        @param min_is_zero boolean Default True. If quantity is lesser than min returns 0 else return min size.
        """
        if self._min_size > 0.0 and quantity < self._min_size:
            if min_is_zero:
                return 0.0

            return self._min_size

        if self._max_size > 0.0 and quantity > self._max_size:
            return self._max_size

        if self._step_size > 0.0:
            precision = -int(math.log10(self._step_size))
            # return max(round(int(quantity / self._step_size) * self._step_size, precision), self._min_size)
            return max(round(self._step_size * round(quantity / self._step_size), precision), self._min_size)

        return quantity

    def format_quantity(self, quantity):
        """
        Return a quantity as str according to the precision of the step size.
        """
        precision = -int(math.log10(self._step_size))
        qty = "{:0.0{}f}".format(truncate(quantity, precision), precision)

        if '.' in qty:
            qty = qty.rstrip('0').rstrip('.')

        return qty

    def store(self):
        """
        Store the last minute of ticks data.
        """
        for l in self._previous:
            if self._last_update_time - l['t'] > self.ROLLOVER_TIME:
                self._previous.pop(0)
            else:
                break

        self._previous.append({
            't': self._last_update_time,
            'b': self._bid,
            'o': self._ofr,
            'e': self._base_exchange_rate
        })

    def price_at(self, timestamp):
        """
        One minute ticks price history.
        @todo Could use a dichotomic search.
        @return Price at timestamp or None if not found.
        """
        for l in self._previous:
            if timestamp >= l['t']:
                return (l['b'] + l['o']) * 0.5

        return None

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

    def margin_cost(self, quantity):
        realized_position_cost = quantity * (self._lot_size * self._contract_size)  # in base currency
        margin_cost = realized_position_cost * self._margin_factor / self._base_exchange_rate

        return margin_cost
