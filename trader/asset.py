# @date 2018-10-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Trader asset

import math

from common.utils import truncate


class Asset(object):
    """
    Asset define a symbol and a balance, with margin or not. It is initially created for
    use with binance.com but will be extended to any balance even for EUR or USD margin based broker,
    in such we would check the asset balance before opening a position.
    """

    def __init__(self, trader, symbol, precision=8):
        super().__init__()
        
        self._trader = trader
        self._symbol = symbol
        self._precision = precision  # price decimal place

        self._locked = 0.0  # currently locked quantity in orders
        self._free = 0.0    # free quantity for trading

        self._price = 0.0   # last updated average price
        self._quote = None  # quote symbol

        self._last_update_time = 0.0
        self._last_trade_id = 0

        self._market_ids = []

        self._profit_loss = 0.0
        self._profit_loss_rate = 0.0
        
        self._profit_loss_market = 0.0
        self._profit_loss_market_rate = 0.0

    @property
    def last_update_time(self):
        return self._last_update_time

    @property
    def last_trade_id(self):
        return self._last_trade_id
    
    @property
    def symbol(self):
        return self._symbol
    
    @property
    def trader(self):
        return self._trader

    @property
    def quantity(self):
        return round(self._locked + self._free, self._precision)

    @property
    def free(self):
        return self._free
    
    @property
    def locked(self):
        return self._locked
    
    @property
    def price(self):
        return self._price

    @property
    def quote(self):
        return self._quote

    @quote.setter
    def quote(self, quote):
        self._quote = quote

    @property
    def precision(self):
        return self._precision
    
    @precision.setter
    def precision(self, precision):
        self._precision = precision

    def set_quantity(self, locked, free):
        self._locked = locked
        self._free = free

        # reset profit/loss when zero
        if not locked and not free:
            self._profit_loss = 0.0
            self._profit_loss_rate = 0.0

            self._profit_loss_market = 0.0
            self._profit_loss_market_rate = 0.0

    def update_price(self, last_update_time, last_trade_id, price, quote):
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

    def set_market_ids(self, market_ids):
        """
        Defines a list of compatibles markets identifiers.
        """
        self._market_ids = market_ids

    def add_market_id(self, market_id):
        self._market_ids.append(market_id)

    def remove_market_id(self, market_id):
        del self._market_ids[self.index(market_id)]

    @property
    def market_ids(self):
        return self._market_ids

    @property
    def profit_loss(self):
        return self._profit_loss

    @property
    def profit_loss_rate(self):
        return self._profit_loss_rate

    @property
    def profit_loss_market(self):
        return self._profit_loss_market

    @property
    def profit_loss_market_rate(self):
        return self._profit_loss_market_rate

    def update_profit_loss(self, market):
        """
        Compute profit_loss and profit_loss_rate for maker and taker.
        @param market A valid market object related to the symbol of the position.
        """
        if market is None or not market.bid or not market.ask:
            # market must be valid with valid price
            return

        if self._price is None:
            # asset price must be defined
            return

        if market.quote != self.quote:
            # market quote must be the same as the asset prefered quote
            return

        # delta price if closing at market
        delta_price = market.bid - self._price

        # cost of the asset in market quote
        cost = self.quantity * self._price
        raw_profit_loss = self.quantity * delta_price

        # use maker fee and commission
        self._profit_loss = raw_profit_loss - (cost * market.maker_fee) - (cost * market.maker_commission)
        self._profit_loss_rate = (self._profit_loss / cost) if cost != 0.0 else 0.0

        # use taker fee and commission
        self._profit_loss_market = raw_profit_loss - (cost * market.taker_fee) - (cost * market.taker_commission)
        self._profit_loss_market_rate = (self._profit_loss_market / cost) if cost != 0.0 else 0.0

    def format_price(self, price):
        """
        Format the price according to the precision.
        @param use_quote True use quote display or quote, False base, None no symbol only price.
        """
        formatted_price = "{:0.0{}f}".format(truncate(price, self._precision), self._precision)

        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        return formatted_price
