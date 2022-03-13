# @date 2018-09-14
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Market data

import time
from typing import Union, Tuple, List, Set

from trader.position import Position
from common.utils import truncate, decimal_place


class Market(object):
    """
    Useful market data from instrument.
    @note Ofr is a synonym for ask.

    @todo available margins levels for IG but its complicated to manage
    @todo rollover fee buts its complicated too
    @todo leverage persistence
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
    CONTRACT_FUTURE = 2
    CONTRACT_OPTION = 3
    CONTRACT_WARRANT = 4
    CONTRACT_TURBO = 5

    TRADE_BUY_SELL = 1     # no margin no short, only buy (hold) and sell
    TRADE_ASSET = 1        # synonym for buy-sell/spot
    TRADE_SPOT = 1         # synonym for buy-sell/asset
    TRADE_MARGIN = 2       # margin, long and short
    TRADE_IND_MARGIN = 4   # indivisible position, margin, long and short
    TRADE_FIFO = 8         # position are closed in FIFO order
    TRADE_POSITION = 16    # individual position on the broker side

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

    __slots__ = '_market_id', '_symbol', '_trade', '_orders', \
                '_base', '_base_display', '_base_precision', \
                '_quote', '_quote_display', '_quote_precision', \
                '_expiry', '_is_open', '_contract_size', '_lot_size', '_base_exchange_rate', \
                '_value_per_pip', '_one_pip_means', '_margin_factor', '_size_limits', '_price_limits', \
                '_notional_limits', '_market_type', '_unit_type', '_contract_type', '_vol24h_base', '_vol24h_quote', \
                '_hedging', '_fees', '_fee_currency', '_previous', '_leverages', '_last_update_time', \
                '_bid', '_ask', '_last_mem', '_last_mem_timestamp'

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
        self._ask = 0.0

        self._last_mem = 0.0
        self._last_mem_timestamp = 0.0

    @property
    def market_id(self) -> str:
        return self._market_id

    @property
    def symbol(self) -> str:
        return self._symbol

    #
    # market trade type
    #

    @property
    def trade(self) -> int:
        return self._trade

    @trade.setter
    def trade(self, trade: int):
        self._trade = trade

    @property
    def has_spot(self) -> bool:
        return self._trade & Market.TRADE_SPOT == Market.TRADE_SPOT

    @property
    def has_margin(self) -> bool:
        return self._trade & Market.TRADE_MARGIN == Market.TRADE_MARGIN

    @property
    def indivisible_position(self) -> bool:
        return self._trade & Market.TRADE_IND_MARGIN == Market.TRADE_IND_MARGIN

    @property
    def fifo_position(self) -> bool:
        return self._trade & Market.TRADE_FIFO == Market.TRADE_FIFO

    @property
    def has_position(self) -> bool:
        return self._trade & Market.TRADE_POSITION == Market.TRADE_POSITION

    @property
    def orders(self) -> int:
        return self._orders

    @orders.setter
    def orders(self, flags: int):
        self._orders = flags

    def set_quote(self, symbol: str, display: str, precision: int = 8):
        self._quote = symbol
        self._quote_display = display
        self._quote_precision = precision

    @property
    def quote(self) -> str:
        return self._quote

    @property
    def quote_display(self) -> str:
        return self._quote_display

    @property
    def quote_precision(self) -> int:
        return self._quote_precision

    def set_base(self, symbol: str, display: str, precision: int = 8):
        self._base = symbol
        self._base_display = display
        self._base_precision = precision

    @property
    def base(self) -> str:
        return self._base

    @property
    def base_display(self) -> str:
        return self._base_display

    @property
    def base_precision(self) -> int:
        return self._base_precision

    @property
    def expiry(self) -> str:
        return self._expiry

    @expiry.setter
    def expiry(self, expiry: str):
        self._expiry = expiry

    @property
    def bid(self) -> float:
        return self._bid

    @bid.setter
    def bid(self, bid: float):
        self._bid = bid

    @property
    def market_bid(self) -> float:
        """Synonym for bid and compatibility with Market class."""
        return self._bid

    @property
    def spread(self) -> float:
        return self._ask - self._bid

    def market_spread(self) -> float:
        """Synonym for spread and compatibility with Market class."""
        return self._ask - self._bid

    @property
    def ask(self) -> float:
        return self._ask

    @ask.setter
    def ask(self, ask: float):
        self._ask = ask

    @property
    def market_ask(self) -> float:
        """Synonym for ask and compatibility with Market class."""
        return self._ask

    @property
    def price(self) -> float:
        return (self._bid + self._ask) * 0.5

    @property
    def market_price(self) -> float:
        """Synonym for price and compatibility with Market class."""
        return (self._bid + self._ask) * 0.5

    @property
    def last_update_time(self) -> float:
        return self._last_update_time

    @last_update_time.setter
    def last_update_time(self, last_update_time: float):
        self._last_update_time = last_update_time

    @property
    def is_open(self) -> bool:
        return self._is_open

    @is_open.setter
    def is_open(self, is_open: bool):
        self._is_open = is_open

    @property
    def contract_size(self) -> float:
        return self._contract_size

    @contract_size.setter
    def contract_size(self, contract_size: float):
        self._contract_size = contract_size

    @property
    def lot_size(self) -> float:
        return self._lot_size

    @lot_size.setter
    def lot_size(self, lot_size: float):
        self._lot_size = lot_size

    @property
    def base_exchange_rate(self) -> float:
        return self._base_exchange_rate

    @base_exchange_rate.setter
    def base_exchange_rate(self, base_exchange_rate: float):
        self._base_exchange_rate = base_exchange_rate

    @property
    def value_per_pip(self) -> float:
        return self._value_per_pip

    @value_per_pip.setter
    def value_per_pip(self, value_per_pip: float):
        self._value_per_pip = value_per_pip

    @property
    def one_pip_means(self) -> float:
        return self._one_pip_means

    @one_pip_means.setter
    def one_pip_means(self, one_pip_means: float):
        self._one_pip_means = one_pip_means

    @property
    def market_type(self) -> int:
        return self._market_type

    @market_type.setter
    def market_type(self, market_type: int):
        self._market_type = market_type

    @property
    def unit_type(self) -> int:
        return self._unit_type

    @unit_type.setter
    def unit_type(self, unit_type: int):
        self._unit_type = unit_type

    @property
    def contract_type(self) -> int:
        return self._contract_type
    
    @contract_type.setter
    def contract_type(self, contract_type: int):
        self._contract_type = contract_type

    @property
    def margin_factor(self) -> float:
        return self._margin_factor

    @margin_factor.setter
    def margin_factor(self, margin_factor: float):
        self._margin_factor = margin_factor

    @property
    def hedging(self) -> bool:
        return self._hedging
    
    @hedging.setter
    def hedging(self, hedging: bool):
        self._hedging = hedging

    #
    # fees
    #

    @property
    def maker_fee(self) -> float:
        return self._fees[0][0]

    @maker_fee.setter
    def maker_fee(self, maker_fee: float):
        self._fees[0][0] = maker_fee

    @property
    def taker_fee(self) -> float:
        return self._fees[1][0]

    @taker_fee.setter
    def taker_fee(self, taker_fee: float):
        self._fees[1][0] = taker_fee

    @property
    def maker_commission(self) -> float:
        return self._fees[0][1]

    @maker_commission.setter
    def maker_commission(self, commission: float):
        self._fees[0][1] = commission

    @property
    def taker_commission(self) -> float:
        return self._fees[1][1]

    @taker_commission.setter
    def taker_commission(self, commission: float):
        self._fees[1][1] = commission

    @property
    def fee_currency(self) -> str:
        return self._fee_currency

    @fee_currency.setter
    def fee_currency(self, currency: str):
        self._fee_currency = currency

    #
    # limits
    #

    @property
    def size_limits(self) -> Tuple[float, float, float, float]:
        return self._size_limits

    @property
    def min_size(self) -> float:
        return self._size_limits[0]

    @property
    def max_size(self) -> float:
        return self._size_limits[1]

    @property
    def step_size(self) -> float:
        return self._size_limits[2]

    @property
    def size_precision(self) -> float:
        return self._size_limits[3]

    @property
    def notional_limits(self) -> Tuple[float, float, float, float]:
        return self._notional_limits

    @property
    def min_notional(self) -> float:
        return self._notional_limits[0]

    @property
    def max_notional(self) -> float:
        return self._notional_limits[1]

    @property
    def step_notional(self) -> float:
        return self._notional_limits[2]

    @property
    def notional_precision(self) -> float:
        return self._notional_limits[3]

    @property
    def price_limits(self) -> Tuple[float, float, float, float]:
        return self._price_limits

    @property
    def min_price(self) -> float:
        return self._price_limits[0]

    @property
    def max_price(self) -> float:
        return self._price_limits[1]

    @property
    def step_price(self) -> float:
        return self._price_limits[2]

    @property
    def tick_price(self) -> float:
        return self._price_limits[2]

    @property
    def price_precision(self) -> float:
        return self._price_limits[3]

    @property
    def min_leverage(self) -> float:
        return min(self._leverages)
    
    @property
    def max_leverage(self) -> float:
        return max(self._leverages)

    @property
    def leverages(self) -> Tuple[float]:
        return self._leverages

    def set_size_limits(self, min_size: float, max_size: float, step_size: float):
        size_precision = max(0, decimal_place(step_size) if step_size > 0 else 0)
        self._size_limits = (min_size, max_size, step_size, size_precision)

    def set_notional_limits(self, min_notional: float, max_notional: float, step_notional: float):
        notional_precision = max(0, decimal_place(step_notional) if step_notional > 0 else 0)
        self._notional_limits = (min_notional, max_notional, step_notional, notional_precision)

    def set_price_limits(self, min_price: float, max_price: float, step_price: float):
        price_precision = max(0, decimal_place(step_price) if step_price > 0 else 0)
        self._price_limits = (min_price, max_price, step_price, price_precision)

    def set_leverages(self, leverages: Union[Tuple, List, Set]):
        self._leverages = tuple(leverages)

    #
    # volume
    #

    @property
    def vol24h_base(self) -> float:
        return self._vol24h_base
    
    @property
    def vol24h_quote(self) -> float:
        return self._vol24h_quote
    
    @vol24h_base.setter
    def vol24h_base(self, vol: float):
        self._vol24h_base = vol

    @vol24h_quote.setter
    def vol24h_quote(self, vol: float):
        self._vol24h_quote = vol

    #
    # helpers
    #

    def open_exec_price(self, direction: int) -> float:
        """
        Return the execution price if an order open a position.
        It depend of the direction of the order and the market bid/ask prices.
        If position is long, then returns the market ask price.
        If position is short, then returns the market bid price.
        """
        if direction == Position.LONG:
            return self._ask
        elif direction == Position.SHORT:
            return self._bid
        else:
            return self._ask

    def close_exec_price(self, direction: int) -> float:
        """
        Return the execution price if an order/position is closing.
        It depend of the direction of the order and the market bid/ask prices.
        If position is long, then returns the market bid price.
        If position is short, then returns the market ask price.
        """
        if direction == Position.LONG:
            return self._bid
        elif direction == Position.SHORT:
            return self._ask
        else:
            return self._bid

    #
    # format/adjust
    #

    def adjust_price(self, price: float) -> float:
        """
        Format the price according to the precision.
        """
        if price is None:
            price = 0.0

        precision = self._price_limits[3] or self._quote_precision
        if not precision:
            precision = decimal_place(self.value_per_pip) or 8

        tick_size = self._price_limits[2] or self.one_pip_means

        # adjusted price at precision and by step of pip meaning
        return truncate(round(price / tick_size) * tick_size, precision)

    def format_base_price(self, price: float) -> str:
        """
        Format the base price according to its precision.
        """
        if price is None:
            price = 0.0

        precision = self._base_precision
        if not precision:
            precision = decimal_place(self.one_pip_means) or 8

        tick_size = self.one_pip_means or 1.0

        adjusted_price = truncate(round(price / tick_size) * tick_size, precision)
        formatted_price = "{:0.0{}f}".format(adjusted_price, precision)

        # remove trailing 0s and dot
        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        return formatted_price

    def format_price(self, price: float) -> str:
        """
        Format the price according to its precision.
        """
        if price is None:
            price = 0.0

        precision = self._price_limits[3] or self._quote_precision
        if not precision:
            precision = decimal_place(self.value_per_pip) or 8

        tick_size = self._price_limits[2] or self.one_pip_means

        # adjusted price at precision and by step of tick size
        adjusted_price = truncate(round(price / tick_size) * tick_size, precision)
        formatted_price = "{:0.0{}f}".format(adjusted_price, precision)

        # remove trailing 0s and dot
        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        return formatted_price

    def format_spread(self, spread: float, shifted: bool = False) -> str:
        """
        Format the spread according to the precision.
        @param spread: float Spread value
        @param shifted: bool Shift the spread value by power of 10 based on the tick size.
        @return str Formatted spread
        """
        if spread is None:
            spread = 0.0

        precision = self._price_limits[3] or self._quote_precision

        if not precision:
            # quote use value per pip
            precision = decimal_place(self.value_per_pip)

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

        # remove trailing 0s and dot
        if '.' in formatted_spread:
            formatted_spread = formatted_spread.rstrip('0').rstrip('.')

        return formatted_spread

    def adjust_quantity(self, quantity: float, min_is_zero: bool = True) -> float:
        """
        From quantity return the floor tradeable quantity according to min, max and rounded to step size.
        To make a precise value for trade use format_value from this returned value.

        @param quantity float Quantity to adjust
        @param min_is_zero boolean Default True. If quantity is lesser than min returns 0 else return min size.
        """
        if quantity is None:
            quantity = 0.0

        if self.min_size > 0.0 and quantity < self.min_size:
            if min_is_zero:
                return 0.0

            return self.min_size

        if 0.0 < self.max_size < quantity:
            return self.max_size

        if self.step_size > 0:
            precision = self._size_limits[3]
            inv_step_size = 1.0 / self.step_size

            # return max(round(int(quantity / self.step_size) * self.step_size, precision), self.min_size)
            # return max(round(self.step_size * round(quantity / self.step_size), precision), self.min_size)
            # return max(round(self.step_size * math.floor(quantity / self.step_size), precision), self.min_size)
            return max(truncate(round(quantity * inv_step_size) * self.step_size, precision), self.min_size)

        return quantity

    def format_quantity(self, quantity: float) -> str:
        """
        Return a quantity as str according to the precision of the step size.
        """
        if quantity is None:
            quantity = 0.0

        precision = self._size_limits[3] or self._quote_precision
        qty = "{:0.0{}f}".format(truncate(quantity, precision), precision)

        if '.' in qty:
            qty = qty.rstrip('0').rstrip('.')

        return qty

    #
    # ticks local history cache
    #

    @property
    def last_mem(self) -> float:
        """Last memorised price for comparison"""
        return self._last_mem

    @property
    def last_mem_timestamp(self) -> float:
        """Last memorised price for comparison"""
        return self._last_mem_timestamp

    def mem_set(self):
        self._last_mem = (self._bid + self._ask) * 0.5
        self._last_mem_timestamp = time.time()

    def push_price(self):
        """
        Push the last bid/ask price, base exchange rate and timestamp.
        Keep only TICK_PRICE_TIMEOUT of samples in memory.
        """
        while self._previous and (self._last_update_time - self._previous[0][0]) > self.TICK_PRICE_TIMEOUT:
            self._previous.pop(0)

        self._previous.append((
            self._last_update_time,
            self._bid,
            self._ask,
            self._base_exchange_rate))

        if not self._last_mem:
            self.mem_set()

    def recent_price(self, timestamp: float) -> Union[float, None]:
        """
        One minute ticks price history.
        @return Price at timestamp or None.

        @todo Could use a dichotomy search.
        """
        if self._previous:
            if self._previous[0][0] > timestamp:
                return None

            for prev in self._previous:
                if timestamp >= prev[0]:
                    return (prev[1] + prev[2]) * 0.5

        return None

    def recent(self, timestamp: float) -> Union[float, None]:
        """
        One minute ticks price history.
        @return tuple(timestamp, bid, ask, base-exchange-rate) or None

        @todo Could use a dichotomy search.
        """
        if self._previous:
            if self._previous[0][0] > timestamp:
                return None

            for prev in self._previous:
                if timestamp >= prev[0]:
                    return prev

        return None

    def previous(self, position: int = -1) -> Union[float, None]:
        """
        One minute ticks price history, return the previous entry.
        @return tuple(timestamp, bid, ask, base-exchange-rate) or None
        """
        if 0 > position >= -len(self._previous):
            return self._previous[position]

        return None

    def previous_spread(self) -> Union[float, None]:
        """
        One minute ticks price history, return the previous entry spread.
        @return float spread or None
        """
        return (self._previous[-1][2] - self._previous[-1][1]) if self._previous else None

    #
    # helpers
    #

    def effective_cost(self, quantity: float, price: float) -> float:
        """
        Effective cost, not using the margin factor, for a quantity at specific price.
        In contracts size, the price has no effect.
        """
        if self._unit_type == Market.UNIT_AMOUNT:
            return quantity * (self._lot_size * self._contract_size) * price  # in quote currency
        elif self._unit_type == Market.UNIT_CONTRACTS:
            return quantity * (self._lot_size * self._contract_size / self._value_per_pip * price)
        elif self._unit_type == Market.UNIT_SHARES:
            return quantity * price  # in quote currency
        else:
            return quantity * (self._lot_size * self._contract_size) * price  # in quote currency

    def margin_cost(self, quantity: float, price: float) -> float:
        """
        Cost in margin, using the margin factor, for a quantity at specific price.
        In contracts size, the price has no effect.
        """
        if self._unit_type == Market.UNIT_AMOUNT:
            realized_position_cost = quantity * (self._lot_size * self._contract_size) * price  # in quote currency
        elif self._unit_type == Market.UNIT_CONTRACTS:
            realized_position_cost = quantity * (self._lot_size * self._contract_size / self._value_per_pip * price)
        elif self._unit_type == Market.UNIT_SHARES:
            realized_position_cost = quantity * price  # in quote currency
        else:
            realized_position_cost = quantity * (self._lot_size * self._contract_size) * price  # in quote currency

        return realized_position_cost * self._margin_factor / self._base_exchange_rate  # in account currency

    def clamp_leverage(self, leverage: float) -> float:
        low = min(self._leverages)
        high = max(self._leverages)

        if leverage < low:
            leverage = low
        elif leverage > high:
            leverage = high

        # if leverage not in self._leverages:
        # @todo or to a fixed value

        return leverage

    def unit_type_str(self) -> str:
        if self._unit_type == Market.UNIT_AMOUNT:
            return "amount"
        elif self._unit_type == Market.UNIT_CONTRACTS:
            return "contracts"
        elif self._unit_type == Market.UNIT_SHARES:
            return "shares"

        return "undefined"

    def market_type_str(self) -> str:
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

    def contract_type_str(self) -> str:
        if self._contract_type == Market.CONTRACT_SPOT:
            return "spot"
        elif self._contract_type == Market.CONTRACT_CFD:
            return "cfd"
        elif self._contract_type == Market.CONTRACT_FUTURE:
            return "future"
        elif self._contract_type == Market.CONTRACT_OPTION:
            return "option"
        elif self._contract_type == Market.CONTRACT_WARRANT:
            return "warrant"
        elif self._contract_type == Market.CONTRACT_TURBO:
            return "turbo"

        return "undefined"

    #
    # persistence
    #

    def dumps(self) -> dict:
        return {}

    def loads(self, data: dict):
        pass
