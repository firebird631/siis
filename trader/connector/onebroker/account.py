# @date 2018-08-08
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Account/user model

import http.client
import urllib
import json
import time

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.account import Account
from terminal.terminal import Terminal


class OneBrokerAccount(Account):

	def __init__(self, parent):
		super().__init__(parent)

		self._account_type = Account.TYPE_MARGIN

		self._currency = 'BTC'
		self._currency_ratio = 6600  # @todo need to be get from source at update...

        self._currency_precision = 8
        self._alt_currency_precision = 2

		self._last_update = 0

	def update(self, connector):
		if not connector.connected:
			return

		# @todo update using WS
		# https://1broker.com/api/v2/user/details.php?token=YOUR_API_TOKEN&pretty=true

		# update once per second
		now = time.time()
		if now - self._last_update < 1.0:
			return
		else:
			self._last_update = now

		var = {
			'pretty': 'false',
			'token': connector.api_key
		}

		url = connector._base_url + 'user/details.php?' + urllib.parse.urlencode(var)
		connector._conn.request("GET", url)

		response = connector._conn.getresponse()
		data = response.read()

		if response.status != 200:
			Terminal.inst().error("Http error getting %s user details account !" % (self.name,))
			raise Exception("Http error")

		data = json.loads(data)

		if data['error'] or data['warning']:
			Terminal.inst().error("API error getting %s user details account !" % (self.name,)e)
			Terminal.inst().error(repr(data))
			raise Exception("API error")

		self._name = data['response']['email']
		self._username = data['response']['username']
		self._email = data['response']['email']

		self._balance = float(data['response']['balance'])

		#
		# overview
		# 

		# https://1broker.com/api/v2/user/overview.php?token=YOUR_API_TOKEN&pretty=true
		url = connector._base_url + 'user/overview.php?' + urllib.parse.urlencode(var)
		connector._conn.request("GET", url)

		response = connector._conn.getresponse()	
		data = response.read()

		if response.status != 200:
			Terminal.inst().error("Http error getting %s user overview account !" % (self.name,))
			raise Exception("Http error")

		data = json.loads(data)

		if data['error'] or data['warning']:
			Terminal.inst().error("API error getting %s user overview account !" % (self.name,))
			raise Exception("API error")

		self._net_worth = float(data['response']['net_worth'])
		self._risk_limit = self._net_worth * 200  # hum...

		# @todo position and orders overview, load and map with database previous backup

		# {
		# 	...
		# 	"response": {
		# 	    "username": "example_user",
		# 	    "email": "user@example.com",
		# 	    "balance": "9.1636",
		# 	    "date_created": "2014-11-06T10:34:47Z",
		# 	    "orders_worth": "405",
		# 	    "positions_worth": "424.5548",
		# 	    "net_worth": "2738.7184",
		# 	    "orders_open": [
		# 	        {
		# 	            "order_id": "1650",
		# 	            "symbol": "EURUSD",
		# 	            "margin": "1",
		# 	            "leverage": "200",
		# 	            "direction": "short",
		# 	            "order_type": "Market",
		# 	            "order_type_parameter": "-1",
		# 	            "stop_loss": "0",
		# 	            "take_profit": "0",
		# 	            "shared": true,
		# 	            "date_created": "2016-11-03T15:40:53Z"
		# 	        }
		# 	    ],
		# 	    "positions_open": [
		# 	        {
		# 	            "position_id": "16993",
		# 	            "order_id": "456",
		# 	            "symbol": "DOW",
		# 	            "margin": "1",
		# 	            "leverage": "1",
		# 	            "direction": "long",
		# 	            "entry_price": "18209.40514339",
		# 	            "profit_loss": "-0.0336556",
		# 	            "profit_loss_percent": "-3.37",
		# 	            "value": "0.9663444",
		# 	            "market_close": false,
		# 	            "stop_loss": "0",
		# 	            "take_profit": null,
		# 	            "trailing_stop_loss": false,
		# 	            "shared": true,
		# 	            "copy_of": null,
		# 	            "date_created": "2016-10-24T07:16:55Z"
		# 	        }
		# 	    ]
		# 	}
		# }

		# auto copied trader
    	# https://1broker.com/api/v2/copy_trader/list.php?token=Aa508b7a7a5ffba14908bded38a88ee8&pretty=true
    	# @todo but only for final application because its not the idea

		# {
		#     "server_time": "2018-08-07T19:23:24.254Z",
		#     "error": false,
		#     "warning": false,
		#     "response": [
		#         {
		#             "user_id_copied": "11531",
		#             "username_copied": "wangzai888",
		#             "margin_per_trade": "0.003",
		#             "limit_trades_daily": "50",
		#             "limit_trades_used": "3",
		#             "date_created": "2018-08-02T15:21:07Z",
		#             "profile_image_url": "https://1broker.com/img.php?i=90d58b44eb932fa9"
		#         }
		#     ]
		# }
