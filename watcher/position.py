# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# watcher side position model

from __future__ import annotations

from typing import TYPE_CHECKING, Union, Optional

if TYPE_CHECKING:
    from .watcher import Watcher

from watcher.author import Author
from common.keyed import Keyed


class Position(Keyed):
    """
    Social position.

    Contains detail on the author of the position and more.
    @deprecated Must be part of the social strategy.    
    """

    POSITION_PENDING = 0
    POSITION_OPENED = 1
    POSITION_CLOSED = 2
    POSITION_UPDATED = 3

    LONG = 1    # long direction
    SHORT = -1  # short direction

    _author: Union[Author, None]

    def __init__(self, watcher: Watcher, position_id: str, author: Optional[Author] = None):
        super().__init__()

        self._watcher = watcher
        self._status = Position.POSITION_PENDING
        self._position_id = position_id
        self._author = author
        self._score = 0.0
        self._symbol = ""
        self._direction = Position.LONG
        self._profit_loss = 0.0
        self._profit_loss_rate = 0.0
        self._take_profit = None
        self._stop_loss = None
        self._quantity = 0.0
        self._leverage = 1.0
        self._trailing_stop_loss = False
        self._entry_price = 0.0
        self._entry_date = 0.0
        self._exit_price = 0.0
        self._exit_date = 0.0

    def entry(self, direction: int, quantity: float, entry_price: float, stop_loss: float, take_profit: float,
              entry_date: float,
              leverage: Optional[float] = None, trailing_stop_loss: bool = False):

        self._status = Position.POSITION_OPENED
        self._direction = direction
        self._quantity = quantity
        self._entry_price = entry_price
        self._stop_loss = stop_loss
        self._take_profit = take_profit
        self._leverage = leverage
        self._entry_date = entry_date
        self._trailing_stop_loss = trailing_stop_loss

    def exit(self, exit_price: float, exit_date: float):
        self._status = Position.POSITION_CLOSED
        self._exit_price = exit_price
        self._exit_date = exit_date

    def updated(self, direction: int, quantity: float, entry_price: float, stop_loss: float, take_profit: float):
        self._status = Position.POSITION_UPDATED
        self._quantity = quantity
        self._entry_price = entry_price
        self._direction = direction
        self._stop_loss = stop_loss
        self._take_profit = take_profit

    @property
    def quantity(self) -> float:
        return self._quantity

    @quantity.setter
    def quantity(self, quantity: float):
        self._quantity = quantity

    @property
    def watcher(self) -> Watcher:
        return self._watcher

    @property
    def position_id(self) -> str:
        return self._position_id
    
    @property
    def symbol(self) -> str:
        return self._symbol

    @symbol.setter
    def symbol(self, symbol: str):
        self._symbol = symbol

    @property
    def status(self) -> int:
        return self._status

    @property
    def entry_price(self) -> float:
        return self._entry_price

    @property
    def exit_price(self) -> float:
        return self._exit_price

    @property
    def direction(self) -> int:
        return self._direction

    @property
    def author(self) -> Union[Author, None]:
        return self._author
    
    @property
    def stop_loss(self) -> float:
        return self._stop_loss
    
    @property
    def take_profit(self) -> float:
        return self._take_profit
    
    @property
    def leverage(self) -> float:
        return self._leverage

    @property
    def score(self) -> float:
        return self._score

    @property
    def profit_loss(self) -> float:
        return self._profit_loss

    @property
    def trailing_stop_loss(self) -> bool:
        return self._trailing_stop_loss

    @profit_loss.setter
    def profit_loss(self, pl: float):
        self._profit_loss = pl
    
    @property
    def profit_loss_rate(self) -> float:
        return self._profit_loss_rate
    
    @profit_loss_rate.setter
    def profit_loss_rate(self, pl_rate: float):
        self._profit_loss_rate = pl_rate

    @property
    def entry_date(self) -> float:
        return self._entry_date
    
    @property
    def exit_date(self) -> float:
        return self._exit_date
