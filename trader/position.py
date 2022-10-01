# @date 2018-08-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Trader position

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from .trader import Trader
    from .market import Market

from common.keyed import Keyed


class Position(Keyed):
    """
    Trader side position.
    Profit/loss are computed in base currency.
    Profit/loss rate consider the traded volume and margin level.
    To have the change rate from the opened price use the change_rate method.
    Fee are defined in rate (0.01 meaning 1%)

    The rollover is not computed into the profit/loss, it might be done at the account level

    and position of the symbol (ex: $1000.01 or 1175.37€ or 11.3751B)
    """

    __slots_ = '_trader', '_position_id', '_state', '_symbol', '_symbol', '_quantity', \
               '_profit_loss', '_profit_loss_rate', \
               '_profit_loss_market', '_profit_loss_market_rate', '_raw_profit_loss', '_raw_profit_loss_rate', \
               '_created_time', '_market_close', \
               '_leverage', '_entry_price', '_exit_price' \
               '_stop_loss', '_take_profit', '_trailing_stop', '_direction'

    LONG = 1    # long direction
    SHORT = -1  # short direction

    STATE_PENDING = 0
    STATE_OPENED = 1
    STATE_CLOSING = 3
    STATE_CLOSED = 4

    _take_profit: Union[float, None]
    _stop_loss: Union[float, None]

    def __init__(self, trader: Trader):
        super().__init__()

        self._trader = trader
        self._position_id = ""
        self._state = Position.STATE_PENDING

        self._symbol = ""
        self._quantity = 0.0

        self._raw_profit_loss = 0.0
        self._raw_profit_loss_rate = 0.0

        self._profit_loss = 0.0
        self._profit_loss_rate = 0.0

        self._profit_loss_market = 0.0
        self._profit_loss_market_rate = 0.0

        self._created_time = 0.0
        self._closed_time = 0.0

        self._market_close = False
        self._leverage = 1.0
        self._entry_price = 0.0
        self._exit_price = 0.0
        self._take_profit = None
        self._stop_loss = None
        self._trailing_stop = False
        self._direction = Position.LONG

    def entry(self, direction: int, symbol: str, quantity: float, take_profit: Optional[float] = None,
              stop_loss: Optional[float] = None, leverage: float = 1.0, trailing_stop: bool = False):

        self._state = Position.STATE_OPENED
        self._direction = direction
        self._symbol = symbol
        self._quantity = quantity
        self._take_profit = take_profit
        self._stop_loss = stop_loss
        self._leverage = leverage
        self._trailing_stop = trailing_stop

    def closing(self, exit_price=None):
        self._state = Position.STATE_CLOSING
        self._exit_price = exit_price

    def exit(self, exit_price=None):
        self._state = Position.STATE_CLOSED
        self._exit_price = exit_price

    def set_position_id(self, position_id: str):
        self._position_id = position_id

    def is_opened(self) -> bool:
        return self._state == Position.STATE_OPENED

    def is_closing(self) -> bool:
        return self._state == Position.STATE_CLOSING

    def is_closed(self) -> bool:
        return self._state == Position.STATE_CLOSED

    @property
    def state(self) -> int:
        return self._state

    @property
    def position_id(self) -> str:
        return self._position_id
    
    @property
    def trader(self) -> Trader:
        return self._trader

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def direction(self) -> int:
        return self._direction

    @property
    def take_profit(self) -> float:
        return self._take_profit
    
    @property
    def stop_loss(self) -> float:
        return self._stop_loss
    
    @property
    def entry_price(self) -> float:
        return self._entry_price

    @property
    def exit_price(self) -> float:
        return self._exit_price

    @property
    def trailing_stop(self) -> bool:
        return self._trailing_stop
    
    @property
    def leverage(self) -> float:
        return self._leverage

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

    @property
    def market_close(self) -> bool:
        return self._market_close

    @property
    def created_time(self) -> float:
        return self._created_time

    @property
    def closed_time(self) -> float:
        return self._closed_time

    @property
    def quantity(self) -> float:
        return self._quantity

    @trader.setter
    def trader(self, trader: Trader):
        self._trader = trader
    
    @symbol.setter
    def symbol(self, symbol: str):
        self._symbol = symbol

    @direction.setter
    def direction(self, direction: int):
        self._direction = direction

    @profit_loss.setter
    def profit_loss(self, profit_loss: float):
        self._profit_loss = profit_loss

    @profit_loss_rate.setter
    def profit_loss_rate(self, profit_loss_rate: float):
        self._profit_loss_rate = profit_loss_rate
    
    @profit_loss_market.setter
    def profit_loss_market(self, profit_loss_market: float):
        self._profit_loss_market = profit_loss_market

    @profit_loss_market_rate.setter
    def profit_loss_market_rate(self, profit_loss_market_rate: float):
        self._profit_loss_market_rate = profit_loss_market_rate
    
    @market_close.setter
    def market_close(self, market_close: bool):
        self._market_close = market_close

    @trailing_stop.setter
    def trailing_stop(self, trailing_stop: bool):
        self._trailing_stop = trailing_stop

    @created_time.setter
    def created_time(self, timestamp: float):
        self._created_time = timestamp

    @closed_time.setter
    def closed_time(self, timestamp: float):
        self._closed_time = timestamp

    @quantity.setter
    def quantity(self, quantity: float):
        self._quantity = quantity

    @entry_price.setter
    def entry_price(self, entry_price: float):
        self._entry_price = entry_price

    @leverage.setter
    def leverage(self, leverage: float):
        self._leverage = leverage

    @take_profit.setter
    def take_profit(self, tp: float):
        self._take_profit = tp

    @stop_loss.setter
    def stop_loss(self, sl: float):
        self._stop_loss = sl

    @exit_price.setter
    def exit_price(self, price: float):
        self._exit_price = price

    def change_rate(self, market: Market) -> float:
        """
        Compute and return the gained rate related to the entry and market price.
        Its only the change of the price in percent (does not take care of the size of the position)
        @return Profit/loss rate
        """
        if market is None:
            return 0.0

        # delta price if closing at market
        if self.direction == Position.LONG:
            delta_price = market.bid - self.entry_price
        elif self.direction == Position.SHORT:
            delta_price = self.entry_price - market.ask
        else:
            delta_price = 0.0

        return delta_price / self.entry_price if self.entry_price else 0.0

    def update_profit_loss(self, market: Market):
        """
        Compute profit_loss and profit_loss_rate for maker and taker.
        @param market A valid market object related to the symbol of the position.
        """
        if market is None or not market.bid or not market.ask:
            return

        if self.entry_price is None:
            return

        delta_price = self.price_diff(market)
        position_cost = self.position_cost(market)

        # raw_profit_loss = self.quantity * (delta_price / (market.one_pip_means or 1.0)) * market.value_per_pip
        raw_profit_loss = self.quantity * delta_price * market.contract_size

        # without fees neither commissions
        self._raw_profit_loss = raw_profit_loss
        self._raw_profit_loss_rate = (self._raw_profit_loss / position_cost) if position_cost != 0.0 else 0.0

        # use maker fee and commission
        self._profit_loss = raw_profit_loss - (position_cost * market.maker_fee) - market.maker_commission
        self._profit_loss_rate = (self._profit_loss / position_cost) if position_cost != 0.0 else 0.0

        # use taker fee and commission
        self._profit_loss_market = raw_profit_loss - (position_cost * market.taker_fee) - market.taker_commission
        self._profit_loss_market_rate = (self._profit_loss_market / position_cost) if position_cost != 0.0 else 0.0

    def close_direction(self) -> int:
        """
        Return the inverse of the direction of the position that is needed to close or revert this position.
        It does not invert the position ! It is just a syntax sugar.
        """
        return Position.LONG if self.direction == Position.SHORT else Position.SHORT

    def price_diff(self, market: Market) -> float:
        """
        Difference of price from entry to current market price, depending on the direction.
        """
        if market is None:
            return 0.0

        if self.direction == Position.LONG:
            return market.bid - self.entry_price
        elif self.direction == Position.SHORT:
            return self.entry_price - market.ask

        return 0.0

    def position_cost(self, market: Market) -> float:
        """
        Return the cost of the position in base currency. It does not take care about the margin factor / leverage.
        """
        if market is None:
            return 0.0

        # @todo not sure lot_size should be here
        # return self.quantity * (market.lot_size * market.contract_size) * self._entry_price
        return self.quantity * market.contract_size * self._entry_price

    def margin_cost(self, market: Market) -> float:
        """
        Return the used margin in base currency (using margin factor). Have to divide per base exchange rate to have
        it in account base currency. But in backtesting we don't have all the rate from base pair to base account.
        """
        if market is None:
            return 0.0

        # @todo not sure lot_size should be here
        # return self.quantity * (market.lot_size * market.contract_size) * market.margin_factor * self._entry_price
        return self.quantity * market.contract_size * market.margin_factor * self._entry_price

    def direction_to_str(self) -> str:
        if self._direction > 0:
            return 'long'
        elif self._direction < 0:
            return 'short'
        else:
            return ''

    def direction_from_str(self, direction: str):
        if direction == 'long':
            self._direction = 1
        elif direction == 'short':
            self._direction = -1
        else:
            self._direction = 0

    #
    # persistence
    #

    def dumps(self) -> dict:
        """
        @todo Could humanize str and timestamp into datetime
        @return: dict
        """
        return {
            'id': self._position_id,
            'state': self._state,
            'symbol': self._symbol,
            'quantity': self._quantity,
            'direction': self._direction,
            'created': self._created_time,
            'closed': self._closed_time,
            'market-close': self._market_close,
            'leverage': self._leverage,
            'entry-price': self._entry_price,
            'exit-price': self._exit_price,
            'take-profit-price': self._take_profit,
            'stop-loss-price': self._stop_loss,
            'trailing-stop': self._trailing_stop,
            'raw-profit-loss': self._raw_profit_loss,
            'raw-profit-loss-rate': self._raw_profit_loss_rate,
            'profit-loss': self._profit_loss,
            'profit-loss-rate': self._profit_loss_rate,
            'profit-loss-market': self._profit_loss_market,
            'profit-loss-market-rate': self._profit_loss_market_rate,
        }

    def loads(self, data: dict):
        # if data.get('symbol', "") == self._symbol:
        #     # @todo could merge with current

        self._position_id = data.get('id', None)
        self._state = data.get('state', Position.STATE_PENDING)

        self._symbol = data.get('symbol', "")
        self._quantity = data.get('quantity', 0.0)
        self._direction = data.get('direction', Position.LONG)

        self._created_time = data.get('created', 0.0)
        self._closed_time = data.get('closed', 0.0)

        self._market_close = data.get('market-close', False)
        self._leverage = data.get('leverage', 1.0)
        self._entry_price = data.get('entry-price', 0.0)
        self._exit_price = data.get('exit-price', 0.0)
        self._take_profit = data.get('take-profit-price', None)
        self._stop_loss = data.get('stop-loss-price', None)
        self._trailing_stop = data.get('trailing-stop', False)

        self._raw_profit_loss = data.get('raw-profit-loss', 0.0)
        self._raw_profit_loss_rate = data.get('raw-profit-loss-rate', 0.0)
        self._profit_loss = data.get('profit-loss', 0.0)
        self._profit_loss_rate = data.get('profit-loss-rate', 0.0)
        self._profit_loss_market = data.get('profit-loss-market', 0.0)
        self._profit_loss_market_rate = data.get('profit-loss-market-rate', 0.0)
