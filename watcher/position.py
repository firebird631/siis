# @date 2018-08-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# watcher side position model

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

    def __init__(self, watcher, position_id, author=None):
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

    def entry(self, direction, quantity, entry_price, stop_loss, take_profit, entry_date,
              leverage=None, trailing_stop_loss=False):
        self._status = Position.POSITION_OPENED
        self._direction = direction
        self._quantity = quantity
        self._entry_price = entry_price
        self._stop_loss = stop_loss
        self._take_profit = take_profit
        self._leverage = leverage
        self._entry_date = entry_date
        self._trailing_stop_loss = trailing_stop_loss

    def exit(self, exit_price, exit_date):
        self._status = Position.POSITION_CLOSED
        self._exit_price = exit_price
        self._exit_date = exit_date

    def updated(self, direction, quantity, entry_price, stop_loss, take_profit):
        self._status = Position.POSITION_UPDATED
        self._quantity = quantity
        self._entry_price = entry_price
        self._direction = direction
        self._stop_loss = stop_loss
        self._take_profit = take_profit

    @property
    def quantity(self):
        return self._quantity

    @quantity.setter
    def quantity(self, quantity):
        self._quantity = quantity

    @property
    def watcher(self):
        return self._watcher

    @property
    def position_id(self):
        return self._position_id
    
    @property
    def symbol(self):
        return self._symbol

    @symbol.setter
    def symbol(self, symbol):
        self._symbol = symbol

    @property
    def status(self):
        return self._status

    @property
    def entry_price(self):
        return self._entry_price

    @property
    def exit_price(self):
        return self._exit_price

    @property
    def direction(self):
        return self._direction

    @property
    def author(self):
        return self._author
    
    @property
    def stop_loss(self):
        return self._stop_loss
    
    @property
    def take_profit(self):
        return self._take_profit
    
    @property
    def leverage(self):
        return self._leverage

    @property
    def score(self):
        return self._score

    @property
    def profit_loss(self):
        return self._profit_loss

    @property
    def trailing_stop_loss(self):
        return self._trailing_stop_loss

    @profit_loss.setter
    def profit_loss(self, pl):
        self._profit_loss = pl
    
    @property
    def profit_loss_rate(self):
        return self._profit_loss_rate
    
    @profit_loss_rate.setter
    def profit_loss_rate(self, pl_rate):
        self._profit_loss_rate = pl_rate

    @property
    def entry_date(self):
        return self._entry_date
    
    @property
    def exit_date(self):
        return self._exit_date
