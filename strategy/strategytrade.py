# @date 2018-12-28
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy trade base class

from datetime import datetime

from common.signal import Signal
from common.utils import timeframe_to_str, timeframe_from_str, UTC

from trader.order import Order, order_type_to_str

import logging
logger = logging.getLogger('siis.strategy.trade')


class StrategyTrade(object):
    """
    Strategy trade base abstract class. A trade is related to entry and and one or many exit order.
    It can be created from an automated or manual signal, and having some initial conditions, timeframe, expiry,
    and they are managed according to the policy of a strategy trade manager, or from some other operations added manually
    for semi-automated trading.

    It can only have on entry order. The exit works on the entried quantity. When the entry order is not fully filled,
    the exit order are later adjusted.

    @todo Take care to do not try to serialize objects from extra dict.
    """

    __slots__ = '_trade_type', '_entry_state', '_exit_state', '_closing', '_timeframe', '_operations', '_user_trade', '_next_operation_id', \
                'id', 'dir', 'op', 'oq', 'tp', 'sl', 'aep', 'axp', 'eot', 'xot', 'e', 'x', 'pl', '_stats', 'last_tp_ot', 'last_stop_ot', \
                'exit_trades', '_label', '_entry_timeout', '_expiry', '_dirty', '_extra', 'sl_mode', 'sl_tf', 'tp_mode', 'tp_tf', 'context'

    VERSION = "1.0.0"

    TRADE_UNDEFINED = -1
    TRADE_BUY_SELL = 0    # spot/asset trade
    TRADE_ASSET = 0
    TRADE_SPOT = 0
    TRADE_MARGIN = 1      # individual margin trade but as FIFO position (incompatible with hedging markets)
    TRADE_IND_MARGIN = 2  # indivisible margin trade position (incompatible with hedging markets)
    TRADE_POSITION = 3    # individual margin trade position (compatible with hedging markets)

    STATE_UNDEFINED = -1
    STATE_NEW = 0
    STATE_REJECTED = 1
    STATE_DELETED = 2
    STATE_CANCELED = 3
    STATE_OPENED = 4
    STATE_PARTIALLY_FILLED = 5
    STATE_FILLED = 6

    ERROR = -1
    REJECTED = 0
    ACCEPTED = 1
    NOTHING_TO_DO = 2

    REASON_NONE = 0
    REASON_TAKE_PROFIT_MARKET = 1   # take-profit market hitted
    REASON_TAKE_PROFIT_LIMIT = 2    # take-profit limit hitted
    REASON_STOP_LOSS_MARKET = 3     # stop-loss market hitted
    REASON_STOP_LOSS_LIMIT = 4      # stop-loss limit hitted
    REASON_CLOSE_MARKET = 5         # exit signal at market
    REASON_CANCELED_TIMEOUT = 6     # canceled after a timeout expiration delay
    REASON_CANCELED_TARGETED = 7    # canceled before entering because take-profit price reached before entry price
    REASON_MARKET_TIMEOUT = 8       # closed (in profit or in loss) after a timeout

    def __init__(self, trade_type, timeframe):
        self._trade_type = trade_type

        self._entry_state = StrategyTrade.STATE_NEW
        self._exit_state = StrategyTrade.STATE_NEW
        self._closing = False
        self._dirty = False        # flag set when the quantity of the entry trade increase and then the exit orders must be updated

        self._timeframe = timeframe  # timeframe that have given this trade

        self._operations = []      # list containing the operation to process during the trade for semi-automated trading
        self._user_trade = False   # true if the user is responsible of the TP & SL adjustement else (default) strategy manage it
        self._label = ""           # trade label(must be few chars)
        self._entry_timeout = 0    # expiration delay in seconds of the entry
        self._expiry = 0           # expiration delay in seconds or 0 if never

        self._next_operation_id = 1

        self.id = 0      # unique trade identifier
        self.dir = 0     # direction (1 long, -1 short)

        self.op = 0.0    # ordered price (limit)
        self.oq = 0.0    # ordered quantity

        self.tp = 0.0    # take-profit price
        self.sl = 0.0    # stop-loss price

        self.aep = 0.0   # average entry price
        self.axp = 0.0   # average exit price

        self.eot = 0     # entry order opened timestamp
        self.xot = 0     # exit order opened timestamp

        self.e = 0.0     # current filled entry quantity
        self.x = 0.0     # current filled exit quantity (a correctly closed trade must have x == f with f <= q and q > 0)

        self.pl = 0.0    # once closed profit/loss in percent (valid once partially or fully closed)

        self.exit_trades = {}  # contain each executed exit trades {<orderId< : (<qty<, <price>)}

        self.last_stop_ot = [0, 0]
        self.sl_mode = 0   # integer that could serves as stop-loss compute method (for update)
        self.sl_tf = 0     # timeframe model of the stop-loss (not the float value)

        self.last_tp_ot = [0, 0]
        self.tp_mode = 0   # integer that could serves as take-profit compute method (for update)
        self.tp_tf = 0     # timeframe model of the take-profit (not the float value)

        self.context = None  # reference to an object concerning the context of the trade (ref from StrategySignal.context)

        self._stats = {
            'best-price': 0.0,
            'best-timestamp': 0.0,
            'worst-price': 0.0,
            'worst-timestamp': 0.0,
            'entry-order-type': Order.ORDER_LIMIT,
            'take-profit-order-type': Order.ORDER_LIMIT,
            'stop-order-type': Order.ORDER_MARKET,
            'first-realized-entry-timestamp': 0.0,
            'first-realized-exit-timestamp': 0.0,
            'last-realized-entry-timestamp': 0.0,
            'last-realized-exit-timestamp': 0.0,
            'unrealized-profit-loss': 0.0,
            'profit-loss-currency': "",
            'entry-fees': 0.0,
            'exit-fees': 0.0,
            'exit-reason': StrategyTrade.REASON_NONE,
            'conditions': {}
        }

        self._extra = {}

    #
    # getters
    #

    @classmethod
    def version(cls):
        return cls.VERSION

    @classmethod
    def is_margin(cls):
        """
        Overrides, must return true if the trader is margin based.
        """
        return False

    @classmethod
    def is_spot(cls):
        """
        Overrides, must return true if the trader is spot based.
        """
        return False

    @property
    def trade_type(self):
        return self._trade_type

    @property
    def entry_state(self):
        return self._entry_state

    @property
    def exit_state(self):
        return self._exit_state   

    @property
    def direction(self):
        return self.dir
    
    def close_direction(self):
        return -self.dir

    @property
    def entry_open_time(self):
        return self.eot

    @property
    def exit_open_time(self):
        return self.xot

    @property
    def order_quantity(self):
        return self.oq

    @property
    def quantity(self):
        """Synonym for order_quantity"""
        return self.oq

    @property  
    def order_price(self):
        return self.op

    @property
    def take_profit(self):
        return self.tp
    
    @property
    def stop_loss(self):
        return self.sl

    @property
    def entry_price(self):
        return self.aep

    @property
    def exit_price(self):
        return self.axp

    @property
    def exec_entry_qty(self):
        return self.e
    
    @property
    def exec_exit_qty(self):
        return self.x

    @property
    def profit_loss(self):
        return self.pl

    @property
    def timeframe(self):
        return self._timeframe

    @timeframe.setter
    def timeframe(self, timeframe):
        self._timeframe = timeframe

    @property
    def expiry(self):
        return self._expiry

    @property
    def entry_timeout(self):
        return self._entry_timeout

    @property
    def first_realized_entry_time(self):
        return self._stats['first-realized-entry-timestamp']

    @property
    def first_realized_exit_time(self):
        return self._stats['first-realized-exit-timestamp']

    @property
    def last_realized_entry_time(self):
        return self._stats['last-realized-entry-timestamp']

    @property
    def last_realized_exit_time(self):
        return self._stats['last-realized-exit-timestamp']

    @property
    def unrealized_profit_loss(self):
        return self._stats['unrealized-profit-loss']

    @property
    def profit_loss_currency(self):
        return self._stats['profit-loss-currency']

    @property
    def exit_reason(self):
        return self._stats['exit-reason']

    @exit_reason.setter
    def exit_reason(self, reason):
        self._stats['exit-reason'] = reason

    @expiry.setter
    def expiry(self, expiry):
        self._expiry = expiry

    @entry_timeout.setter
    def entry_timeout(self, timeout):
        self._entry_timeout = timeout

    def set_user_trade(self, user_trade=True):
        self._user_trade = user_trade

    def is_user_trade(self):
        return self._user_trade

    @property
    def last_take_profit(self):
        """Last take-profit order creation/modification timestamp"""
        return self.last_tp_ot

    @property
    def last_stop_loss(self):
        """Last stop-loss order creation/modification timestamp"""
        return self.last_stop_ot

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, label):
        self._label = label

    @property
    def is_dirty(self):
        return self._dirty

    #
    # processing
    #

    def open(self, trader, instrument, direction, order_type, order_price, quantity, take_profit, stop_loss, leverage=1.0, hedging=None):
        """
        Order to open a position or to buy an asset.

        @param trader Trader Valid trader handler.
        @param instrument Instrument object.
        @param direction int Order direction (1 or -1)
        @param order_type int Order type (market, limit...)
        @param order_price float Limit order price or None for market
        @param quantity float Quantity in unit of quantity
        @param take_profit float Initial take-profit price or None
        @param stop_loss float Initial stop-loss price or None
        @param leverage float For some brokers leverage multiplier else unused
        @param hedging boolean On margin market if True could open positions of opposites directions
        """
        return False

    def remove(self, trader, instrument):
        """
        Remove the trade and related remaining orders.
        """
        pass

    def can_delete(self):
        """
        Because of the slippage once a trade is closed deletion can only be done once all the quantity of the
        asset or the position are executed.
        """
        if self._entry_state == StrategyTrade.STATE_FILLED and self._exit_state == StrategyTrade.STATE_FILLED:
            # entry and exit are fully filled
            return True

        if self._entry_state == StrategyTrade.STATE_REJECTED:
            # entry rejected
            return True

        if (self._entry_state == StrategyTrade.STATE_CANCELED or self._entry_state == StrategyTrade.STATE_DELETED) and self.e <= 0:
            # entry canceled or deleted and empty
            return True

        return False

    def is_active(self):
        """
        Return true if the trade is active (non-null entry qty, and exit quantity non fully completed).
        """
        if self._exit_state == StrategyTrade.STATE_FILLED:
            return False

        return self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED or self._entry_state == StrategyTrade.STATE_FILLED

    def is_opened(self):
        """
        Return true if the entry trade is opened but no qty filled at this moment time.
        """
        return self._entry_state == StrategyTrade.STATE_OPENED

    def is_canceled(self):
        """
        Return true if the trade is not active, canceled or rejected.
        """
        if self._entry_state == StrategyTrade.STATE_REJECTED:
            return True

        if self._entry_state == StrategyTrade.STATE_CANCELED and self.e <= 0:
            return True

        return False

    def is_opening(self):
        """
        Is entry order in progress.
        """
        return self._entry_state == StrategyTrade.STATE_OPENED or self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED

    def is_closing(self):
        """
        Is close order in progress.
        """
        return self._closing and self._exit_state != StrategyTrade.STATE_FILLED

    def is_closed(self):
        """
        Is trade fully closed (all qty sold).
        """
        return self._exit_state == StrategyTrade.STATE_FILLED

    def is_entry_timeout(self, timestamp, timeout):
        """
        Return true if the trade entry timeout.

        @note created timestamp t must be valid else it will timeout every time.
        """
        return (self._entry_state == StrategyTrade.STATE_OPENED) and (self.e == 0) and (self.eot > 0) and timeout > 0.0 and ((timestamp - self.eot) >= timeout)

    def is_trade_timeout(self, timestamp):
        """
        Return true if the trade timeout.

        @note created timestamp t must be valid else it will timeout every time.
        """
        return (
                (self._entry_state in (StrategyTrade.STATE_PARTIALLY_FILLED, StrategyTrade.STATE_FILLED)) and
                (self._expiry > 0.0) and (self.e > 0) and (self.eot > 0) and (timestamp > 0.0) and ((timestamp - self.eot) >= self._expiry)
            )

    def is_duration_timeout(self, timestamp, duration):
        """
        Return true if the trade timeout after given duration.

        @note created timestamp t must be valid else it will timeout every time.
        """
        return (
                (self._entry_state in (StrategyTrade.STATE_PARTIALLY_FILLED, StrategyTrade.STATE_FILLED)) and
                (duration > 0.0) and (self.e > 0) and (self.eot > 0) and (timestamp > 0.0) and ((timestamp - self.eot) >= duration)
            )

    def is_valid(self, timestamp, validity):
        """
        Return true if the trade is not expired (signal still acceptable) and entry quantity not fully filled.
        """
        return (
                ((self._entry_state == StrategyTrade.STATE_OPENED or self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED) and
                (validity > 0.0) and (timestamp > 0.0) and ((timestamp - self.entry_open_time) <= validity))
            )

    def cancel_open(self, trader, instrument):
        """
        Cancel the entiere or remaining open order.
        """
        return False

    def cancel_close(self, trader, instrument):
        """
        Cancel the entiere or remaining close order.
        """
        return False

    def modify_take_profit(self, trader, instrument, limit_price):
        """
        Create/modify the take-order limit order or position limit.
        """
        return self.NOTHING_TO_DO

    def modify_stop_loss(self, trader, instrument, stop_price):
        """
        Create/modify the stop-loss taker order or position limit.
        """
        return self.NOTHING_TO_DO

    def modify_oco(self, trader, instrument, limit_price, stop_price):
        """
        Create/modify the OCO order with both take-profit and stop-loss orders.
        """
        return self.NOTHING_TO_DO

    def close(self, trader, instrument):
        """
        Close the position or sell the asset.
        """
        return self.NOTHING_TO_DO

    def has_stop_order(self):
        """
        Overrides, must return true if the trade have a broker side stop order, else local trigger stop.
        """
        return False

    def has_limit_order(self):
        """
        Overrides, must return true if the trade have a broker side limit order, else local take-profit stop
        """
        return False

    def has_oco_order(self):
        """
        Overrides, must return true if the trade have a broker side OCO order
        """
        return False

    def support_both_order(self):
        """
        Overrides, must return true if the trader support stop and limit order at the same time
        """
        return False

    def can_modify_limit_order(self, timestamp, max_count=1, timeout=10.0):
        """
        Can modify the limit order according to current timestamp and previous limit order timestamp,
        and max change per count duration in seconds.
        """
        if self.last_tp_ot[0] <= 0 or self.last_tp_ot[1] <= 0:
            return True

        if timestamp - self.last_tp_ot[0] < timeout:
            return True

        if not self.has_limit_order():
            return True

        return False

    def can_modify_stop_order(self, timestamp, max_count=1, timeout=10.0):
        """
        Can modify the stop order according to current timestamp and previous stop order timestamp,
        and max change per count duration in seconds.
        """
        if self.last_stop_ot[0] <= 0 or self.last_stop_ot[1] <= 0:
            return True

        if timestamp - self.last_stop_ot[0] < timeout:
            return True

        if not self.has_stop_order():
            return True

        return False

    #
    # signals
    #

    def order_signal(self, signal_type, data, ref_order_id, instrument):
        pass

    def position_signal(self, signal_type, data, ref_order_id, instrument):
        pass

    def is_target_order(self, order_id, ref_order_id):
        return False

    def is_target_position(self, position_id, ref_order_id):
        return False

    def update_dirty(self, trader, instrument):
        pass

    #
    # Helpers
    #

    def direction_to_str(self):
        if self.dir > 0:
            return 'long'
        elif self.dir < 0:
            return 'short'
        else:
            return ''

    def direction_from_str(self, direction):
        if direction == 'long':
            self.dir = 1
        elif direction == 'short':
            self.dir = -1
        else:
            self.dir = 0

    def state_to_str(self):
        """
        Get a string for the state of the trade (only for display usage).
        """
        if self._entry_state == StrategyTrade.STATE_NEW:
            # entry is new, not ordered
            return 'new'
        elif self._entry_state == StrategyTrade.STATE_OPENED:
            # the entry order is created, waiting for filling
            return 'opened'
        elif self._entry_state == StrategyTrade.STATE_REJECTED:
            # the entry order is rejected, trade must be deleted
            return 'rejected'
        elif self._exit_state == StrategyTrade.STATE_REJECTED and self.e > self.x:
            # exit order is rejectect but the exit quantity is not fully filled (x < e), this case must be managed
            return 'problem'
        elif self._entry_state == StrategyTrade.STATE_PARTIALLY_FILLED:
            # entry order filling until complete
            return 'filling'
        elif self._exit_state == StrategyTrade.STATE_PARTIALLY_FILLED:
            # exit order filling until complete
            return 'closing'
        elif self._entry_state == StrategyTrade.STATE_FILLED and self._exit_state == StrategyTrade.STATE_FILLED:
            # entry and exit are completed
            return 'closed'
        elif self._entry_state == StrategyTrade.STATE_CANCELED and self.e <= 0: 
            # not entry quantity and entry order canceled
            return 'canceled'
        elif self._entry_state == StrategyTrade.STATE_FILLED:
            # entry order completed
            return 'filled'
        else:
            # any others case meaning pending state
            return 'waiting'

    def timeframe_to_str(self):
        return timeframe_to_str(self._timeframe)

    def trade_type_to_str(self):
        if self._trade_type == StrategyTrade.TRADE_ASSET:
            return 'asset'
        elif self._trade_type == StrategyTrade.TRADE_MARGIN:
            return 'margin'
        elif self._trade_type == StrategyTrade.TRADE_IND_MARGIN:
            return 'ind-margin'
        elif self._trade_type == StrategyTrade.TRADE_POSITION:
            return 'position'
        else:
            return "undefined"

    @staticmethod
    def trade_type_from_str(self, trade_type):
        if trade_type == 'asset':
            return StrategyTrade.TRADE_ASSET
        elif trade_type == 'margin':
            return StrategyTrade.TRADE_MARGIN
        elif trade_type == 'ind-margin':
            return StrategyTrade.TRADE_IND_MARGIN
        elif trade_type == 'position':
            return StrategyTrade.TRADE_POSITION
        else:
            return StrategyTrade.TRADE_UNDEFINED

    def trade_state_to_str(self, trade_state):
        if trade_state == StrategyTrade.STATE_NEW:
            return 'new'
        elif trade_state == StrategyTrade.STATE_REJECTED:
            return 'rejected'
        elif trade_state == StrategyTrade.STATE_DELETED:
            return 'deleted'
        elif trade_state == StrategyTrade.STATE_CANCELED:
            return 'canceled'
        elif trade_state == StrategyTrade.STATE_OPENED:
            return 'opened'
        elif trade_state == StrategyTrade.STATE_PARTIALLY_FILLED:
            return 'partially-filled'
        elif trade_state == StrategyTrade.STATE_FILLED:
            return 'filled'
        else:
            return "undefined"

    @staticmethod
    def trade_state_from_str(self, trade_state):
        if trade_state == 'new':
            return StrategyTrade.STATE_NEW
        elif trade_type == 'rejected':
            return StrategyTrade.STATE_REJECTED
        elif trade_type == 'deleted':
            return StrategyTrade.STATE_DELETED
        elif trade_type == 'canceled':
            return StrategyTrade.STATE_CANCELED
        elif trade_type == 'opened':
            return StrategyTrade.STATE_OPENED
        elif trade_type == 'partially-filled':
            return StrategyTrade.STATE_PARTIALLY_FILLED
        elif trade_type == 'filled':
            return StrategyTrade.STATE_FILLED
        else:
            return StrategyTrade.STATE_UNDEFINED

    @staticmethod
    def reason_to_str(reason):
        if reason == StrategyTrade.REASON_NONE:
            return "undefined"
        elif reason == StrategyTrade.REASON_MARKET_TIMEOUT:
            return "timeout-market"
        elif reason == StrategyTrade.REASON_CLOSE_MARKET:
            return "close-market"
        elif reason == StrategyTrade.REASON_STOP_LOSS_MARKET:
            return "stop-loss-market"
        elif reason == StrategyTrade.REASON_STOP_LOSS_LIMIT:
            return "stop-loss-limit"
        elif reason == StrategyTrade.REASON_TAKE_PROFIT_LIMIT:
            return "take-profit-limit"
        elif reason == StrategyTrade.REASON_TAKE_PROFIT_MARKET:
            return "take-profit-market"
        elif reason == StrategyTrade.REASON_CANCELED_TARGETED:
            return "canceled-targeted"
        elif reason == StrategyTrade.REASON_CANCELED_TIMEOUT:
            return "canceled-timeout"
        else:
            return "undefined"

    #
    # presistance
    #

    def dump_timestamp(self, timestamp):
        return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    def load_timestamp(self, datetime_str):
        if datetime_str:
            return datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=UTC()).timestamp()
        else:
            return 0

    def dumps(self):
        """
        Override this method to make a dumps for the persistance.
        @return dict with at least as defined in this method.
        """
        return {
            'version': self.version(),
            'id': self.id,
            'trade': self._trade_type,  #  self.trade_type_to_str(),
            'entry-timeout': self._entry_timeout,  # self.timeframe_to_str(self._entry_timeout),
            'expiry': self._expiry,
            'entry-state': self._entry_state,  # self.trade_state_to_str(self._entry_state),
            'exit-state': self._exit_state,  # self.trade_state_to_str(self._exit_state),
            'closing': self._closing,
            'timeframe': self._timeframe,  # self.timeframe_to_str(),
            'user-trade': self._user_trade,
            'label': self._label,
            'avg-entry-price': self.aep,
            'avg-exit-price': self.axp,
            'take-profit-price': self.tp,
            'take-profit-mode': self.tp_mode,
            'take-profit-timeframe': self.tp_tf.timeframe if self.tp_tf else 0,
            'stop-loss-price': self.sl,
            'stop-loss-mode': self.sl_mode,
            'stop-loss-timeframe': self.sl_tf.timeframe if self.sl_tf else 0,
            'direction': self.dir,  # self.direction_to_str(),
            'entry-open-time': self.eot,  # self.dump_timestamp(self.eot),
            'exit-open-time': self.xot,  # self.dump_timestamp(self.xot),
            'order-qty': self.oq,
            'filled-entry-qty': self.e,
            'filled-exit-qty': self.x,
            'profit-loss-rate': self.pl,
            'exit-trades': self.exit_trades,
            'last-take-profit-order-time': self.last_tp_ot,
            'last-stop-loss-order-time': self.last_stop_ot,
            'statistics': self._stats,
            'context': self.context.dumps() if self.context else None,
            'extra': self._extra,
        }

    def loads(self, data, context_builder=None):
        """
        Override this method to make a loads for the persistance model.
        @return True if success.
        """
        self.id = data.get('id', -1)
        self._trade_type = data.get('trade', 0)  # self.trade_type_from_str(data.get('type', ''))
        self._entry_timeout = data.get('entry-timeout', 0)
        self._expiry = data.get('expiry', 0)
        self._entry_state = data.get('entry-state', 0)  # self.trade_state_from_str(data.get('entry-state', ''))
        self._exit_state = data.get('exit-state', 0)  # self.trade_state_from_str(data.get('exit-state', ''))
        self._closing = data.get('closing', False)
        self._timeframe = data.get('timeframe', 0)  # timeframe_from_str(data.get('timeframe', '4h'))
        self._user_trade = data.get('user-trade')
        self._label = data.get('label', "")

        self._operations = []
        self._next_operation_id = -1

        self.dir = data.get('direction', 0)  # self.direction_from_str(data.get('direction', ''))
        self.oq = data.get('order-qty', 0.0)

        self.tp = data.get('take-profit-price', 0.0)
        self.sl = data.get('stop-loss-price', 0.0)

        self.aep = data.get('avg-entry-price', 0.0)
        self.axp = data.get('avg-exit-price', 0.0)
       
        self.eot = data.get('entry-open-time', 0)  # self.load_timestamp(data.get('entry-open-datetime'))
        self.xot = data.get('exit-open-time', 0)  # self.load_timestamp(data.get('exit-open-datetime'))

        self.e = data.get('filled-entry-qty', 0.0)
        self.x = data.get('filled-exit-qty', 0.0)

        self.pl = data.get('profit-loss-rate', 0.0)

        self.last_tp_ot = data.get('last-take-profit-order-time')
        self.last_stop_ot = data.get('last-stop-loss-order-time')

        self.exit_trades = data.get('exit-trades', {})

        self._stats = data.get('statistics', {
            'best-price': 0.0,
            'best-timestamp': 0.0,
            'worst-price': 0.0,
            'worst-timestamp': 0.0,
            'entry-order-type': Order.ORDER_LIMIT,
            'take-profit-order-type': Order.ORDER_LIMIT,
            'stop-order-type': Order.ORDER_MARKET,
            'entry-fees': 0.0,
            'exit-fees': 0.0,
            'conditions': {}
        })

        self._extra = data.get('extra', {})

        if context_builder and data.get('context'):
            self.context = context_builder.loads(data['context'])
        else:
            self.context = None

        return True

    def check(self, trader, instrument):
        """
        Check refered orders and positions exists and quantities too.
        @return True if success.
        """
        return False

    #
    # stats
    #

    def update_stats(self, last_price, timestamp):
        if self.is_active():
            if self.dir > 0:
                if last_price > self._stats['best-price']:
                    self._stats['best-price'] = last_price
                    self._stats['best-timestamp'] = timestamp

                if last_price < self._stats['worst-price'] or not self._stats['worst-price']:
                    self._stats['worst-price'] = last_price
                    self._stats['worst-timestamp'] = timestamp

            elif self.dir < 0:
                if last_price < self._stats['best-price'] or not self._stats['best-price']:
                    self._stats['best-price'] = last_price
                    self._stats['best-timestamp'] = timestamp

                if last_price > self._stats['worst-price']:
                    self._stats['worst-price'] = last_price
                    self._stats['worst-timestamp'] = timestamp

    def best_price(self):
        return self._stats['best-price']

    def worst_price(self):
        return self._stats['worst-price']

    def best_price_timestamp(self):
        return self._stats['best-timestamp']

    def worst_price_timestamp(self):
        return self._stats['worst-timestamp']

    def get_stats(self):
        return self._stats

    def add_condition(self, name, data):
        self._stats['conditions'][name] = data

    def get_conditions(self):
        return self._stats['conditions']

    def entry_fees(self):
        """Realized entry fees cost (not rate)"""
        return self._stats['entry-fees']

    def entry_fees_rate(self):
        """Realized entry fees rate"""
        if self.e > 0:
            return self._stats['entry-fees'] / self.e

        return 0.0

    def exit_fees(self):
        """Realized exit fees cost (not rate)"""
        return self._stats['exit-fees']

    def exit_fees_rate(self):
        """Realized entry fees rate"""
        if self.x > 0:
            return self._stats['exit-fees'] / self.x

        return 0.0

    def estimate_profit_loss(self, instrument):
        """
        During the trade open, compute an estimation of the unrealized profit/loss rate.
        """
        # estimation at close price
        if self.direction > 0 and self.entry_price > 0:
            profit_loss = (instrument.close_exec_price(self.direction) - self.entry_price) / self.entry_price
        elif self.direction < 0 and self.entry_price > 0:
            profit_loss = (self.entry_price - instrument.close_exec_price(self.direction)) / self.entry_price
        else:
            profit_loss = 0.0

        # minus realized entry fees rate
        profit_loss -= self.entry_fees_rate()

        # count the exit fees related to limit order type
        if self._stats['take-profit-order-type'] in (Order.ORDER_LIMIT, Order.ORDER_STOP_LIMIT, Order.ORDER_TAKE_PROFIT_LIMIT):
            profit_loss -= instrument.maker_fee
        elif self._stats['take-profit-order-type'] in (Order.ORDER_MARKET, Order.ORDER_STOP, Order.ORDER_TAKE_PROFIT):
            profit_loss -= instrument.taker_fee

        return profit_loss

    def estimate_exit_fees_rate(self, instrument):
        """
        Return the estimate fees rate for the exit order.
        """
        # count the exit fees related to limit order type
        if self._stats['take-profit-order-type'] in (Order.ORDER_LIMIT, Order.ORDER_STOP_LIMIT, Order.ORDER_TAKE_PROFIT_LIMIT):
            return instrument.maker_fee
        elif self._stats['take-profit-order-type'] in (Order.ORDER_MARKET, Order.ORDER_STOP, Order.ORDER_TAKE_PROFIT):
            return instrument.taker_fee

        return 0.0

    #
    # extra
    #

    def set(self, key, value):
        """
        Add a key:value paire in the extra member dict of the trade.
        It allow to add you internal trade data, states you want to keep during the live of the trade and even in persistency
        """
        self._extra[key] = value

    def unset(self, key):
        """Remove a previously set extra key"""
        if key in self._extra:
            del self._extra[key]

    def get(self, key, default=None):
        """Return a value for a previously defined key or default value if not exists"""
        return self._extra.get(key, default)

    #
    # operations
    #

    @property
    def operations(self):
        """
        List all pending/peristants operations
        """
        return self._operations

    def cleanup_operations(self):
        """
        Regenerate the list of operations by removing the finished operations.
        """
        ops = []

        for operation in self._operations:
            if not operation.can_delete():
                ops.append(operation)

        # replace the operations list
        self._operations = ops

    def add_operation(self, trade_operation):
        trade_operation.set_id(self._next_operation_id)
        self._next_operation_id += 1

        self._operations.append(trade_operation)

    def remove_operation(self, trade_operation_id):
        for operation in self._operations:
            if operation.id == trade_operation_id:
                self._operations.remove(operation)
                return True

        return False

    def has_operations(self):
        return len(self._operations) > 0

    #
    # dumps for notify/history
    #

    def dumps_notify_entry(self, timestamp, strategy_trader):
        """
        Dumps to dict for notify/history.
        """
        return {
            'version': self.version(),
            'trade': self.trade_type_to_str(),
            'id': self.id,
            'app-name': strategy_trader.strategy.name,
            'app-id': strategy_trader.strategy.identifier,
            'timestamp': timestamp,
            'symbol': strategy_trader.instrument.market_id,
            'way': "entry",
            'entry-timeout': timeframe_to_str(self._entry_timeout),
            'expiry': self._expiry,
            'timeframe': timeframe_to_str(self._timeframe),
            'is-user-trade': self._user_trade,
            'label': self._label,
            'direction': self.direction_to_str(),
            'order-price': strategy_trader.instrument.format_price(self.op),
            'order-qty': strategy_trader.instrument.format_quantity(self.oq),
            'stop-loss-price': strategy_trader.instrument.format_price(self.sl),
            'take-profit-price': strategy_trader.instrument.format_price(self.tp),
            'avg-entry-price': strategy_trader.instrument.format_price(self.aep),
            'filled-entry-qty': strategy_trader.instrument.format_quantity(self.e),
            'entry-open-time': self.dump_timestamp(self.eot),
            'stats': {
                'entry-order-type': order_type_to_str(self._stats['entry-order-type']),
            }
        }

    def dumps_notify_exit(self, timestamp, strategy_trader):
        """
        Dumps to dict for notify/history.
        """
        return {
            'version': self.version(),
            'trade': self.trade_type_to_str(),
            'id': self.id,
            'app-name': strategy_trader.strategy.name,
            'app-id': strategy_trader.strategy.identifier,
            'timestamp': timestamp,
            'symbol': strategy_trader.instrument.market_id,
            'way': "exit",
            'entry-timeout': timeframe_to_str(self._entry_timeout),
            'expiry': self._expiry,
            'timeframe': timeframe_to_str(self._timeframe),
            'is-user-trade': self._user_trade,
            'label': self._label,
            'direction': self.direction_to_str(),
            'order-price': strategy_trader.instrument.format_price(self.op),
            'order-qty': strategy_trader.instrument.format_quantity(self.oq),
            'stop-loss-price': strategy_trader.instrument.format_price(self.sl),
            'take-profit-price': strategy_trader.instrument.format_price(self.tp),
            'avg-entry-price': strategy_trader.instrument.format_price(self.aep),
            'avg-exit-price': strategy_trader.instrument.format_price(self.axp),
            'entry-open-time': self.dump_timestamp(self.eot),
            'exit-open-time': self.dump_timestamp(self.xot),
            'filled-entry-qty': strategy_trader.instrument.format_quantity(self.e),
            'filled-exit-qty': strategy_trader.instrument.format_quantity(self.x),
            'profit-loss-pct': round(self.pl * 100.0, 2),
            'num-exit-trades': len(self.exit_trades),
            'stats': {
                'best-price': strategy_trader.instrument.format_price(self._stats['best-price']),
                'best-datetime': self.dump_timestamp(self._stats['best-timestamp']),
                'worst-price': strategy_trader.instrument.format_price(self._stats['worst-price']),
                'worst-datetime': self.dump_timestamp(self._stats['worst-timestamp']),
                'entry-order-type': order_type_to_str(self._stats['entry-order-type']),
                'first-realized-entry-datetime': self.dump_timestamp(self._stats['first-realized-entry-timestamp']),
                'first-realized-exit-datetime': self.dump_timestamp(self._stats['first-realized-exit-timestamp']),
                'last-realized-entry-datetime': self.dump_timestamp(self._stats['last-realized-entry-timestamp']),
                'last-realized-exit-datetime': self.dump_timestamp(self._stats['last-realized-exit-timestamp']),
                'profit-loss-currency': self._stats['profit-loss-currency'],
                'profit-loss': self._stats['unrealized-profit-loss'],
                'entry-fees': self._stats['entry-fees'],
                'exit-fees': self._stats['exit-fees'],
                'exit-reason': StrategyTrade.reason_to_str(self._stats['exit-reason'])
            }
        }

    def dumps_notify_update(self, timestamp, strategy_trader):
        # @todo
        return {}
