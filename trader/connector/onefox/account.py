# @date 2018-08-08
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

import http.client
import urllib
import json
import datetime

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.account import Account

from config import config
from terminal.terminal import Terminal

from trader.connector.onebroker.account import OneBrokerAccount


class OneFoxAccount(OneBrokerAccount):

	def __init__(self, parent):
		super().__init__(parent)

		self._account_type = Account.TYPE_MARGIN

		self._currency = 'BTC'
		self._currency_ratio = 6600  # @todo need to be get from source at update...
