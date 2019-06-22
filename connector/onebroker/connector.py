# @date 2018-08-23
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# HTTPS connector for 1broker.com

import http.client
import urllib
import json
import datetime
import base64

from terminal.terminal import Terminal

from config import config


class OneBrokerConnector(object):

	def __init__(self, service, api_key, host="1broker.com"):
		self._host = host or "1broker.com"
		self._base_url = "/api/v2/"
		self._timeout = 7
		self._connected = False

		self.__api_key = api_key

	# @todo remove me once converted
	@property
	def api_key(self):
		return self.__api_key

	def connect(self):
		self._conn = http.client.HTTPSConnection(self._host, timeout=10)

		var = {
			'pretty': 'false',
			'token': self.__api_key
		}

		url = self._base_url + 'user/details.php?' + urllib.parse.urlencode(var)
		self._conn.request("GET", url)

		response = self._conn.getresponse() 
		data = response.read()

		if response.status == 200:
			self._connected = True
		else:
			self._connected = False

	def disconnect(self):
		self._conn = None
		self._connected = False

	def request(path, query=None, postdict=None, verb=None, timeout=None, max_retries=None):
		if not self._connected:
			return None

		# @todo for now it uses directly self._conn
		url = self._host + self._base_url + path

		if timeout is None:
			timeout = self._timeout

		# default to POST if data is attached, GET otherwise
		if not verb:
			verb = 'POST' if postdict else 'GET'

		if max_retries is None:
			max_retries = 0 if verb in ['POST', 'PUT'] else 3

	@property
	def connected(self):
		return self._connected
