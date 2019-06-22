# @date 2018-08-08
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

from config import config
from common.utils import truncate

import threading


class Account(object):
    """
    An account object is owned by a Trader object.
    @todo currency string formatter ?
    """

    TYPE_ASSET = 0
    TYPE_MARGIN = 1

    STOP_NONE = 0
    STOP_LIMIT = 1
    STOP_MARKET = 2
    STOP_GUARANTEED = 3

    STOP_VALUE_NONE = 0          # no stop value specified
    STOP_VALUE_LEVEL = 1         # in account currency max loss
    STOP_VALUE_LEVEL_PCT = 2     # in account currency max loss rate of account current available balance
    STOP_VALUE_DISTANCE = 3      # in instrument unit (ie in pips for a forex)
    STOP_VALUE_DISTANCE_PCT = 4  # in instrument unit rate (ie rate of pips for a forex)

    TAKE_PROFIT_NONE = 0
    TAKE_PROFIT_LIMIT = 1
    TAKE_PROFIT_MARKET = 2

    TAKE_PROFIT_NONE = 0
    TAKE_PROFIT_DISTANCE = 1
    TAKE_PROFIT_LEVEL = 2

    def __init__(self, parent):
        self._mutex = threading.Lock()
        self._parent = parent

        # account data
        self._id = ""
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

        self._balance = 0
        self._net_worth = 0     

        self._margin_balance = 0
        self._risk_limit = 0

        self._profit_loss = 0

        self._shared = False   # share shared trades xD

        # copy options
        self._leverage = [1, 200]    # min/max leverage

        # global bet should be par instrument/appliance
        self._default_stop_loss_rate = 0.5    # never goes deeper than 50%
        self._default_take_profit_rate = 0.5  # when no take profit assume at 50%
        self._default_risk_ratio = 2.0        # mean take profit -2x the stop loss

        self._guaranteed_stop = None

        trader_config = parent.service.trader_config(self._parent.name)
        if trader_config:
            self._guaranteed_stop = trader_config.get('guaranteed_stop', None)

    def update(self, connector):
        pass

    @property
    def parent(self):
        return self._parent

    @property
    def id(self):
        return self._id

    @property
    def account_type(self):
        return self._account_type
            
    @property
    def name(self):
        return self._name

    @property
    def username(self):
        return self._username

    @property
    def email(self):
        return self._email

    @property
    def net_worth(self):
        return self._net_worth

    @property
    def balance(self):
        return self._balance

    @property
    def shared(self):
        return self._shared

    @property
    def currency(self):
        return self._currency

    @property
    def currency_display(self):
        return self._currency_display

    @property
    def alt_currency(self):
        return self._alt_currency

    @property
    def alt_currency_display(self):
        return self._alt_currency_display

    @property
    def currency_ratio(self):
        return self._currency_ratio
    
    @property
    def currency_precision(self):
        return self._currency_precision
    
    @property
    def alt_currency_precision(self):
        return self._alt_currency_precision

    @property
    def min_leverage(self):
        return self._leverage[0]

    @property
    def max_leverage(self):
        return self._leverage[1]

    @property
    def profit_loss(self):
        return self._profit_loss

    @property
    def default_stop_loss_rate(self):
        return self._default_stop_loss_rate

    @property
    def default_take_profit_rate(self):
        return self._default_take_profit_rate

    @property
    def default_risk_ratio(self):
        return self._default_risk_ratio

    @property
    def margin_balance(self):
        return self._margin_balance

    @property
    def risk_limit(self):
        return self._risk_limit

    @property
    def has_guaranteed_stop(self):
        return self._guaranteed_stop and self._guaranteed_stop.get('status', False)

    @account_type.setter
    def account_type(self, account_type):
        self._account_type = account_type

    def add_realized_profit_loss(self, profit_loss):
        """
        Update the balance adding the realized profit/loss, and minus that profit/loss from the
        current unrealized profit loss
        """
        self._profit_loss -= profit_loss
        self._balance += profit_loss

    def set_balance(self, balance):
        self._balance = balance

    def add_used_margin(self, margin):
        self._margin_balance += margin

    def set_used_margin(self, used_margin):
        self._margin_balance = self._balance - used_margin

    def set_margin_balance(self, margin_balance):
        self._margin_balance = margin_balance

    def add_unrealized_profit_loss(self, upnl):
        self._profit_loss += upnl

    def set_unrealized_profit_loss(self, upnl):
        self._profit_loss = upnl

    def set_currency(self, currency, currency_display=""):
        self._currency = currency
        self._currency_display = currency_display or currency

    def set_alt_currency(self, alt_currency, alt_currency_display=""):
        self._alt_currency = alt_currency
        self._alt_currency_display = alt_currency_display or alt_currency

    def set_risk_limit(self, risk_limit):
        self._risk_limit = risk_limit

    def initial(self, balance, currency, currency_display):
        self._balance = balance
        self._currency = currency
        self._currency_display = currency_display

    @currency_ratio.setter
    def currency_ratio(self, currency_ratio):
        self._currency_ratio = currency_ratio

    @property
    def guaranteed_stop_mode(self):
        if self._guaranteed_stop:
            mode = self._guaranteed_stop.get('mode', '')
            if mode and mode == 'level':
                return Account.STOP_VALUE_LEVEL
            elif mode and mode == 'level-percent':
                return Account.STOP_VALUE_LEVEL_PCT         
            elif mode and mode == 'distance':
                return Account.STOP_VALUE_DISTANCE
            elif mode and mode == 'distance-percent':
                return Account.STOP_VALUE_DISTANCE_PCT

        return Account.STOP_VALUE_NONE

    @property
    def guaranteed_stop_value(self):
        if self._guaranteed_stop:
            return self._guaranteed_stop.get('value', 0)
        else:
            return 0

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()       

    @classmethod
    def mutexed(cls, fn):
        """Annotation for methods that require mutex locker."""
        def wrapped(self, *args, **kwargs):
            self.lock()
            result = fn(self, *args, **kwargs)
            self.unlock()
            return result
    
        return wrapped

    #
    # helpers
    #

    def format_price(self, price, use_alt=True, display_symbol=False):
        """
        Format the price according to the precision.
        @param use_quote True use currency display or alt currency, False base, None no symbol only price.
        """
        if use_alt:
            precision = self._alt_currency_precision
        else:
            precision = self._currency_precision

        formatted_price = "{:0.0{}f}".format(truncate(price, precision), precision)

        if '.' in formatted_price:
            formatted_price = formatted_price.rstrip('0').rstrip('.')

        if not display_symbol:
            return formatted_price

        if use_alt:
            return "%s%s" % (formatted_price, self._alt_currency_display or self._alt_currency)
        else:
            return "%s%s" % (formatted_price, self._currency_display or self._currency)
