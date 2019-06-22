# @date 2018-08-23
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# HTTPS connector for 1fox.com (dup from 1broker.com connector)

import http.client
import urllib
import json
import datetime
import base64

from terminal.terminal import Terminal
from connector.onebroker.connector import OneBrokerConnector


from config import config


class OneFoxConnector(OneBrokerConnector):

	def __init__(self, service, api_key, host="1fox.com"):
		super().__init__(service, api_key, host or "1fox.com")

		self._base_url = "/api/v1/"
