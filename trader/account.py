# @date 2018-08-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .trader import Trader

import threading

from dataclasses import dataclass, field
from common.utils import truncate

import logging
logger = logging.getLogger('siis.trader.account')


@dataclass
class AccountStatSample:
    """
    Account statistic sample
    """

    timestamp: float = 0.0     # timestamp of the sample
    performance: float = 0.0   # balance equity
    profit_loss: float = 0.0   # unrealized balance

    draw_down_rate: float = 0.0
    draw_down: float = 0.0

    def dumps(self):
        return self.timestamp, self.performance, self.profit_loss, self.draw_down_rate, self.draw_down

    @staticmethod
    def builder(data):
        return AccountStatSample(data[0], data[1], data[2], data[3], data[4])


class Account(object):
    """
    An account object is owned by a Trader object.

    @todo log equity, draw-down in an array at a defined frequency
    """

    TYPE_UNDEFINED = 0
    TYPE_ASSET = 1
    TYPE_SPOT = 1
    TYPE_MARGIN = 2
    TYPE_SPREADBET = 4

    DEFAULT_STATS_SAMPLING_TIMEFRAME = 60*60*24  # 1 day

    _parent: Trader

    def __init__(self, parent: Trader):
        self._mutex = threading.RLock()
        self._parent = parent

        # account data
        self._name = ""     
        self._username = ""
        self._email = ""

        self._account_type = Account.TYPE_MARGIN

        self._currency = "USD"
        self._currency_display = "$"

        self._alt_currency = "USD"
        self._alt_currency_display = "$"

        self._currency_ratio = 1.0  # conversion rate from currency to alternative currency

        self._currency_precision = 2
        self._alt_currency_precision = 2

        self._balance = 0.0
        self._net_worth = 0.0
        self._margin_balance = 0.0
        self._risk_limit = 0.0
        self._margin_level = 0.0  # equity / initial margin

        self._profit_loss = 0.0
        self._asset_profit_loss = 0.0

        self._asset_balance = 0.0
        self._free_asset_balance = 0.0

        # copy options
        self._leverage = [1, 200]    # min/max leverage

        # global bet should be par instrument
        self._default_stop_loss_rate = 0.5    # never goes deeper than 50%
        self._default_take_profit_rate = 0.5  # when no take profit assume at 50%
        self._default_risk_ratio = 2.0        # mean take profit -2x the stop loss

        self._guaranteed_stop = False

        self._draw_down = 0.0           # in currency
        self._max_draw_down = 0.0       # in currency

        self._draw_down_rate = 0.0      # ratio over balance
        self._max_draw_down_rate = 0.0  # ratio over balance

        self._stats_sampling_timeframe = Account.DEFAULT_STATS_SAMPLING_TIMEFRAME
        self._last_stats_update = 0.0
        self._stats_samples = []

        trader_config = parent.service.trader_config()
        if trader_config:
            self._guaranteed_stop = trader_config.get('guaranteed-stop', False)

    def update(self, connector):
        pass

    @property
    def parent(self) -> Trader:
        return self._parent

    @property
    def account_type(self) -> int:
        return self._account_type

    @property
    def name(self) -> str:
        return self._name

    @property
    def username(self) -> str:
        return self._username

    @property
    def email(self) -> str:
        return self._email

    @property
    def net_worth(self) -> float:
        return self._net_worth

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def currency_display(self) -> str:
        return self._currency_display

    @property
    def alt_currency(self) -> str:
        return self._alt_currency

    @property
    def alt_currency_display(self) -> str:
        return self._alt_currency_display

    @property
    def currency_ratio(self) -> float:
        return self._currency_ratio
    
    @property
    def currency_precision(self) -> int:
        return self._currency_precision
    
    @property
    def alt_currency_precision(self) -> int:
        return self._alt_currency_precision

    @property
    def min_leverage(self) -> float:
        return self._leverage[0]

    @property
    def max_leverage(self) -> float:
        return self._leverage[1]

    @property
    def profit_loss(self) -> float:
        return self._profit_loss

    @property
    def asset_profit_loss(self) -> float:
        return self._asset_profit_loss

    @property
    def default_stop_loss_rate(self) -> float:
        return self._default_stop_loss_rate

    @property
    def default_take_profit_rate(self) -> float:
        return self._default_take_profit_rate

    @property
    def default_risk_ratio(self) -> float:
        return self._default_risk_ratio

    @property
    def margin_balance(self) -> float:
        return self._margin_balance

    @property
    def risk_limit(self) -> float:
        return self._risk_limit

    @property
    def margin_level(self) -> float:
        return self._margin_level

    @property
    def asset_balance(self) -> float:
        return self._asset_balance

    @property
    def free_asset_balance(self) -> float:
        return self._free_asset_balance

    @property
    def guaranteed_stop(self) -> bool:
        return self._guaranteed_stop

    @property
    def draw_down(self) -> float:
        return self._draw_down_rate

    @property
    def max_draw_down(self) -> float:
        return self._max_draw_down_rate

    @property
    def stats_samples(self) -> list[AccountStatSample]:
        return self._stats_samples

    @account_type.setter
    def account_type(self, account_type: int):
        self._account_type = account_type

    def add_realized_profit_loss(self, profit_loss: float):
        """
        Update the balance adding the realized profit/loss, and minus that profit/loss from the
        current unrealized profit loss
        """
        self._profit_loss -= profit_loss
        self._balance += profit_loss

    def set_balance(self, balance: float):
        self._balance = balance

    def use_balance(self, amount: float):
        self._balance -= amount

    def set_asset_balance(self, balance: float, free: float):
        self._asset_balance = balance
        self._free_asset_balance = free

    def use_margin(self, margin: float):
        self._margin_balance -= margin

    def free_margin(self, margin: float):
        self._margin_balance += margin

    def set_used_margin(self, used_margin: float):
        self._margin_balance = self._balance - used_margin

    def set_margin_balance(self, margin_balance: float):
        self._margin_balance = margin_balance

    def add_unrealized_profit_loss(self, upnl: float):
        self._profit_loss += upnl

    def set_unrealized_profit_loss(self, upnl: float):
        self._profit_loss = upnl

    def add_unrealized_asset_profit_loss(self, upnl: float):
        self._asset_profit_loss += upnl

    def set_unrealized_asset_profit_loss(self, upnl: float):
        self._asset_profit_loss = upnl

    def set_currency(self, currency: str, currency_display: str = ""):
        self._currency = currency
        self._currency_display = currency_display or currency

    def set_alt_currency(self, alt_currency: str, alt_currency_display: str = ""):
        self._alt_currency = alt_currency
        self._alt_currency_display = alt_currency_display or alt_currency

    def set_risk_limit(self, risk_limit: float):
        self._risk_limit = risk_limit

    def set_margin_level(self, margin_level: float):
        self._margin_level = margin_level

    def set_net_worth(self, net_worth: float):
        self._net_worth = net_worth

    def initial(self, balance: float, currency: str, currency_display: str):
        self._balance = balance
        self._margin_balance = balance
        self._currency = currency
        self._currency_display = currency_display

    @currency_ratio.setter
    def currency_ratio(self, currency_ratio: float):
        self._currency_ratio = currency_ratio

    def lock(self, blocking: bool = True, timeout: float = -1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()       

    @classmethod
    def mutexed(cls, fn: Callable):
        """Annotation for methods that require mutex locker."""
        def wrapped(self, *args, **kwargs):
            with self._mutex:
                return fn(self, *args, **kwargs)
    
        return wrapped

    #
    # helpers
    #

    def format_price(self, price: float) -> str:
        """
        Format the price according to the precision.
        """
        precision = self._currency_precision

        formatted_price = "{:0.0{}f}".format(truncate(price, precision), precision)

        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        return formatted_price

    def format_alt_price(self, price: float) -> str:
        """
        Format the price according to the precision.
        """
        precision = self._alt_currency_precision

        formatted_price = "{:0.0{}f}".format(truncate(price, precision), precision)

        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        return formatted_price

    def update_draw_down(self):
        # update draw down
        dd = (self._profit_loss + self._asset_profit_loss) / self._balance if self._balance > 0 else 0
        if dd < 0.0:
            self._draw_down_rate = -dd

        dd = self._profit_loss + self._asset_profit_loss
        if dd < 0.0:
            self._draw_down = -dd

        self._max_draw_down_rate = max(self._max_draw_down_rate, self._draw_down_rate)
        self._max_draw_down = max(self._max_draw_down, self._draw_down)

    def update_stats(self, timestamp: float):
        if not self._last_stats_update:
            # initial sample
            self._last_stats_update = timestamp
            self._stats_samples.append(AccountStatSample(
                self._last_stats_update,
                self._balance,
                self._profit_loss,
                self._draw_down_rate,
                self._draw_down))

            return

        if timestamp - self._last_stats_update >= self._stats_sampling_timeframe:
            self._last_stats_update = self._last_stats_update + self._stats_sampling_timeframe
            self._stats_samples.append(AccountStatSample(
                self._last_stats_update,
                self._balance,
                self._profit_loss,
                self._draw_down_rate,
                self._draw_down))

    #
    # persistence
    #

    def dumps(self) -> dict:
        return {
            'balance': self._balance,
            'net-worth': self._net_worth,
            'margin-balance': self._margin_balance,
            'risk-limit': self._risk_limit,
            'margin-level': self._margin_level,
            'profit-loss': self._profit_loss,
            'asset-profit-loss': self._asset_profit_loss,
            'asset-balance': self._asset_balance,
            'free-asset-balance': self._free_asset_balance,
            'draw-down-rate': self._draw_down_rate,
            'draw-down': self._draw_down,
            'max-draw-down': self._max_draw_down_rate,
            'max-draw-down-rate': self._max_draw_down,
            'stats-samples': [x.dumps() for x in self._stats_samples]
        }

    def loads(self, data: dict):
        self._balance = data.get('balance', 0.0)
        self._net_worth = data.get('net-worth', 0.0)
        self._margin_balance = data.get('margin-balance', 0.0)
        self._risk_limit = data.get('risk-limit', 0.0)
        self._margin_level = data.get('margin-level', 0.0)
        self._profit_loss = data.get('profit-loss', 0.0)
        self._asset_profit_loss = data.get('asset-profit-loss', 0.0)
        self._asset_balance = data.get('asset-balance', 0.0)
        self._free_asset_balance = data.get('free-asset-balance', 0.0)

        self._draw_down_rate = data.get('draw-down-rate', 0.0)
        self._draw_down = data.get('draw-down', 0.0)
        self._max_draw_down_rate = data.get('max-draw-down-rate', 0.0)
        self._max_draw_down = data.get('max-draw-down', 0.0)

        self._stats_samples = [AccountStatSample.builder(d) for d in data.get('stats-samples', [])]
