# @date 2019-01-04
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# tiingo.com connector implementation

import time
import json
import requests

from datetime import datetime

import logging
logger = logging.getLogger('siis.connector.tiingo')


class Connector(object):
	"""
	Tiingo HTTP+WS connector.
	
	>> https://www.tiingo.com/account/api/token
	>> https://api.tiingo.com/docs/

	- currency list: https://www.alphavantage.co/physical_currency_list/

	@note API call frequency is 5 calls per minute and 500 calls per day.
	@todo Support max call frequency

	Tiingo
	======
	
	- Meta data : https://api.tiingo.com/tiingo/daily/<ticker>
	- Latest Price : https://api.tiingo.com/tiingo/daily/<ticker>/prices
	- Historical Prices : https://api.tiingo.com/tiingo/daily/<ticker>/prices?startDate=2012-1-1&endDate=2016-1-1

	EIX
	===

	- Real-time (Latest) Data : https://api.tiingo.com/iex/<ticker>
	- Historical Prices : https://api.tiingo.com/iex/<ticker>/prices?startDate=2017-5-22&resampleFreq=5min

	REST API has limits of 2,000 requests/second for the latest data.
	Historical API has a limit of 200/requests a second.

	Crypto
	======

	- Real-time (Latest) Data for specific tickers : https://api.tiingo.com/tiingo/crypto/prices?tickers=btcusd,fldcbtc
	- Historical Prices : https://api.tiingo.com/tiingo/crypto/prices?tickers=btcusd,fldcbtc&startDate=2017-5-22&resampleFreq=5min
	- Top-of-Book Data for specific tickers : https://api.tiingo.com/tiingo/crypto/top?tickers=btcusd,fldcbtc
	"""

	TF_MAP = {
		60: '1min',
		5*60: '5min',
		15*60: '15min',
		30*60: '30min',
		60*60: '60min',
	}

	RATE_LIMIT_PER_SEC = 2000
	HISTORICAL_RATE_LIMIT_PER_SEC = 200

	def __init__(self, service, api_key, host="api.tiingo.com", protocol="https://"):
		self._host = host or "api.tiingo.com"
		self._protocol = protocol

		self._tiingo_base_url = "/tiingo/"
		self._iex_base_url = "/iex/"

		self.__api_key = api_key

		# REST API
		self._session = None
		self._timeout = 7   
		self._retries = 0  # initialize counter

		self._iex_max_api_call_per_sec = Connector.RATE_LIMIT_PER_SEC
		self._iex_max_history_call_per_sec = Connector.HISTORICAL_RATE_LIMIT_PER_SEC

	def connect(self):
		if self._session is None:
			self._session = requests.Session()

			self._session.headers.update({'user-agent': 'siis-' + '0.2'})
			self._session.headers.update({'content-type': 'application/json'})
			self._session.headers.update({'authorization': self.__api_key})

			requestResponse = requests.get("https://api.tiingo.com/api/test?token=" % (self.__api_key,))
			logger.info(requestResponse.json())

			# @todo list stocks
			all_instruments = []

	@property
	def connected(self):
		return self._session is not None

	def disconnect(self):
		if self._session:
			self._session = None

	@property
	def authenticated(self):
		return self.__api_key is not None

	def request(self, path, query=None, postdict=None, verb=None, timeout=None, max_retries=None):
		url = self._protocol + self._host + self._base_url + path
		auth = None

		if timeout is None:
			timeout = self._timeout

		# default to POST if data is attached, GET otherwise
		if not verb:
			verb = 'POST' if postdict else 'GET'

		if max_retries is None:
			max_retries = 0 if verb in ['POST', 'PUT'] else 3

		def retry():
			self._retries += 1
			if self._retries > max_retries:
				raise Exception("Max retries on %s (%s) hit, raising." % (path, json.dumps(postdict or '')))

			return self.request(path, query, postdict, timeout, verb, max_retries)

		# Make the request
		response = None
		try:
			logger.debug("Sending req to %s: %s" % (url, json.dumps(postdict or query or '')))

			req = requests.Request(verb, url, json=postdict, auth=auth, params=query)
			prepped = self._session.prepare_request(req)
			response = self._session.send(prepped, timeout=timeout)
			# Make non-200s throw
			response.raise_for_status()

		except requests.exceptions.HTTPError as e:
			if response is None:
				raise e

			# 401 - Auth error. This is fatal.
			if response.status_code == 401:
				logger.error("API Key or Secret incorrect, please check and restart.")
				logger.error("Error: " + response.text, True)
			
				if postdict:
					# fatal error...
					return False

			# 404, can be thrown if order canceled or does not exist.
			elif response.status_code == 404:
				if verb == 'DELETE':
					logger.error("Unable to contact the Tiingo API (404). ")
					logger.error("Request: %s \n %s" % (url, json.dumps(postdict)))
					raise e

			# 429, ratelimit; cancel orders & wait until X-RateLimit-Reset
			elif response.status_code == 429:
				logger.error("Ratelimited on current request. ")
				logger.error("Request: %s \n %s" % (url, json.dumps(postdict)))

				to_sleep = 1.0
				# # Figure out how long we need to wait.
				# ratelimit_reset = response.headers['X-RateLimit-Reset']
				# to_sleep = int(ratelimit_reset) - int(time.time()) + 1.0  # add 1.0 more second be we still have issues
				# reset_str = datetime.fromtimestamp(int(ratelimit_reset)).strftime('%X')

				# logger.info("Your ratelimit will reset at %s. Sleeping for %d seconds." % (reset_str, to_sleep), True)
				time.sleep(to_sleep)

				# Retry the request
				return retry()

			# 503 - temporary downtime, likely due to a deploy. Try again
			elif response.status_code == 503:
				logger.warning("Unable to contact the Tiingo API (503), retrying.")
				logger.warning("Request: %s \n %s" % (url, json.dumps(postdict)))

				time.sleep(5)

				return retry()

			elif response.status_code == 400:
				error = response.json()['error']
				message = error['message'].lower() if error else ''

				# If we haven't returned or re-raised yet, we get here.
				logger.error("Tiingo unhandled Error: %s: %s" % (e, response.text))
				logger.error("Endpoint was: %s %s: %s" % (verb, path, json.dumps(postdict)))

				raise e

		except requests.exceptions.Timeout as e:
			# Timeout, re-run this request (retry immediately)
			logger.warning("Timed out on request: %s (%s), retrying..." % (path, json.dumps(postdict or '')))
			return retry()

		except requests.exceptions.ConnectionError as e:
			logger.warning("Unable to contact the Tiingo API (%s). Please check the URL. Retrying. ")
			logger.warning("Request: %s %s \n %s" % (e, url, json.dumps(postdict)))

			time.sleep(2)
			return retry()

		# Reset retry counter on success
		self._retries = 0

		return response.content  # .json()

	def fetch_symbol(self, symbol, tf):
		# https://api.tiingo.com/docs/iex/overview
		pass

	def historical_price(self, symbol, tf):
		pass