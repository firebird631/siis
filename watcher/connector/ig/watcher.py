# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# ig.com watcher implementation

import copy
import math
import urllib
import json
import time
import os.path
import traceback

from datetime import datetime

from watcher.watcher import Watcher
from common.signal import Signal

from connector.ig.connector import IGConnector
from connector.ig.lightstreamer import LSClient, Subscription

from instrument.instrument import Instrument, Candle
from database.database import Database

from trader.order import Order
from trader.market import Market

from common.utils import decimal_place, UTC

import logging
logger = logging.getLogger('siis.watcher.ig')
exec_logger = logging.getLogger('siis.exec.watcher.ig')
error_logger = logging.getLogger('siis.error.watcher.ig')
traceback_logger = logging.getLogger('siis.traceback.watcher.ig')


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
        - Only for forex, indices, commodities, but no history for stocks !

    @todo get vol24 in base and quote unit
    @todo base_exchange_rate must be updated as price changes
    """

    MAX_CONCURRENT_SUBSCRIPTIONS = 40

    def __init__(self, service):
        super().__init__("ig.com", service, Watcher.WATCHER_PRICE_AND_VOLUME)

        self._host = "ig.com"
        self._connector = None
        self._lightstreamer = None
        self._subscriptions = []
        self._account_id = ""

        self._subscribed_markets = {}
        self._subscribed_ticks = {}

        self.__configured_symbols = set()  # cache for configured symbols set
        self.__matching_symbols = set()    # cache for matching symbols

        self._cached_tick = {}    # caches for when a value is not defined
        self._store_trade = True  # default store trade because we can't get history else

    def connect(self):
        super().connect()

        try:
            self.lock()
            self._ready = False
            self._connecting = True

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
                # logger.debug(self._connector.cst, self._connector.xst, self._connector.lightstreamer_endpoint, identity.get('account-id'), self._connector.client_id)

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

                configured_instruments = self.configured_symbols()

                # @todo could check with API if configured epic exists and put them into this list
                instruments = copy.copy(configured_instruments)

                self._available_instruments = copy.copy(instruments)

                configured_symbols = self.configured_symbols()
                matching_symbols = self.matching_symbols_set(configured_symbols, instruments)

                # cache them
                self.__configured_symbols = configured_symbols
                self.__matching_symbols = matching_symbols

            self._ready = True
            self._connecting = False

        except Exception as e:
            logger.debug(repr(e))
            error_logger.error(traceback.format_exc())

            self._connector = None
            self._lightstreamer = None
        finally:
            self.unlock()

        if self._connector and self._connector.connected and self._ready:
            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, time.time())

    @property
    def connector(self):
        return self._connector

    @property
    def connected(self):
        return self._ready and self._connector is not None and self._connector.connected

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
                # self._lightstreamer._join()
                self._lightstreamer = None

            if self._connector:
                self._connector.disconnect()
                self._connector = None

                # reset subscribed markets WS
                self._subscribed_markets = {}
                self._subscribed_ticks = {}

            self._ready = False

        except Exception as e:
            logger.error(repr(e))
            error_logger.error(traceback.format_exc())
        finally:
            self.unlock()

    def pre_update(self):
        super().pre_update()

        if not self._connecting and not self._ready:
            self.lock()
            if self._connector is None or not self._connector.connected or self._lightstreamer is None or not self._lightstreamer.connected:
                self._connector = None
                self.unlock()

                self.connect()

                if not self.connected:
                    # retry in 2 second
                    time.sleep(2.0)

                return
            else:
                self.unlock()

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
            try:
                self.update_markets_info()
                self._last_market_update = time.time()
            except Exception as e:
                # session must at least be obtained each 6h, we call each 4h at least but if we have a server invalidation
                # @todo and is the WS still valid ?
                self._connector.update_session()

        return True

    def post_update(self):
        super().post_update()
        time.sleep(0.0005)

    def post_run(self):
        super().post_run()

    #
    # instruments
    #

    def subscribe(self, market_id, timeframe):
        self.lock()
        logger.info(market_id)

        if market_id in self.__matching_symbols:
            # fetch from 1m to 1w, we have a problem of the 10k candle limit per weekend, then we only
            # prefetch for the last of each except for 1m and 5m we assume we have a delay of 5 minutes
            # from the manual prefetch script execution and assuming the higher timeframe are already up-to-date.
            if self._initial_fetch:
                logger.info("%s prefetch for %s" % (self.name, market_id))

                self.fetch_and_generate(market_id, Instrument.TF_1M, 5, None)
                self.fetch_and_generate(market_id, Instrument.TF_3M, 2, None)
                self.fetch_and_generate(market_id, Instrument.TF_5M, 1, None)
                self.fetch_and_generate(market_id, Instrument.TF_15M, 1, None)
                self.fetch_and_generate(market_id, Instrument.TF_1H, 1, None)
                self.fetch_and_generate(market_id, Instrument.TF_4H, 1, None)
                self.fetch_and_generate(market_id, Instrument.TF_1D, 1, None)
                self.fetch_and_generate(market_id, Instrument.TF_1W, 1, None)              

            self.insert_watched_instrument(market_id, [0])

            # to know when market close but could be an hourly REST API call, but it consume one subscriber...
            # @todo so maybe prefers REST call hourly ? but need bid/ofr properly defined at signals on trader.market and strategy.instrument !
            self.subscribe_market(market_id)

            # tick data
            self.subscribe_tick(market_id)

            self.unlock()

            if self._initial_fetch:
                logger.info("Watcher %s wait 8+1 seconds to limit to a fair API usage" % (self.name,))
                time.sleep(9.0)  # 1 sec per query + 1 extra second

            return True
        else:
            self.unlock()
            return False

    def unsubscribe(self, market_id, timeframe):
        self.lock()

        if market_id in self._subscribed_markets:
            sub = self._subscribed_markets[market_id]
            self.unsubscribe_ws(sub)
            del self._subscribed_markets[market_id]

            sub = self._subscribed_ticks[market_id]
            self.unsubscribe_ws(sub)
            del self._subscribed_ticks[market_id]

            self.unlock()
            return True
        else:
            self.unlock()
            return False

    #
    # WS subscribtion
    #

    def subscribe_account(self, account_id):
        fields = ["PNL", "AVAILABLE_TO_DEAL", "MARGIN", "FUNDS", "AVAILABLE_CASH"]

        subscription = Subscription(
                mode="MERGE",
                items=["ACCOUNT:"+account_id],
                fields=fields,
                adapter="")

        self.subscribe_ws(subscription)
        subscription.addlistener(self, IGWatcher.on_account_update)

    def subscribe_trades(self, account_id):
        fields = ["CONFIRMS", "OPU", "WOU"]

        subscription = Subscription(
                mode="DISTINCT",
                items=["TRADE:"+account_id],
                fields=fields,
                adapter="")

        self.subscribe_ws(subscription)
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

        sub_key = self.subscribe_ws(subscription)
        subscription.addlistener(self, IGWatcher.on_tick_update)

        self._subscribed_ticks[instrument] = sub_key

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

    #     self.subscribe_ws(subscription)
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

        sub_key = self.subscribe_ws(subscription)
        subscription.addlistener(self, IGWatcher.on_market_update)

        self._subscribed_markets[instrument] = sub_key

    def subscribe_ws(self, subscription):
        """
        Registering the Subscription
        """
        sub_key = self._lightstreamer.subscribe(subscription)
        self._subscriptions.append(sub_key)

        return sub_key

    def unsubscribe_ws(self, sub_key):
        if sub_key in self._subscriptions:
            self._lightstreamer.unsubscribe(sub_key)
            del self._subscriptions[sub_key]

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
            logger.debug(repr(e))
            error_logger.error(traceback.format_exc())

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
                    # @todo take now and replace H:M:S
                    update_time = time.time()  #  datetime.strptime(values['UPDATE_TIME'], '%H:%M:%S').timestamp()
                    market_data = (name[1], True, update_time, float(values["BID"]), float(values["OFFER"]), None, None, None, None, None)
                else:
                    update_time = 0
                    market_data = (name[1], False, 0, None, None, None, None, None, None, None)

                self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)
        except Exception as e:
            logger.debug(repr(e))
            error_logger.error(traceback.format_exc())

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
                if not self._read_only and self._store_trade:
                    Database.inst().store_market_trade((self.name, market_id, int(utm), bid, ofr, ltv or 0))

        except Exception as e:
            logger.debug(repr(e))
            error_logger.error(traceback.format_exc())

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
    #         logger.debug(repr(e))
    #         error_logger.error(traceback.format_exc())

    @staticmethod
    def on_trade_update(self, item_update):
        name = item_update.get('name', '').split(':')

        try:
            if len(name) == 2 and name[0] == 'TRADE' and name[1] == self._account_id:
                # live trade updates
                values = item_update['values']

                #
                # active waiting order (open/updated/deleted)
                #

                if values.get('WOU'):
                    data = json.loads(values.get('WOU'))
                    exec_logger.info("ig.com WOU %s" % str(data))

                    order_id = data['dealId']
                    ref_order_id = data['dealReference']

                    epic = data['epic']

                    # date of the event 2018-09-13T20:36:01.096 without Z
                    event_time = datetime.strptime(data['timestamp'], '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=UTC()).timestamp()

                    if data.get('direction', '') == 'BUY':
                        direction = Order.LONG
                    elif data.get('direction', '') == 'SELL':
                        direction = Order.SHORT
                    else:
                        direction = 0

                    if data.get('dealStatus', "") == 'REJECTED':
                        pass
                    elif data.get('dealStatus', "") == 'ACCEPTED':
                        quantity = float(data.get('size')) if data.get('size') is not None else 0.0
                        level = float(data['level']) if data.get('level') is not None else None
                        stop_distance = float(data['stopDistance']) if data.get('stopDistance') is not None else None
                        limit_distance = float(data['limitDistance']) if data.get('limitDistance') is not None else None
                        guaranteed_stop = data.get('guaranteedStop', False)
                        currency = data.get('currency', "")

                        if data.get('orderType'):
                            if data['orderType'] == "LIMIT":
                                order_type = Order.ORDER_LIMIT
                            elif data['orderType'] == "STOP":
                                order_type = Order.ORDER_STOP
                            else:
                                order_type = Order.ORDER_MARKET
                        else:
                            order_type = Order.ORDER_MARKET

                        if data.get('timeInForce'):
                            if data['timeInForce'] == "GOOD_TILL_CANCELLED":
                                time_in_force = Order.TIME_IN_FORCE_GTC
                            elif data['timeInForce'] == "GOOD_TILL_DATE":
                                time_in_force = Order.TIME_IN_FORCE_GTD
                                # data['goodTillDate']   @todo till date
                        else:
                            time_in_force = Order.TIME_IN_FORCE_GTC

                        status = data.get('status', "")

                        if status == "OPEN":
                            order_data = {
                                'id': order_id,
                                'type': order_type,
                                'time-in-force': time_in_force,
                                'price': level if order_type == Order.ORDER_LIMIT else None,
                                'stop-price': level if order_type == Order.ORDER_STOP else None,
                                'stop-loss': stop_distance,
                                'take-profit': limit_distance
                            }

                            self.service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (epic, order_data, ref_order_id))

                        elif status == "UPDATED":
                            # signal of updated order
                            order_data = {
                                'id': order_id,
                                'type': order_type,
                                'time-in-force': time_in_force,
                                'price': level if order_type == Order.ORDER_LIMIT else None,
                                'stop-price': level if order_type == Order.ORDER_STOP else None,
                                'stop-loss': stop_distance,
                                'take-profit': limit_distance
                            }

                            self.service.notify(Signal.SIGNAL_ORDER_UPDATED, self.name, (epic, order_data, ref_order_id))

                        elif status == "DELETED":
                            # signal of deleted order
                            self.service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (epic, order_id, ref_order_id))

                #
                # order confirms (accepted/rejected)
                #

                if values.get('CONFIRMS'):
                    data = json.loads(values.get('CONFIRMS'))
                    exec_logger.info("ig.com CONFIRMS %s" % str(data))

                    epic = data.get('epic')

                    if data.get('dealStatus', "") == "REJECTED":
                        ref_order_id = data['dealReference']

                        self.service.notify(Signal.SIGNAL_ORDER_REJECTED, self.name, (epic, ref_order_id))

                    elif data.get('dealStatus', "") == "ACCEPTED":
                        # deal confirmed and accepted
                        order_id = data['dealId']
                        ref_order_id = data['dealReference']

                        # date 2018-09-13T20:36:01.096 without Z
                        event_time = datetime.strptime(data['date'], '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=UTC()).timestamp()

                        # direction of the trade
                        if data['direction'] == 'BUY':
                            direction = Order.LONG
                        elif data['direction'] == 'SELL':
                            direction = Order.SHORT
                        else:
                            direction = 0

                        level = float(data['level']) if data.get('level') is not None else None   # exec price
                        quantity = float(data['size']) if data.get('size') is not None else 0.0
                        stop_level = float(data['stopLevel']) if data.get('stopLevel') is not None else 0.0
                        limit_level = float(data['limitLevel']) if data.get('limitLevel') is not None else 0.0
                        profit_loss = float(data['profit']) if data.get('profit') is not None else 0.0
                        profit_currency = data.get('profitCurrency', "")

                        # 'expiry', 'guaranteedStop'

                        # affected positions, normaly should not be necessary except if user create a manual trade that could reduce an existing position
                        # for affected_deal in data.get('affectedDeals', []):
                        #     position_id = affected_deal['dealId']
                        #     status = affected_deal.get('status', "")
                        #     if status == "AMENDED":
                        #         pass
                        #     elif status == "DELETED":
                        #         pass
                        #     elif status == "FULLY_CLOSED":
                        #         pass
                        #     elif status == "OPENED":
                        #         pass
                        #     elif status == "PARTIALLY_CLOSED":
                        #         pass

                        status = data.get('status', "")

                        if status == "AMENDED":
                            # traded and initial
                            order = {
                                'id': order_id,
                                'symbol': epic,
                                'timestamp': event_time,
                                'direction': direction,
                                'quantity': None,  # no have
                                'filled': None,  # no have
                                'cumulative-filled': quantity,
                                'exec-price': level,
                                'avg-price': None,
                                'stop-loss': stop_level,
                                'take-profit': limit_level,
                                'profit-loss': profit_loss,
                                'profit-currency': profit_currency,
                                'info': 'amended'
                            }

                            self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (epic, order, ref_order_id))

                        elif status == "CLOSED":
                            # traded and completed
                            order = {
                                'id': order_id,
                                'symbol': epic,
                                'timestamp': event_time,
                                'direction': direction,
                                'quantity': None,
                                'filled': None,
                                'cumulative-filled': quantity,
                                'exec-price': level,
                                'avg-price': None,
                                'profit-loss': profit_loss,
                                'profit-currency': profit_currency,
                                'info': 'closed'
                            }

                            if data.get('limitLevel') and data.get('stopLevel'):
                                order['type'] = Order.ORDER_STOP_LIMIT
                            elif data.get('limitLevel'):
                                order['type'] = Order.ORDER_LIMIT
                            elif data.get('stopLevel'):
                                order['type'] = Order.ORDER_STOP
                            else:
                                order['type'] = Order.ORDER_MARKET

                            self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (epic, order, ref_order_id))
                            self.service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (epic, order_id, ""))

                        elif status == "DELETED":
                            # deleted why for, we never receive them
                            self.service.notify(Signal.SIGNAL_ORDER_DELETED, self.name, (epic, order_id, ""))

                        elif status == "OPEN":
                            # traded and initial
                            order = {
                                'id': order_id,
                                'symbol': epic,
                                'timestamp': event_time,
                                'direction': direction,
                                'quantity': None,  # no have
                                'filled': None,  # no have
                                'cumulative-filled': quantity,
                                'exec-price': level,
                                'avg-price': None,
                                'stop-loss': stop_level,
                                'take-profit': limit_level,
                                'profit-loss': profit_loss,
                                'profit-currency': profit_currency,
                                'info': 'open'
                            }

                            if data.get('limitLevel') and data.get('stopLevel'):
                                order['type'] = Order.ORDER_STOP_LIMIT
                                order['price'] = float(data.get('limitLevel'))
                                order['stop-price'] = float(data.get('stopLevel'))
                            elif data.get('limitLevel'):
                                order['type'] = Order.ORDER_LIMIT
                                order['price'] = float(data.get('limitLevel'))
                            elif data.get('stopLevel'):
                                order['type'] = Order.ORDER_STOP
                                order['stop-price'] = float(data.get('stopLevel'))
                            else:
                                order['type'] = Order.ORDER_MARKET

                            # @todo 'limitDistance' 'stopDistance' 'trailingStop'

                            self.service.notify(Signal.SIGNAL_ORDER_OPENED, self.name, (epic, order, ref_order_id))

                            if quantity > 0.0:
                                self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (epic, order, ref_order_id))

                        elif status == "PARTIALLY_CLOSED":
                            # traded and partially completed
                            order = {
                                'id': order_id,
                                'symbol': epic,
                                'timestamp': event_time,
                                'direction': direction,
                                'quantity': None,  # no have
                                'filled': None,  # no have
                                'cumulative-filled': quantity,
                                'exec-price': level,
                                'avg-price': None,
                                'profit-loss': profit_loss,
                                'profit-currency': profit_currency,
                                'info': 'partially-closed'
                            }

                            self.service.notify(Signal.SIGNAL_ORDER_TRADED, self.name, (epic, order, ref_order_id))

                #
                # active position (open/updated/deleted)
                #

                if values.get('OPU'):
                    data = json.loads(values.get('OPU'))
                    exec_logger.info("ig.com OPU %s" % str(data))

                    position_id = data['dealId']
                    ref_order_id = data['dealReference']

                    epic = data.get('epic')
                    # "channel": "WTP", "expiry": "-"

                    # date of the event 2018-09-13T20:36:01.096 without Z
                    event_time = datetime.strptime(data['timestamp'], '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=UTC()).timestamp()

                    if data.get('direction', '') == 'BUY':
                        direction = Order.LONG
                    elif data.get('direction', '') == 'SELL':
                        direction = Order.SHORT
                    else:
                        direction = Order.LONG

                    if data.get('dealStatus', "") == "REJECTED":
                        pass

                    elif data.get('dealStatus', "") == "ACCEPTED":
                        quantity = float(data.get('size')) if data.get('size') is not None else 0.0
                        level = float(data['level']) if data.get('level') is not None else None
                        stop_level = float(data['stopLevel']) if data.get('stopLevel') is not None else None
                        limit_level = float(data['limitLevel']) if data.get('limitLevel') is not None else None
                        profit_loss = float(data['profit']) if data.get('profit') is not None else 0.0
                        profit_currency = data.get('profitCurrency', "")
                        # @todo trailingStep, trailingStopDistance, guaranteedStop

                        status = data.get('status', "")

                        if status == "OPEN":
                            # signal of opened position
                            position_data = {
                                'id': position_id,
                                'symbol': epic,
                                'direction': direction,
                                'timestamp': event_time,
                                'quantity': quantity,
                                'exec-price': level,
                                'avg-price': level,
                                'avg-entry-price': level,  # entry
                                'stop-loss': stop_level,
                                'take-profit': limit_level,
                                'profit-loss': profit_loss,
                                'profit-currency': profit_currency,
                                'cumulative-filled': None,
                                'filled': None,
                                'liquidation-price': None
                            }

                            self.service.notify(Signal.SIGNAL_POSITION_OPENED, self.name, (epic, position_data, ref_order_id))

                        elif status == "UPDATED":
                            # signal of updated position
                            position_data = {
                                'id': position_id,
                                'symbol': epic,
                                'direction': direction,
                                'timestamp': event_time,
                                'quantity': quantity,
                                'exec-price': level,
                                'avg-entry-price': level,  # entry
                                'avg-price': level,
                                'stop-loss': stop_level,
                                'take-profit': limit_level,
                                'profit-loss': profit_loss,
                                'profit-currency': profit_currency,
                                'cumulative-filled': None,
                                'filled': None,
                                'liquidation-price': None
                            }

                            self.service.notify(Signal.SIGNAL_POSITION_UPDATED, self.name, (epic, position_data, ref_order_id))

                        elif status == "DELETED":
                            # signal of deleted position
                            position_data = {
                                'id': position_id,
                                'symbol': epic,
                                'direction': direction,
                                'timestamp': event_time,
                                'quantity': quantity,
                                'exec-price': level,
                                'avg-price': level,
                                'avg-exit-price': level,  # exit
                                'stop-loss': stop_level,
                                'take-profit': limit_level,
                                'profit-loss': profit_loss,
                                'profit-currency': profit_currency,
                                'cumulative-filled': None,
                                'filled': None,
                                'liquidation-price': None
                            }
                            self.service.notify(Signal.SIGNAL_POSITION_DELETED, self.name, (epic, position_data, ref_order_id))

        except Exception as e:
            logger.debug(repr(e))
            exec_logger.error(traceback.format_exc())

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

        market.one_pip_means = float(instrument['onePipMeans'].split(' ')[0])  # "1 Index Point", "0.0001 USD/EUR"
        market.value_per_pip = float(instrument['valueOfOnePip'])
        market.contract_size = float(instrument['contractSize'])
        market.lot_size = float(instrument['lotSize'])

        market.set_base(
            base_symbol,
            base_symbol,
            decimal_place(market.one_pip_means))

        if instrument['type'] in ('CURRENCIES'):
            pass  # quote_precision = 
        elif instrument['type'] in ('INDICES', 'COMMODITIES', 'SHARES', 'RATES', 'SECTORS'):
            pass  # quote_precision = 

        market.set_quote(
            instrument["currencies"][0]["name"],
            instrument["currencies"][0]['symbol'],
            decimal_place(market.one_pip_means))

        # "forceOpenAllowed": true,
        # "stopsLimitsAllowed": true,
        # "controlledRiskAllowed": true,
        # "streamingPricesAvailable": true,

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

        market.trade = Market.TRADE_MARGIN | Market.TRADE_POSITION
        market.contract_type = Market.CONTRACT_CFD

        # take minDealSize as tick size
        market.set_size_limits(dealing_rules["minDealSize"]["value"], 0.0, dealing_rules["minDealSize"]["value"])
        # @todo there is some limits in contract size
        market.set_notional_limits(0.0, 0.0, 0.0)
        # use one pip means for minimum and tick price size
        market.set_price_limits(market.one_pip_means, 0.0, market.one_pip_means)

        # commission for stocks @todo
        commission = "0.0"

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

        # print(market.symbol, market._size_limits, market._price_limits)

        # notify for strategy
        self.service.notify(Signal.SIGNAL_MARKET_INFO_DATA, self.name, (epic, market))

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
                market_data = (market_id, market.is_open, market.last_update_time, None, None, None, None, None, None, None)

            self.service.notify(Signal.SIGNAL_MARKET_DATA, self.name, market_data)

    def fetch_candles(self, market_id, timeframe, from_date=None, to_date=None, n_last=None):
        try:
            if n_last:
                data = self._connector.history_last_n(market_id, timeframe, n_last)
            else:
                data = self._connector.history_range(market_id, timeframe, from_date, to_date)
        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

            data = {}

        prices = data.get('prices', [])

        for price in prices:
            timestamp = datetime.strptime(price['snapshotTime'], '%Y:%m:%d-%H:%M:%S').timestamp()

            if price.get('highPrice')['bid'] is None and price.get('highPrice')['ask'] is None:
                # ignore empty candles
                continue

            # yield (timestamp, high bid, low, open, close, high ofr, low, open, close, volume)
            yield([int(timestamp * 1000),
                str(price.get('highPrice')['bid'] or price.get('highPrice')['ask']),
                str(price.get('lowPrice')['bid'] or price.get('lowPrice')['ask']),
                str(price.get('openPrice')['bid'] or price.get('openPrice')['ask']),
                str(price.get('closePrice')['bid'] or price.get('closePrice')['ask']),
                str(price.get('highPrice')['ask'] or price.get('highPrice')['bid']),
                str(price.get('lowPrice')['ask'] or price.get('lowPrice')['bid']),
                str(price.get('openPrice')['ask'] or price.get('openPrice')['bid']),
                str(price.get('closePrice')['ask'] or price.get('closePrice')['bid']),
                price.get('lastTradedVolume', '0')])
