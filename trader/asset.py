# @date 2018-10-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Trader asset

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from trader.trader import Trader
    from trader.market import Market

from common.utils import truncate


class Asset(object):
    """
    Asset define a symbol and a balance, with margin or not. It is initially created for
    use with binance.com but will be extended to any balance even for EUR or USD margin based broker,
    in such we would check the asset balance before opening a position.
    """

    __slots__ = '_trader', '_symbol', '_precision', '_locked', '_free', '_price', '_quote', \
                '_last_update_time', '_last_trade_id', '_market_ids', '_raw_profit_loss', '_raw_profit_loss_rate', \
                '_profit_loss', '_profit_loss_rate', '_profit_loss_market', '_profit_loss_market_rate'

    def __init__(self, trader: Trader, symbol: str, precision: int = 8):
        super().__init__()
        
        self._trader = trader
        self._symbol = symbol
        self._precision = precision  # price decimal place

        self._locked = 0.0  # currently locked quantity in orders
        self._free = 0.0    # free quantity for trading

        self._price = 0.0   # last updated average price
        self._quote = ""    # quote symbol

        self._last_update_time = 0.0
        self._last_trade_id = 0

        self._market_ids = []

        self._raw_profit_loss = 0.0
        self._raw_profit_loss_rate = 0.0

        self._profit_loss = 0.0
        self._profit_loss_rate = 0.0
        
        self._profit_loss_market = 0.0
        self._profit_loss_market_rate = 0.0

    @property
    def last_update_time(self) -> float:
        return self._last_update_time

    @property
    def last_trade_id(self) -> int:
        return self._last_trade_id
    
    @property
    def symbol(self) -> str:
        return self._symbol
    
    @property
    def trader(self) -> Trader:
        return self._trader

    @property
    def quantity(self) -> float:
        return round(self._locked + self._free, self._precision)

    @property
    def free(self) -> float:
        return self._free
    
    @property
    def locked(self) -> float:
        return self._locked
    
    @property
    def price(self) -> float:
        return self._price

    @property
    def quote(self) -> str:
        return self._quote

    @quote.setter
    def quote(self, quote: str):
        self._quote = quote

    @property
    def precision(self) -> int:
        return self._precision
    
    @precision.setter
    def precision(self, precision: int):
        self._precision = precision

    def set_quantity(self, locked: float, free: float):
        self._locked = locked
        self._free = free

        # reset profit/loss when zero
        if not locked and not free:
            self._profit_loss = 0.0
            self._profit_loss_rate = 0.0

            self._profit_loss_market = 0.0
            self._profit_loss_market_rate = 0.0

    def update_price(self, last_update_time: float, last_trade_id: int, price: float, quote: str):
        """
        Update entry price at time and last trade id.
        """
        if last_update_time:
            self._last_update_time = last_update_time

        if last_trade_id:
            self._last_trade_id = last_trade_id

        if price:
            self._price = price

        if quote:
            self._quote = quote

    def add_market_id(self, market_id: str, preferred: bool = False):
        if preferred:
            self._market_ids.insert(0, market_id)
        else:
            self._market_ids.append(market_id)

    @property
    def market_ids(self) -> List[str]:
        return self._market_ids

    @property
    def raw_profit_loss(self) -> float:
        return self._raw_profit_loss

    @property
    def raw_profit_loss_rate(self) -> float:
        return self._raw_profit_loss_rate

    @property
    def profit_loss(self) -> float:
        return self._profit_loss

    @property
    def profit_loss_rate(self) -> float:
        return self._profit_loss_rate

    @property
    def profit_loss_market(self) -> float:
        return self._profit_loss_market

    @property
    def profit_loss_market_rate(self) -> float:
        return self._profit_loss_market_rate

    def update_profit_loss(self, market: Market):
        """
        Compute profit_loss and profit_loss_rate for maker and taker.
        @param market: A valid market object related to the symbol of the position.
        """
        if market is None or not market.bid or not market.ask:
            # market must be valid with valid price
            return

        if self._price is None:
            # asset price must be defined
            return

        if market.quote != self.quote:
            # market quote must be the same as the asset preferred quote
            return

        if self.quantity <= 0.0 or self._price <= 0.0:
            # empty quantity or undefined average entry price
            self._profit_loss = 0.0
            self._profit_loss_rate = 0.0

            self._profit_loss_market = 0.0
            self._profit_loss_market_rate = 0.0

            return

        # delta price if closing at market
        delta_price = market.bid - self._price

        # cost of the asset in market quote
        cost = self.quantity * self._price
        raw_profit_loss = self.quantity * delta_price

        # without fees neither commissions
        self._raw_profit_loss = raw_profit_loss
        self._raw_profit_loss_rate = (self._raw_profit_loss / cost) if cost != 0.0 else 0.0

        # use maker fee and commission
        self._profit_loss = raw_profit_loss - (cost * market.maker_fee) - (cost * market.maker_commission)
        self._profit_loss_rate = (self._profit_loss / cost) if cost != 0.0 else 0.0

        # use taker fee and commission
        self._profit_loss_market = raw_profit_loss - (cost * market.taker_fee) - (cost * market.taker_commission)
        self._profit_loss_market_rate = (self._profit_loss_market / cost) if cost != 0.0 else 0.0

    def format_price(self, price: float) -> str:
        """
        Format the price according to the precision.
        """
        formatted_price = "{:0.0{}f}".format(truncate(price, self._precision), self._precision)

        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        return formatted_price

    #
    # persistence
    #

    def dumps(self) -> dict:
        """
        @todo Could humanize timestamp into datetime
        @return: dict
        """
        return {
            'symbol': self._symbol,
            'locked-qty': self._locked,
            'free-qty': self._free,
            'last-price': self._price,
            'quote': self._quote,
            'last-update-time': self._last_update_time,
            'last-trade-id': self._last_trade_id,
            'raw-profit-loss': self._raw_profit_loss,
            'raw-profit-loss-rate': self._raw_profit_loss_rate,
            'profit-loss': self._profit_loss,
            'profit-loss-rate': self._profit_loss_rate,
            'profit-loss-market': self._profit_loss_market,
            'profit-loss-market-rate': self._profit_loss_market_rate,
        }

    def loads(self, data: dict):
        if data.get('symbol', "") == self._symbol:
            # quantity
            self._locked = data.get('locked-qty', 0.0)
            self._free = data.get('free-qty', 0.0)

        if data.get('quote', "") == self._quote:
            # only if the same quote
            self._price = data.get('last-price', 0.0)
            self._last_update_time = data.get('last-update-time', 0.0)
            self._last_trade_id = data.get('last-trade-id', 0.0)

            self._raw_profit_loss = data.get('raw-profit-loss', 0.0)
            self._raw_profit_loss_rate = data.get('raw-profit-loss-rate', 0.0)
            self._profit_loss = data.get('profit-loss', 0.0)
            self._profit_loss_rate = data.get('profit-loss-rate', 0.0)
            self._profit_loss_market = data.get('profit-loss-market', 0.0)
            self._profit_loss_market_rate = data.get('profit-loss-market-rate', 0.0)
