# @date 2019-01-04
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# tiingo.com WS client implementation

import json
import websocket

from terminal.terminal import Terminal

import logging
logger = logging.getLogger('siis.connector.tiingo')


class TiingoWS(object):
	"""
	Tiinger WS client.

	IEX
	===

	- Real-time (Latest) Data : wss://api.tiingo.com/iex

	Crypto
	======

	- Real-time (Latest) Data :wss://api.tiingo.com/crypto

	Message type :

		"A" for new data
		"U" for updating existing data
		"D" for deleing existing data
		"I" for informational/meta data
		"E" for error messages

	@todo
	"""

	def __init__(self, session, api_key):
		self._session = session
		self.__api_key = api_key

		self._ws = None

	def connect(self):
		try:
			self._ws = create_connection("wss://api.tiingo.com/test")
		except Exception as e:
			logger.error(repr(e))

	def disconnect(self):
		if self._ws:
			try:
				self._ws.close()
			except Exception as e:
				pass

			self._ws = None

	def subscribe(self, sub):
		subscribe = {
			'eventName':'subscribe',
			'eventData': {
				'authToken': self.__api_key
			}
		}

		self._ws.send(json.dumps(subscribe))

	def _message(self, data):
		pass
