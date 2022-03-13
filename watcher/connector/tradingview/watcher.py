# @date 2018-08-20
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# tradingview.com watcher implementation

import http.server
import json
import threading
import time
import traceback

import urllib.parse

from watcher.watcher import Watcher
from trader.position import Position
from common.signal import Signal

from instrument.instrument import BuySellSignal

import logging
logger = logging.getLogger("siis.connector.tradingview")
error_logger = logging.getLogger("siis.error.connector.tradingview")


class MyThread(threading.Thread):
	"""
	@todo using HTTPS server.
	"""

	def __init__(self, host, port):
		super().__init__(name="tradingview")

		# self._server = http.server.ThreadingHTTPServer((host, port), MyHttpHandler)
		self._server = http.server.HTTPServer((host, port), MyHttpHandler)
		self._server.runner = self
		self._qlock = threading.RLock()
		self._queries = []

		self.running = False

	def run(self):
		self.running = True
		self._server.serve_forever()

	def terminate(self):
		self._server.shutdown()
		self._server = None		
		self.running = False

	def add_query(self, data):
		self._qlock.acquire()
		self._queries.append(data)
		self._qlock.release()

	def get_queries(self):
		qs = []

		self._qlock.acquire()
		
		for q in self._queries:
			qs.append(q)

		self._queries = []

		self._qlock.release()
		
		return qs


class MyHttpHandler(http.server.BaseHTTPRequestHandler):

	def __init__(self, request, client_address, server):
		super().__init__(request, client_address, server)

	def do_GET(self):
		# return super().do_GET(self)

		self.send_response(200)
		self.send_header('Content-Type', 'text/json')
		self.end_headers()

		# self.path will contain a URL to be fetched by my proxy
		data = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
		result = json.dumps({
			'result': 'ok'
		})

		self.wfile.write(result.encode("utf-8"))
		# self.server.runner.add_query(data)

	def log_message(self, _format, *args):
		# @todo logger
		msg = _format % args
		return


class TradingViewWatcher(Watcher):
	"""
	Its a simple HTTP server listening GET.
	Watcher + connector combined.
	"""

	DEFAULT_EXPIRY_DELAY = 180   # filter 3 min signals

	def __init__(self, service):
		super().__init__("tradingview.com", service, watcher_type=Watcher.WATCHER_BUY_SELL_SIGNAL)

		self._host = "127.0.0.1"
		self._port = 7373
		self._watcher_update = 1
		self._update_count = 1
		self.__api_key = ''

		self._server = None

		identity = service.identity(self._name)
		if identity:
			self._host = identity.get('host', '127.0.0.1')
			self._port = identity.get('port', 7373)
			self.__api_key = identity.get('api-key', '')

	def connect(self):
		super().connect()

		if self._server is not None:
			return

		try:
			self._server = MyThread(self._host, self._port)
			self._server.start()

			self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, (time.time(), None))

			logger.info("Started tradingview HTTP proxy listener")
		except Exception as e:
			logger.error(repr(e))
			error_logger.error(traceback.format_exc())

	def disconnect(self):
		super().disconnect()

		if self._server:
			self._server.terminate()

			if self._server.is_alive():
				self._server.join()

			self._server = None

	def pre_update(self):
		super().pre_update()

		if not self.connected:
			# wait until serving
			self.connect()
			time.sleep(0.5)
			return

	def update(self):
		if not super().update():
			return False

		self.lock()

		queries = self._server.get_queries()

		for q in queries:
			# check api key
			if q.get('apikey', [''])[0] != self.__api_key:
				continue

			signal_id = q.get('id', ['undefined'])[0]
			strategy = q.get('strategy', [''])[0]
			stype = q.get('type', [''])[0]
			direction = q.get('direction', [''])[0]
			action = q.get('action', [''])[0]
			timestamp = q.get('timestamp', [0])[0]
			price = q.get('price', [0.0])[0]

			symbol = q.get('symbol', [''])[0]
			timeframe = q.get('timeframe', [0])[0]
			
			options = {}

			# optional parameters goes in 'options' and begins by "o_"
			for k, v in q.items():
				if k.startswith('o_'):
					options[k.lstrip('o_')] = v

			if not direction:
				continue

			dir_type = Position.LONG if direction == 'long' else Position.SHORT

			# expiry after 180 seconds (@todo are we sure to first filtering here ?)
			now = time.time()
			if timestamp is None or (now - float(timestamp) > TradingViewWatcher.DEFAULT_EXPIRY_DELAY):
				continue

			# send a buy sell signal
			# @todo is it can be something else ?
			bs = BuySellSignal(timestamp, timeframe)

			if stype == 'entry':
				order_type = BuySellSignal.ORDER_ENTRY
			elif stype == 'exit':
				order_type = BuySellSignal.ORDER_EXIT
			else:
				order_type = BuySellSignal.ORDER_ENTRY

			bs.set_data(strategy, order_type, dir_type, price, timeframe)
			bs.params = options

			self.service.notify(Signal.SIGNAL_BUY_SELL_ORDER, self.name, bs)

			# signal_data = {
			# 	'watcher': self.name,      # name of the watcher
			# 	'signal-id': signal_id,    # optional signal identifier
			# 	'timestamp': timestamp,    # mandatory timestamp of the generation of the signal
			# 	'timeframe': timeframe,    # mandatory timeframe used by the signal
			# 	'strategy': strategy,      # if strategy its name
			# 	'symbol': symbol,          # mandatory related symbol
			# 	'type': stype,             # order, trend, support, resistance, idea, info, comment...
			# 	'direction': dir_type,     # direction if order or suggestion
			# 	'price': price,            # price of the order or when the signal was emitted
			# 	'options': options         # any other specifics details
			# }

			# self.service.notify(Signal.SIGNAL_BUY_SELL_ORDER, self.name, signal_data)

		self.unlock()

	def post_update(self):
		super().post_update()
		time.sleep(0.01)

	@property
	def connected(self) -> bool:
		return self._server is not None
