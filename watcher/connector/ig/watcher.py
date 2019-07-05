# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# ig.com watcher implementation

import math
import urllib
import json
import time
import os.path
import traceback

from datetime import datetime

from watcher.watcher import Watcher
from notifier.signal import Signal

from config import config

from terminal.terminal import Terminal
from connector.ig.connector import IGConnector
from connector.ig.lightstreamer import LSClient, Subscription

from instrument.instrument import Instrument, Candle
from database.database import Database

from trader.order import Order
from trader.market import Market

import logging
logger = logging.getLogger('siis.watcher.ig')


class IGWatcher(Watcher):
    """
    IG watcher get price and volumes of instruments in live mode throught websocket API.

    Search Markets: https://demo-api.ig.com/gateway/deal/markets?searchTerm=USDJPY

    https://labs.ig.com/sample-apps/api-companion/index.html
    https://labs.ig.com/sample-apps/streaming-companion/index.html

    - LTV Last traded volume

    >> https://labs.ig.com/streaming-api-reference

    Limits
    ======

    Rest API:
        - Per-app non-trading requests per minute: 60
        - Per-account trading requests per minute: 100 (Applies to create/amend position or working order requests)
        - Per-account non-trading requests per minute: 30
        - Historical price data points per week: 10,000 (Applies to price history endpoints)

    Streaming API:
        - 40 concurrents subscriptions

    Data history:
        - 1 Sec 4 Days
        - 1 to 3 Min 40 Days
        - 5 Min to 4 Hours 360 Days
        - Day 15 years

    @todo get vol24 in base and quote unit
    @todo base_exchange_rate must be updated as price changes

    @todo could use endpoint marketnavigation to get all instruments but its hierarchically queries...
        { "nodes": [{ "id": "668394", "name": "Crypto-monnaie" }, { "id": "5371876", ...
        per nodes id we have then : {"nodes": [{ "id": "668997", "name": "Bitcoin" }, { "id": "1002200", ...
        and finally when we found "markets": [{ "epic": "CS.D.AUDUSD.CFD.IP", ... }]
    """

    MAX_CONCURRENT_SUBSCRIPTIONS = 40

    def __init__(self, service):
        super().__init__("ig.com", service, Watcher.WATCHER_PRICE_AND_VOLUME)

        self._host = "ig.com"
        self._connector = None
        self._lightstreamer = None
        self._subscriptions = []
        self._account_id = ""

        # caches for when a value is not defined
        self._cached_tick = {}

    def connect(self):
        super().connect()

        try:
            self.lock()

            identity = self.service.identity(self._name)
            self._subscriptions = []  # reset previous list

            if identity:
                self._host = identity.get('host')
                self._account_type = "LIVE" if self._host == "api.ig.com" else "demo"
                self._account_id = identity.get('account-id')

                self._connector = IGConnector(
                    self.service,
                    identity.get('username'),
                    identity.get('password'),
                    identity.get('account-id'),
                    identity.get('api-key'),
                    identity.get('host'))

                self._connector.connect()

                # from CST and XST
                password = "CST-%s|XST-%s" % (self._connector.cst, self._connector.xst)
                # logger.info(self._connector.cst, self._connector.xst, self._connector.lightstreamer_endpoint, identity.get('account-id'), self._connector.client_id)

                if self._lightstreamer:
                    # destroy previous connection
                    self._lightstreamer.destroy()

                self._lightstreamer = LSClient(
                    self._connector.lightstreamer_endpoint,  # "https://push.lightstreamer.com",
                    adapter_set="DEFAULT",
                    user=self._connector.client_id,
                    password=password)

                self._lightstreamer.connect()

                # subscribe for account and trades to have a reactive feedback and don't saturate the REST API
                self.subscribe_account(identity.get('account-id'))
                self.subscribe_trades(identity.get('account-id'))

                #
                # default watched instruments
                #

                all_instruments = []

                if '*' in self.configured_symbols():
                    self._available_instruments = set(all_instruments)
                    instruments = all_instruments
                else:
                    instruments = self.configured_symbols()

                # susbcribe for symbols
                for symbol in instruments:
                    # to know when market close but could be an hourly REST API call, but it consume one subscriber...
                    # @todo so maybe prefers REST call hourly ? but need bid/ofr properly defined at signals on trader.market and strategy.instrument !
                    self.subscribe_market(symbol)

                    # tick data
                    self.subscribe_tick(symbol)

                    # ohlc data (now generated)
                    # for tf in IGWatcher.STORED_TIMEFRAMES:
                    #     self.subscribe_ohlc(symbol, tf)

                    self.insert_watched_instrument(symbol, [0])

            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, time.time())

        except Exception as e:
            logger.error(repr(e))
            logger.error(traceback.format_exc())

            self._connector = None
            self._lightstreamer = None
        finally:
            self.unlock()

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self):
        return self._connector is not None and self._connector.connected

    def subscribe_account(self, account_id):
        fields = ["PNL", "AVAILABLE_TO_DEAL", "MARGIN", "FUNDS", "AVAILABLE_CASH"]

        subscription = Subscription(
                mode="MERGE",
                items=["ACCOUNT:"+account_id],
                fields=fields,
                adapter="")

        self.subscribe(subscription)
        subscription.addlistener(self, IGWatcher.on_account_update)

    def subscribe_trades(self, account_id):
        fields = ["CONFIRMS", "WOU", "OPU"]

        subscription = Subscription(
                mode="DISTINCT",
                items=["TRADE:"+account_id],
                fields=fields,
                adapter="")

        self.subscribe(subscription)
        subscription.addlistener(self, IGWatcher.on_trade_update)

    def subscribe_tick(self, instrument):
        """
        Subscribe to an instrument tick updates.
        """
        fields = ["BID", "OFR", "LTP", "LTV", "TTV", "UTM"]

        subscription = Subscription(
            mode="DISTINCT",
            items=["CHART:"+instrument+":TICK"],
            fields=fields,
            adapter="")

        self.subscribe(subscription)
        subscription.addlistener(self, IGWatcher.on_tick_update)

    # def subscribe_ohlc(self, instrument, timeframe):
    #     """
    #     Subscribe to an instrument. Timeframe must be greater than 0.
    #     """
    #     fields = [
    #         "BID_OPEN", "OFR_OPEN",
    #         "BID_CLOSE", "OFR_CLOSE",
    #         "BID_HIGH", "OFR_HIGH",
    #         "BID_LOW", "OFR_LOW",
    #         "LTP", "LTV", "TTV", "UTM",
    #         "CONS_END"
    #     ]

    #     if timeframe == Instrument.TF_SEC:
    #         tf = "SECOND"
    #     elif timeframe == Instrument.TF_MIN:
    #         tf = "1MINUTE"
    #     elif timeframe == Instrument.TF_5MIN:
    #         tf = "5MINUTE"
    #     elif timeframe == Instrument.TF_HOUR:
    #         tf = "HOUR"
    #     else:
    #         return

    #     subscription = Subscription(
    #         mode="MERGE",
    #         items=["CHART:"+instrument+":"+tf],
    #         fields=fields,
    #         adapter="")

    #     self.subscribe(subscription)
    #     subscription.addlistener(self, IGWatcher.on_ohlc_update)

    def subscribe_market(self, instrument):
        """
        Subscribe to an instrument.
        """
        fields = ["MARKET_STATE", "UPDATE_TIME", "BID", "OFFER"]

        subscription = Subscription(
            mode="MERGE",
            items=["MARKET:"+instrument],
            fields=fields,
            adapter="")

        self.subscribe(subscription)
        subscription.addlistener(self, IGWatcher.on_market_update)

    def subscribe(self, subscription):
        """
        Registering the Subscription
        """
        sub_key = self._lightstreamer.subscribe(subscription)
        self._subscriptions.append(sub_key)

        return sub_key

    def unsubscribe(self, sub_key):
        if sub_key in self._subscriptions:
            self._lightstreamer.unsubscribe(sub_key)
            del self._subscriptions[sub_key]

    def disconnect(self):
        super().disconnect()

        try:
            self.lock()

            if self._lightstreamer:
                # if self._lightstreamer.connected:
                #   for sub_key in self._subscriptions:
                #       self._lightstreamer.unsubscribe(sub_key)

                self._subscriptions = []
                self._lightstreamer.disconnect()
                self._lightstreamer._join()
                self._lightstreamer = None

            if self._connector:
                self._connector.disconnect()
                self._connector = None

        except Exception:
            logger.error(traceback.format_exc())
        finally:
            self.unlock()

    def pre_update(self):
        super().pre_update()

        if self._connector is None or not self._connector.connected or self._lightstreamer is None or not self._lightstreamer.connected:
            self._connector = None
            self.connect()

            if not self.connected:
                # retry in 2 second
                time.sleep(2.0)

            return

    def update(self):
        if not super().update():
            return False

        if not self.connected:
            return False

        #
        # ohlc close/open
        #

        self.lock()
        self.update_from_tick()
        self.unlock()

        #
        # market info update (each 4h)
        #

        if time.time() - self._last_market_update >= IGWatcher.UPDATE_MARKET_INFO_DELAY:  # only once per 4h
            self.update_markets_info()
            self._last_market_update = time.time()

        return True

    def post_update(self):
        super().post_update()
        time.sleep(0.0005)

    def post_run(self):
        super().post_run()

    #
    # WS data
    #

    @staticmethod
    def on_account_update(self, item_update):
        name = item_update.get('name', '').split(':')

        try:
            if len(name) == 2 and name[0] == 'ACCOUNT' and name[1] == self._account_id:
                # live account updates
                values = item_update['values']

                account_data = (float(values['FUNDS']), float(values['AVAILABLE_TO_DEAL']), float(values['PNL']), None, None)
                self.service.notify(Signal.SIGNAL_ACCOUNT_DATA, self.name, account_data)
        except Exception as e:
            logger.error(repr(e))
            logger.error(traceback.format_exc())                

    @staticmethod
    def on_market_update(self, item_update):
        name = item_update.get('name', '').split(':')

        try:
            if len(name) == 2 and name[0] == 'MARKET':
                # market data instrument by epic
                values = item_update['values']
                epic = name[1]

                ready = values['MARKET_STATE'] == 'TRADEABLE'

                # date of the event 20:36:01 without Z
                if ready:
                    update_time = datetime.strptime(values['UPDATE_TIME'], '%H:%M:%S').timestamp()
                    market_data = (name[1], True, update_time, float(values["BID"]), float(values["OFFER"]), None, None, None, None, None)
                else:
                    update_time = 0
                    market_data = (name[1], False, 0, 0.0, 0.0, None, None, None, None, None)

                self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)
        except Exception as e:
            logger.error(repr(e))
            logger.error(traceback.format_exc())                

    @staticmethod
    def on_tick_update(self, item_update):
        name = item_update.get('name', '').split(':')

        try:
            if len(name) == 3 and name[0] == 'CHART' and name[2] == 'TICK':
                values = item_update['values']
                market_id = name[1]

                bid = None
                ofr = None
                utm = None
                ltv = None

                if values['UTM']:
                    utm = values['UTM']
                elif market_id in self._cached_tick:
                    utm = self._cached_tick[market_id][0]

                if values['BID']:
                    bid = values['BID']
                elif market_id in self._cached_tick:
                    bid = self._cached_tick[market_id][1]

                if values['OFR']:
                    ofr = values['OFR']
                elif market_id in self._cached_tick:
                    ofr = self._cached_tick[market_id][2]

                if values['LTV']:
                    ltv = values['LTV']
                elif market_id in self._cached_tick:
                    ltv = self._cached_tick[market_id][3]

                if utm is None or bid is None or ofr is None:
                    # need all informations, wait the next one
                    return

                # cache for when a value is not defined
                self._cached_tick[market_id] = (utm, bid, ofr, ltv)

                tick = (float(utm) * 0.001, float(bid), float(ofr), float(ltv or "0"))

                # keep last complete tick values for ohlc generation
                self._last_tick[market_id] = tick

                self.service.notify(Signal.SIGNAL_TICK_DATA, self.name, (market_id, tick))

                for tf in Watcher.STORED_TIMEFRAMES:
                    # generate candle per each tf
                    self.lock()
                    candle = self.update_ohlc(market_id, tf, tick[0], tick[1], tick[2], tick[3])
                    self.unlock()

                    if candle is not None:
                        self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (market_id, candle))

                # disabled for now
                if not self._read_only:
                    Database.inst().store_market_trade((self.name, market_id, int(utm), bid, ofr, ltv or 0))

        except Exception as e:
            logger.error(repr(e))
            logger.error(traceback.format_exc())                    

    # @staticmethod
    # def on_ohlc_update(self, item_update):
    #     name = item_update.get('name', '').split(':')

    #     try:
    #         if len(name) == 3 and name[0] == 'CHART':
    #             values = item_update['values']
    #             if values['CONS_END'] == '0':
    #                 # get only consolidated candles
    #                 # @warning It is rarely defined, so many close could be missing, prefers using tick to rebuild ohlc locally
    #                 return

    #             # timeframe
    #             if name[2] == 'SECOND':
    #                 tf = Instrument.TF_SEC
    #             elif name[2] == '1MINUTE':
    #                 tf = Instrument.TF_MIN
    #             elif name[2] == '5MINUTE':
    #                 tf = Instrument.TF_5MIN
    #             elif name[2] == 'HOUR':
    #                 tf = Instrument.TF_HOUR
 
    #             # one of the value could be missing, use the previous from the cache if we have it
    #             if (values['UTM'] is None or values['LTV'] is None or
    #                 values['OFR_OPEN'] is None or values['OFR_HIGH'] is None or values['OFR_LOW'] is None or values['OFR_CLOSE'] is None or 
    #                     values['BID_OPEN'] is None or values['BID_HIGH'] is None or values['BID_LOW'] is None or values['BID_CLOSE'] is None):

    #                 if name[1] not in self._cached_ohlc or tf not in self._cached_ohlc[name[1]]:
    #                     logger.warning("no value and cache miss for %s ohlc in %s (%s)" % (name[1], tf, values))

    #                 if values['UTM'] is None:
    #                     utm = self._cached_ohlc[name[1]][tf][0]
    #                 if values['LTV'] is None:
    #                     ltv = self._cached_ohlc[name[1]][tf][9]

    #             utm = values['UTM']
    #             ltv = values['LTV']

    #             candle = Candle(float(utm) * 0.001, tf)

    #             # if incomplete candle replace ofr by bid or bid by ofr @todo but must be value from previous candle
    #             # but and if we don't have to previous... ok for 1 min but for 1h ? ...
    #             bid_open = values['BID_OPEN'] or values['OFR_OPEN']
    #             bid_high = values['BID_HIGH'] or values['OFR_HIGH']
    #             bid_low = values['BID_LOW'] or values['OFR_LOW']
    #             bid_close = values['BID_CLOSE'] or values['OFR_CLOSE']

    #             ofr_open = values['OFR_OPEN'] or values['BID_OPEN']
    #             ofr_high = values['OFR_HIGH'] or values['BID_HIGH']
    #             ofr_low = values['OFR_LOW'] or values['BID_LOW']
    #             ofr_close = values['OFR_CLOSE'] or values['BID_CLOSE']

    #             candle.set_bid_ohlc(float(bid_open), float(bid_high), float(bid_low), float(bid_close))
    #             candle.set_ofr_ohlc(float(ofr_open), float(ofr_high), float(ofr_low), float(ofr_close))
    #             candle.set_volume(float(values['LTV']) if values['LTV'] else 0.0)
    #             candle.set_consolidated(values['CONS_END'] == '1')

    #             self.service.notify(Signal.SIGNAL_CANDLE_DATA, self.name, (name[1], candle))

    #             if values['CONS_END'] == '1' and not self._read_only:
    #                 # write only consolidated candles. values are string its perfect if not last traded volume then 0
    #                 Database.inst().store_market_ohlc((
    #                     self.name, name[1], int(utm), tf,
    #                     bid_open, bid_high, bid_low, bid_close,
    #                     ofr_open, ofr_high, ofr_low, ofr_close,
    #                     values['LTV'] or "0"))

    #             # cache for when a value is not defined
    #             self._cached_ohlc[name[1]][tf] = (utm, bid_open, bid_high, bid_low, bid_close, ofr_open, ofr_high, ofr_low, ofr_close, ltv)

    #     except Exception as e:
    #         logger.error(repr(e))
    #         logger.error(traceback.format_exc())

    @staticmethod
    def on_trade_update(self, item_update):
        name = item_update.get('name', '').split(':')

        try:
            if len(name) == 2 and name[0] == 'TRADE' and name[1] == self._account_id:
                # live trade updates
                values = item_update['values']

                #
                # order confirms (accepted/rejected)
                #

                if values.get('CONFIRMS'):
                    # not use them because we only want CRUD operations => OPU only so
                    data = json.loads(values.get('CONFIRMS'))
                    logger.info("ig.com CONFIRMS %s" % str(data))

                    epic = data.get('epic')
                    level = float(data['level']) if data.get('level') is not None else None
                    quantity = float(data['size']) if data.get('size') is not None else None

                    if data['dealStatus'] == 'REJECTED':
                        ref_order_id = data['dealReference']

                        # if data['reason'] == 'INSUFFICIENT_BALANCE':
                        #   reason = 'insufficient balance'

                        self.service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (epic, ref_order_id))

                    elif data['dealStatus'] == 'ACCEPTED':
                        # deal confirmed and accepted
                        order_id = data['dealId']
                        ref_order_id = data['dealReference']

                        logger.warning("ig 538 'CONFIRMS' %s" % str(data))

                        # date 2018-09-13T20:36:01.096 without Z
                        event_time = datetime.strptime(data['date'], '%Y-%m-%dT%H:%M:%S.%f').timestamp()

                        if data['direction'] == 'BUY':
                            direction = Order.LONG
                        elif data['direction'] == 'SELL':
                            direction = Order.SHORT
                        else:
                            direction = Order.LONG                        

                        quantity = float(data.get('size')) if data.get('size') is not None else 0.0

                        # don't send event because create_order return True in that case

                        if quantity and level:
                            # signal of updated order
                            order_data = {
                                'id': order_id,
                                # @todo important we want TRADED and UPDATED distinct
                            }

                            # @todo to be completed before signal, but not really necessary we can work with position update
                            # self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (epic, order_data, ref_order_id))

                #
                # active waiting order (open/updated/deleted)
                #

                if values.get('WOU'):
                    data = json.loads(values.get('WOU'))
                    logger.info("ig.com WOU %s" % str(data))

                    order_id = data['dealId']
                    ref_order_id = data['dealReference']

                    epic = data['epic']

                    # level = float(data['level']) if data.get('level') is not None else None
                    # stop_level = float(data['stopLevel']) if data.get('stopLevel') is not None else None
                    # limit_level = float(data['limitLevel']) if data.get('limitLevel') is not None else None
                    # stop_distance = float(data['stopDistance']) if data.get('stopDistance') is not None else None
                    # limit_distance = float(data['limitDistance']) if data.get('limitDistance') is not None else None
                    # profit_loss = float(data['profit']) if data.get('profit') is not None else 0.0
                    # epic, level, guaranteedStop, currency, timeInForce (GOOD_TILL_CANCELLED, GOOD_TILL_DATE)
                    # goodTillDate, size, timestamp, stopDistance, limitDistance

                    # if data['orderType'] == "LIMIT":
                    #   pass
                    # elif data['orderType'] == "STOP":
                    #   pass

                    # status OPEN, DELETED, FULLY_CLOSED
                    if data['status'] == "OPEN":
                        order_data = {
                            'id': order_id,
                            # @todo important
                        }

                        self.service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (epic, order_data, ref_order_id))

                    elif data['status'] == "UPDATED":
                        # signal of updated order
                        order_data = {
                            'id': order_id,
                            # @todo important we want TRADED and UPDATED distinct
                        }

                        self.service.notify(Signal.SIGNAL_ORDER_UPDATED, self.name, (epic, order_data, ref_order_id))

                    elif data['status'] == "DELETED":
                        # signal of deleted order
                        self.service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (epic, order_id, ref_order_id))

                    elif data['status'] == "FULLY_CLOSED":
                        # @todo ??
                        pass

                #
                # active position (open/updated/deleted)
                #

                if values.get('OPU'):
                    data = json.loads(values.get('OPU'))
                    logger.info("ig.com OPU %s" % str(data))

                    if data.get('direction', '') == 'BUY':
                        direction = Order.LONG
                    elif data.get('direction', '') == 'SELL':
                        direction = Order.SHORT
                    else:
                        direction = Order.LONG

                    position_id = data['dealId']
                    ref_order_id = data['dealReference']

                    epic = data.get('epic')
                    quantity = float(data.get('size')) if data.get('size') is not None else 0.0

                    level = float(data['level']) if data.get('level') is not None else None
                    stop_level = float(data['stopLevel']) if data.get('stopLevel') is not None else None
                    limit_level = float(data['limitLevel']) if data.get('limitLevel') is not None else None
                    stop_distance = float(data['stopDistance']) if data.get('stopDistance') is not None else None
                    limit_distance = float(data['limitDistance']) if data.get('limitDistance') is not None else None                        
                    profit_loss = float(data['profit']) if data.get('profit') is not None else 0.0

                    # "dealStatus": "ACCEPTED",
                    # "channel": "WTP", "expiry": "-", "currency": "EUR", "guaranteedStop": false,
                    # @todo "orderType": "LIMIT", "timeInForce": "GOOD_TILL_CANCELLED", "goodTillDate": null

                    # date of the event 2018-09-13T20:36:01.096 without Z
                    event_time = datetime.strptime(data['timestamp'], '%Y-%m-%dT%H:%M:%S.%f').timestamp()

                    # status OPEN, UPDATED, DELETED
                    if data['status'] == "OPEN":
                        # signal of opened position
                        position_data = {
                            'id': position_id,
                            'symbol': epic,
                            'direction': direction,
                            'timestamp': event_time,
                            'quantity': quantity,
                            'exec-price': level,
                            'stop-loss': stop_distance,
                            'take-profit': limit_level,
                            'profit-loss': profit_loss,
                            'cumulative-filled': quantity,
                            'filled': None,  # no have
                            'liquidation-price': None  # no have
                        }

                        self.service.notify(Signal.SIGNAL_POSITION_OPENED, self.name, (epic, position_data, ref_order_id))

                    elif data['status'] == "UPDATED":
                        # signal of updated position
                        position_data = {
                            'id': position_id,
                            'symbol': epic,
                            'direction': direction,
                            'timestamp': event_time,
                            'quantity': quantity,
                            'exec-price': level,
                            'stop-loss': stop_distance,
                            'take-profit': limit_level,
                            # 'profit-currency': '', 'profitCurrency'
                            'profit-loss': profit_loss,
                            # @todo trailingStep, trailingStopDistance, guaranteedStop
                            'cumulative-filled': quantity,
                            'filled': None,  # no have
                            'liquidation-price': None  # no have
                        }

                        self.service.notify(Signal.SIGNAL_POSITION_UPDATED, self.name, (epic, position_data, ref_order_id))

                    elif data['status'] == "DELETED":
                        # signal of updated position
                        position_data = {
                            'id': position_id,
                            'symbol': epic,
                            'direction': direction,
                            'timestamp': event_time,
                            'quantity': quantity,
                            'exec-price': level,
                            'stop-loss': stop_distance,
                            'take-profit': limit_level,
                            # 'profit-currency': '', 'profitCurrency'
                            'profit-loss': profit_loss,
                            # @todo trailingStep, trailingStopDistance, guaranteedStop
                            'cumulative-filled': quantity,
                            'filled': None,  # no have
                            'liquidation-price': None  # no have
                        }

                        self.service.notify(Signal.SIGNAL_POSITION_DELETED, self.name, (epic, position_data, ref_order_id))
                    else:
                        logger.warning("ig l695 'OPU' %s" % str(data))

        except Exception as e:
            logger.error(repr(e))
            logger.error(traceback.format_exc())

    #
    # REST data
    #

    def fetch_market(self, epic):
        """
        Fetch and cache it. It rarely changes, except for base exchange rate, so assume it once for all.
        """
        market_info = self._connector.market(epic)

        instrument = market_info['instrument']
        snapshot = market_info['snapshot']
        dealing_rules = market_info['dealingRules']

        market = Market(epic, instrument['marketId'])

        # cannot interpret this value because IG want it as it is
        market.expiry = instrument['expiry']

        # not perfect but IG does not provides this information
        if instrument["marketId"].endswith(instrument["currencies"][0]["name"]):
            base_symbol = instrument["marketId"][:-len(instrument["currencies"][0]["name"])]
        else:
            base_symbol = instrument["marketId"]

        market.base_exchange_rate = instrument['currencies'][0]['baseExchangeRate']   # "exchangeRate": 0.77

        market.one_pip_means = float(instrument['onePipMeans'].split(' ')[0])
        market.value_per_pip = float(instrument['valueOfOnePip'])
        market.contract_size = float(instrument['contractSize'])
        market.lot_size = float(instrument['lotSize'])

        # @todo how to determine base precision ?
        market.set_base(base_symbol, base_symbol)
        market.set_quote(
            instrument["currencies"][0]["name"],
            instrument["currencies"][0]['symbol'],
            -int(math.log10(market.one_pip_means)))  # "USD", "$" 

        if snapshot:
            market.is_open = snapshot["marketStatus"] == "TRADEABLE"
            market.bid = snapshot['bid']
            market.ofr = snapshot['offer']

        # "marginFactorUnit": "PERCENTAGE" not avalaible if market is down
        if instrument.get('marginFactor') and market.is_open:
            market.margin_factor = float(instrument['marginFactor'])
            margin_factor = instrument['marginFactor']
        elif instrument.get('margin') and market.is_open:
            market.margin_factor = 0.1 / float(instrument['margin'])
            margin_factor = str(market.margin_factor)
        else:
            # we don't want this when market is down because it could overwrite the previous stored value
            margin_factor = None

        if instrument['unit'] == 'AMOUNT':
            market.unit_type = Market.UNIT_AMOUNT
        elif instrument['unit'] == 'CONTRACTS':
            market.unit_type = Market.UNIT_CONTRACTS
        elif instrument['unit'] == 'SHARES':
            market.unit_type = Market.UNIT_SHARES

        # BINARY OPT_* BUNGEE_* 
        if instrument['type'] == 'CURRENCIES':
            market.market_type = Market.TYPE_CURRENCY
        elif instrument['type'] == 'INDICES':
            market.market_type = Market.TYPE_INDICE
        elif instrument['type'] == 'COMMODITIES':
            market.market_type = Market.TYPE_COMMODITY
        elif instrument['type'] == 'SHARES':
            market.market_type = Market.TYPE_STOCK
        elif instrument['type'] == 'RATES':
            market.market_type = Market.TYPE_RATE
        elif instrument['type'] == 'SECTORS':
            market.market_type = Market.TYPE_SECTOR

        market.contract_type = Market.CONTRACT_CFD
        market.trade = Market.TRADE_MARGIN

        market.set_size_limits(dealing_rules["minDealSize"]["value"], 0.0, dealing_rules["minDealSize"]["value"])
        market.set_notional_limits(0.0, 0.0, 0.0)
        market.set_price_limits(0.0, 0.0, 0.0)

        # commission for stocks
        commission = "0.0"
        # @todo

        # store the last market info to be used for backtesting
        if not self._read_only:
            Database.inst().store_market_info((self.name, epic, market.symbol,
                market.market_type, market.unit_type, market.contract_type,  # type
                market.trade, market.orders,  # type
                market.base, market.base_display, market.base_precision,  # base
                market.quote, market.quote_display, market.quote_precision,  # quote
                market.expiry, int(market.last_update_time * 1000.0),  # expiry, timestamp
                instrument['lotSize'], instrument['contractSize'], str(market.base_exchange_rate),
                instrument['valueOfOnePip'], instrument['onePipMeans'].split(' ')[0], margin_factor,
                dealing_rules["minDealSize"]["value"], "0.0", dealing_rules["minDealSize"]["value"],  # size limits
                "0.0", "0.0", "0.0",  # notional limits
                "0.0", "0.0", "0.0",  # price limits
                "0.0", "0.0", commission, commission)  # fees
            )

        return market

    def update_markets_info(self):
        """
        Update market info (very important because IG frequently changes lot or contract size).
        """
        for market_id in self._watched_instruments:
            market = self.fetch_market(market_id)

            if market.is_open:
                market_data = (market_id, market.is_open, market.last_update_time, market.bid, market.ofr,
                        market.base_exchange_rate, market.contract_size, market.value_per_pip,
                        market.vol24h_base, market.vol24h_quote)
            else:
                market_data = (market_id, market.is_open, market.last_update_time, 0.0, 0.0, None, None, None, None, None)

            self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)
