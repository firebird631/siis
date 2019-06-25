# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# service worker

class Signal(object):

	SIGNAL_POSITION_ENTER = 0
	SIGNAL_POSITION_EXIT = 1
	SIGNAL_POSITION_SCORIFY = 2
	
	SIGNAL_POSITION_ALERT = 3
	SIGNAL_SERVICE_ALERT = 4
	SIGNAL_WATCHER_ALERT = 5
	SIGNAL_TRADER_ALERT = 6

	SIGNAL_AUTHOR_ADDED = 7
	SIGNAL_AUTHOR_REMOVED = 8

	SIGNAL_POSITION_ENJOY = 9
	SIGNAL_STRATEGY_ENTRY_EXIT = 10     # data is a dict {'trader-name', 'trade-id', 'symbol', 'direction', 'price', 'symbol', 'action', 'rate', 'timestamp', ...}

	SIGNAL_CANDLE_DATA = 100            # data is a pair with (market_id, Candle)
	SIGNAL_TICK_DATA = 101              # data is a pair with (market_id, Tick)
	SIGNAL_CANDLE_DATA_BULK = 102       # data is a tuple of (market_id, tf, Candle[])
	SIGNAL_TICK_DATA_BULK = 103         # data is a tuple of (market_id, tf, Tick[])
	SIGNAL_SOCIAL_ORDER = 104           # data is a tuple with (str market id, dict position details)
	SIGNAL_BUY_SELL_ORDER = 105         # data is BuySellSignal

	SIGNAL_WATCHER_CONNECTED = 200      # data is None
	SIGNAL_WATCHER_DISCONNECTED = 201   # data is None

	SIGNAL_ACCOUNT_DATA = 300           # data is a tuple with (balance, free_margin, pnl, currency, risk_limit)
	SIGNAL_MARKET_DATA = 301            # data is a tuple with (market_id, tradable, timestamp, bid, ofr, base_exchange_rate, contract_size, value_per_pip, vol24h_base, vol24h_quote)
	SIGNAL_MARKET_INFO_DATA = 302       # data is a tuple with (market_id, Market())
	SIGNAL_MARKET_LIST_DATA = 303       # data is an array of tuples of str (market_id, symbol, base, quote)

	SIGNAL_POSITION_OPENED = 400        # data is a (str market id, dict position details, str ref order id)
	SIGNAL_POSITION_UPDATED = 401       # data is a (str market id, dict position details, str ref order id)
	SIGNAL_POSITION_DELETED = 402       # data is a (str market id, str position id, str ref order id)
	SIGNAL_POSITION_AMENDED = 403       # data is a (str market id, dict position details)

	SIGNAL_ORDER_OPENED = 500           # data is a (str market id, dict order details, str ref order id)
	SIGNAL_ORDER_UPDATED = 501          # data is a (str market id, dict order details, str ref order id)
	SIGNAL_ORDER_DELETED = 502          # data is a (str market id, str order id, str ref order id)
	SIGNAL_ORDER_REJECTED = 503         # data is a (str market id, str ref order id)
	SIGNAL_ORDER_CANCELED = 504         # data is a (str market id, str order id, str ref order id)
	SIGNAL_ORDER_TRADED = 505           # data is a (str market id, dict order details, str ref order id)

	SIGNAL_ASSET_DATA = 600             # data is a tuple with (asset_id, asset object)
	SIGNAL_ASSET_DATA_BULK = 601        # data is an array of Asset objects
	SIGNAL_ASSET_UPDATED = 602          # data is a tuple with (asset_id, locked_balance, free_balance)
	SIGNAL_STRATEGY_TRADE_LIST = 603    # data is an array of Strategy(Asset|Margin)Trade objects

	SIGNAL_ORDER_BOOK = 700             # data is a tuple with (market_id, buys array, sells array)

	SIGNAL_TRADE_DATA = 800             # data is a tuple with (market_id, StrategyTrade)
	SIGNAL_TRADE_DATA_BULK = 801        # data is a tuple with (market_id, StrategyTrade[])

	SOURCE_UNDEFINED = 0
	SOURCE_WATCHER = 1
	SOURCE_TRADER = 2
	SOURCE_STRATEGY = 3
	SOURCE_MONITOR = 4

	def __init__(self, source, source_name, signal_type, data):
		self._source = source
		self._source_name = source_name
		self._signal_type = signal_type
		self._data = data

	@property
	def source(self):
		return self._source

	@property
	def source_name(self):
		return self._source_name

	@property
	def signal_type(self):
		return self._signal_type
	
	@property
	def data(self):
		return self._data
