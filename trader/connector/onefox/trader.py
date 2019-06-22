# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Trader/autotrader connector for 1fox.com

import http.client
import urllib
import json
import time
import datetime

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.trader import Trader

from .account import OneFoxAccount
from trader.position import Position as TraderPosition
from trader.order import Order
from terminal.terminal import Terminal

from connector.onefox.connector import OneFoxConnector
from config import config

from trader.connector.onebroker.trader import OneBrokerTrader


class OneFoxTrader(OneBrokerTrader):

	def __init__(self, service):
		super().__init__(service, name="1fox.com")

		self._host = "1fox.com"
		self._base_url = "/api/v1/"

		self._account = OneFoxAccount(self)
		self._connector = None

	def connect(self):
		super().connect()

		self.lock()

		identity = self.service.identity(self._name)
		if identity:
			self._host = identity.get('host')

			self.connector = OneFoxConnector(
				self.service,
				identity.get('api-key'),
				self._host)

		self.connector.connect()

		self.unlock()

	def tradeable(self, market_id):
		"""
		Return True if the trader accept order and market id is tradeable.
		"""
		# return  self._watcher.connected and market_id in self._markets
		# @todo markets...
		return  self._connector and self._connector.connected
