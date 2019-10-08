# @date 2018-08-25
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Trader/autotrader connector for ig.com

import time
import base64
import uuid
import copy

from datetime import datetime

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.trader import Trader

from .account import IGAccount

from trader.position import Position
from trader.order import Order
from trader.account import Account
from trader.market import Market

from connector.ig.rest import IGException
from database.database import Database

import logging
logger = logging.getLogger('siis.trader.ig')


class IGTrader(Trader):
    """
    IG market trader.

    @todo Improve wait between two similar order (avoid duplicate order need to wait 1sec)
    @todo Check that we have all our signals from WS and don't need forced sync during update
    """

    REST_OR_WS = False  # True if REST API sync else do with the state returned by WS events

    def __init__(self, service):
        super().__init__("ig.com", service)

        self._watcher = None
        self._account = IGAccount(self)

        self._last_position_update = 0
        self._last_order_update = 0
        self._last_market_update = 0

        self._previous_order = {}

    @property
    def authenticated(self):
        return self.connected and self._watcher.connector.authenticated

    @property
    def connected(self):
        return self._watcher is not None and self._watcher.connector is not None and self._watcher.connector.connected

    def connect(self):
        super().connect()

        # retrieve the ig.com watcher and take its connector
        self.lock()

        self._watcher = self.service.watcher_service.watcher(self._name)

        if self._watcher:
            self.service.watcher_service.add_listener(self)

        self.unlock()

        if self._watcher and self._watcher.connected:
            self.on_watcher_connected(self._watcher.name)

    def disconnect(self):
        super().disconnect()

        self.lock()

        if self._watcher:
            self.service.watcher_service.remove_listener(self)
            self._watcher = None

        self.unlock()

    def on_watcher_connected(self, watcher_name):
        super().on_watcher_connected(watcher_name)

        # markets, orders and positions
        logger.info("- Trader ig.com retrieving symbols and markets...")

        configured_symbols = self.configured_symbols()
        matching_symbols = self.matching_symbols_set(configured_symbols, self._watcher.watched_instruments())
      
        # fetch markets
        for symbol in matching_symbols:
            self.market(symbol, True)

        # markets, orders and positions
        self.lock()

        # initials orders and positions
        self.__fetch_orders()
        self.__fetch_positions()

        self.unlock()

        self.account.update(self._watcher.connector)

        logger.info("Trader ig.com got data. Running.")

    def on_watcher_disconnected(self, watcher_name):
        super().on_watcher_disconnected(watcher_name)

    def pre_update(self):
        super().pre_update()

        if self._watcher is None:
            self.connect()
        elif self._watcher.connector is None or not self._watcher.connector.connected:
            # wait for the watcher be connected
            retry = 0
            while self._watcher.connector is None or not self._watcher.connector.connected:
                retry += 1

                if retry >= int(5 / 0.01):
                    self._watcher.connect()

                    # and wait 0.5 second to be connected
                    time.sleep(0.5)

                # don't waste the CPU
                time.sleep(0.01)

    def update(self):
        if not super().update():
            return False

        if self._watcher is None or not self._watcher.connected:
            return True

        if IGTrader.REST_OR_WS:  # or True:
            # only if not using WS live API

            #
            # account data update (each minute)
            #

            try:
                self.lock()
                self._account.update(self._watcher.connector)
            except Exception as e:
                import traceback
                logger.error(traceback.format_exc())
            finally:
                self.unlock()

            #
            # positions
            #

            try:
                self.lock()
                # only once per 10 seconds to avoid API excess
                if time.time() - self._last_position_update >= 10.0:
                    self.__fetch_positions()
                    self._last_position_update = time.time()
            except Exception as e:
                import traceback
                logger.error(traceback.format_exc())
            finally:
                self.unlock()

            #
            # orders
            #

            try:
                self.lock()
                # only once per 10 seconds to avoid API excess
                if time.time() - self._last_order_update >= 10.0:
                    self.__fetch_orders()
                    self._last_order_update = time.time()
            except Exception as e:
                import traceback
                logger.error(traceback.format_exc())
            finally:
                self.unlock()

        return True

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop
        time.sleep(0.005)

    def set_ref_order_id(self, order):
        """
        Generate a new reference order id to be setup before calling create order, else a default one wil be generated.
        Generating it before is a prefered way to correctly manange order in strategy.
        @param order A valid or on to set the ref order id.
        @note If the given order already have a ref order id no change is made.
        @ref Pattern(regexp="[A-Za-z0-9_\\-]{1,30}")]
        """
        if order and not order.ref_order_id:
            order.set_ref_order_id("siis_" + base64.b64encode(uuid.uuid4().bytes).decode('utf8').rstrip('=\n').replace('+', '-').replace('/', '_'))
            # order.set_ref_order_id("siis_" + base64.b64encode(uuid.uuid5(uuid.NAMESPACE_DNS, 'siis.com').bytes).decode('utf8').rstrip('=\n'))
            return order.ref_order_id

        return None

    @Trader.mutexed
    def create_order(self, order):
        """
        Create a market or limit order using the REST API. Take care to does not make too many calls per minutes.
        """
        if not self.has_market(order.symbol):
            logger.error("Trader %s does not support market %s in order %s !" % (self.name, order.symbol, order.order_id))
            return False

        if not self._activity:
            return False

        level = None
        force_open = False  # can be used to hedge force_open = order.hedging

        if order.order_type == Order.ORDER_MARKET:
            order_type = 'MARKET'

            if order.hedging:
                force_open = True

        if order.order_type == Order.ORDER_LIMIT:
            order_type = 'LIMIT'
            level = order.price

            if order.hedging:
                force_open = True

        elif order.order_type == Order.ORDER_STOP:
            order_type = 'MARKET'

        else:
            order_type = 'MARKET'

        epic = order.symbol
        size = order.quantity

        direction = 'BUY' if order.direction == Position.LONG else 'SELL'

        # EPIC market detail fetched once next use cached
        market_info = self.market(epic)
        if market_info is None:
            return False

        quote_id = None
        deal_reference = order.ref_order_id

        if IGTrader.REST_OR_WS:
            try:
                # retrieve current epic position quantity only if not using WS API
                self.__fetch_positions()
            except:
                pass

        currency_code = market_info.quote
        expiry = market_info.expiry

        # take-profit
        limit_distance = None
        limit_level = None

        if order.take_profit:
            limit_level = order.take_profit
            force_open = True

        # stop-loss
        stop_distance = None
        stop_level = None
        guaranteed_stop = False

        if order.stop_loss:
            if self._account.guaranteed_stop:
                # @todo depends of the account setting and look at "dealingRules" to adjust to min stop level
                guaranteed_stop = True
                stop_level = order.stop_loss
                force_open = True
            else:
                stop_level = order.stop_loss
                force_open = True
   
        # trailing-stop
        trailing_stop = False
        trailing_stop_increment = None
        # @todo

        # time in force
        time_in_force = 'EXECUTE_AND_ELIMINATE'

        if order.time_in_force == Order.TIME_IN_FORCE_GTC:
            time_in_force = 'EXECUTE_AND_ELIMINATE'
        elif order.time_in_force == Order.TIME_IN_FORCE_IOC:
            time_in_force = 'IMMEDIATE_OR_CANCEL'  # @todo is that correct ?
        elif order.time_in_force == Order.TIME_IN_FORCE_FOK:
            time_in_force = 'FILL_OR_KILL'

        size = str(size)

        logger.info("Trader %s order %s %s EP@%s %s" % (self.name, order.direction_to_str(), epic, limit_level, size))

        # avoid DUPLICATE_ORDER_ERROR when sending two similar orders
        logger.info(self._previous_order)
        if epic in self._previous_order and (self._previous_order[epic] == (expiry, size, direction)):
            logger.debug("%s wait 1sec before passing a duplicate order..." % (self.name,))
            time.sleep(1.0)

        # @todo how to set the deal reference id ?
        try:
            results = self._watcher.connector.ig.create_open_position(currency_code, direction, epic, expiry,
                                                    force_open, guaranteed_stop, level,
                                                    limit_distance, limit_level, order_type,
                                                    quote_id, size, stop_distance, stop_level, time_in_force,
                                                    deal_reference)

            if results.get('dealStatus', '') == 'ACCEPTED':
                # logger.debug("create_order :" + repr(results))
                self._previous_order[epic] = (expiry, size, direction)

                # dealId is the IG given unique id, dealReference is the query dealId that have given its
                # order creation dealRef can be specified to have in return its ref (as signature for us)
                order.set_order_id(results['dealReference'])
                order.set_position_id(results['dealId'])

                # but it's in local account timezone, not createdDateUTC... but API v2 provides that (@todo look with header v=2 in place of v=1)
                order.created_time = datetime.strptime(results.get('createdDate', '1970/01/01 00:00:00:000'), "%Y/%m/%d %H:%M:%S:%f").timestamp()
                order.transact_time = datetime.strptime(results.get('createdDate', '1970/01/01 00:00:00:000'), "%Y/%m/%d %H:%M:%S:%f").timestamp()

                # executed price (no change in limit, but useful when market order)
                order.entry_price = results.get('level')

                # store it, but we will receive a creation signal too
                self._orders[order.order_id] = order

                # store the position directly because create_open_position fetch the position after acceptance or wait the WS signal
                # position = Position(self)
                # position.set_key(self.service.gen_key())

                # position.entry(direction, epic, size)
                # position.set_position_id(results['dealId'])
                # position.entry_price = results.get('level')
                # position.stop_loss = results.get('stopLevel') 
                # position.take_profit = results.get('limitLevel')

                # but it's in local account timezone, not createdDateUTC... but API v2 provides that (@todo look with header v=2 in place of v=1)
                # position.created_time = datetime.strptime(results.get('createdDate', '1970/01/01 00:00:00:000'), "%Y/%m/%d %H:%M:%S:%f").timestamp()

                # @todo 'trailingStep' 'trailingStopDistance' 'controlledRisk'

                # self._positions[position.position_id] = position
            else:
                reason = results
                logger.error("Trader %s rejected order %s of %s %s - cause : %s !" % (self.name, order.direction_to_str(), size, epic, reason))

                return False

        except IGException as e:
            logger.error("Trader %s except on order %s of %s %s - cause : %s !" % (self.name, order.direction_to_str(), size, epic, repr(e)))
            return False

        return True

    @Trader.mutexed
    def cancel_order(self, order_id):
        if not self._activity:
            return False

        order = self._orders.get(order_id)

        if order is None:
            return False

        deal_id = order.order_id

        try:
            results = self._watcher.connector.ig.delete_working_order(deal_id)
        except IGException as e:
            logger.error("%s except on order %s cancelation - cause : %s !" % (self.name, deal_id, repr(e)))
            return False

        return True

    @Trader.mutexed
    def close_position(self, position_id, market=True, limit_price=None):
        # @todo check why error, if we have "errorCode":"unable to aggregate close positions - no compatible position found" cancel the stop order
        if not self._activity:
            return False

        position = self._positions.get(position_id)

        if position is None or not position.is_opened():
            return False

        if not self.has_market(position.symbol):
            logger.error("%s does not support market %s on close position %s !" % (self.name, position.symbol, position.position_id))
            return False

        epic = position.symbol

        # EPIC market detail fetched once next use cached
        market_info = self.market(epic)
        if market_info is None:
            return False

        quote_id = None
        size = position.quantity
        expiry = market_info.expiry
        deal_id = None  # position.position_id

        if market:
            order_type = 'MARKET'
            level = None
        else:
            order_type = 'LIMIT'
            level = limit_price

        direction = 'SELL' if position.direction == Position.LONG else 'BUY'

        # avoid DUPLICATE_ORDER_ERROR when sending two similar orders
        logger.info(self._previous_order)
        if epic in self._previous_order and (self._previous_order[epic] == (expiry, size, direction)):
            logger.warning("%s wait 1sec before passing a duplicate order..." % (self.name,))
            time.sleep(1.0)

        try:
            results = self._watcher.connector.ig.close_open_position(deal_id, direction, epic, expiry, level, order_type, quote_id, size)
     
            if results.get('dealStatus', '') == 'ACCEPTED':
                self._previous_order[epic] = (expiry, size, direction)

                # set position closing until we get confirmation on a next update
                position.closing(limit_price)

                # del the position (done by streaming signal once fully-closed)
                # del self._positions[position.position_id]
            else:
                position.closing(limit_price)
                logger.error("%s rejected close position %s of %s %s !" % (self.name, direction, size, position.symbol))

                return False

        except IGException as e:
            logger.error("%s except close position %s of %s %s !" % (self.name, direction, size, position.symbol))
            return False

        return True

    @Trader.mutexed
    def modify_position(self, position_id, stop_loss_price=None, take_profit_price=None):
        if not self._activity:
            return False

        position = self._positions.get(position_id)

        if position is None or not position.is_opened():
            return False

        limit_level = None
        stop_level = None

        if take_profit_price:
            limit_level = take_profit_price

        if stop_loss_price:
            stop_level = stop_loss_price

        deal_id = position.position_id

        try:
            results = self._watcher.connector.ig.update_open_position(limit_level, stop_level, deal_id)

            if results.get('dealStatus', '') == 'ACCEPTED':
                position.take_profit = take_profit_price
                position.stop_loss = stop_loss_price

                return True
            else:
                logger.error("%s rejected modifiy position %s - %s - %s !" % (self.name, position.position_id, position.symbol))

            return True

        except IGException as e:
            logger.error("%s except close position %s of %s %s !" % (self.name, direction, size, position.symbol))
            return False

        return False

    def positions(self, market_id):
        """
        Returns current positions for an instrtument. If the trader does not use a WS API it is possible
        to constat a latency between the reality and what it returns. Prefers use WS API as possible.
        """
        positions = []

        self.lock()

        for k, position in self._positions.items():
            if position.symbol == market_id:
                positions.append(copy.copy(position))

        self.unlock()

        return positions

    def market(self, market_id, force=False):
        """
        Fetch from the watcher and cache it. It rarely changes so assume it once per connection.
        @param force Force to update the cache
        """
        market = self._markets.get(market_id)
        if (market is None or force) and self._watcher is not None and self._watcher.connected:
            try:
                market = self._watcher.fetch_market(market_id)
                self._markets[market_id] = market
            except Exception as e:
                logger.error("fetch_market: %s" % repr(e))
                return None

        return market

    #
    # protected
    #

    def __fetch_positions(self):
        """
        This is the synchronous REST fetching, but prefer the WS asynchronous and live one.
        Mainly used for initial fetching.
        """
        try:
            positions = self._watcher.connector.positions()
        except Exception as e:
            logger.error("fetch_market_by_epic: %s" % repr(e))
            raise

        # too this can be done by signals
        for pos_data in positions:
            pos = pos_data.get('position')
            market_data = pos_data.get('market')
            if not pos or not market_data:
                continue

            epic = market_data.get('epic', '')
            if not epic:
                continue

            #
            # update the market data first
            #

            deal_id = pos.get('dealId')

            market_update_time = datetime.strptime(market_data['updateTime'], '%H:%M:%S').timestamp() if market_data.get('updateTime') else None
            market_status = (market_data['marketStatus'] == 'TRADEABLE')
            self.on_update_market(epic, market_status, market_update_time, market_data['bid'], market_data['offer'], base_exchange_rate=None)
 
            market = self.market(epic)
            if market is None:
                continue

            #
            # related order
            #

            # retrieve the related order and remove that order or do it at order deleted signals...
            deal_ref = pos.get('dealReference')
            original_order = self._orders.get(deal_ref)

            if original_order:
                # @todo might be not necessary as a rejected order emit a signal but return rejection error at creation
                # and deal ref are not into the dict (only accepted order id)
                logger.debug("Todo original order retrieved")
                del self._orders[deal_ref]

            #
            # create or update the local position
            #

            direction = Position.LONG if pos.get('direction') == 'BUY' else Position.SHORT
            quantity = pos.get('dealSize', 0.0)

            position = self._positions.get(deal_id)
            if position is None:
                position = Position(self)

                position.set_position_id(deal_id)
                position.set_key(self.service.gen_key())
                position.leverage = 1.0 / market.margin_factor

                position.entry(direction, epic, quantity)

                # position are merged by epic but might be independents
                self._positions[deal_id] = position

            # account local tz, but createdDateUTC exists in API v2 (look at HTTP header v=2)
            position.created_time = datetime.strptime(pos.get('createdDate', '1970/01/01 00:00:00:000'), "%Y/%m/%d %H:%M:%S:%f").timestamp()

            position.entry_price = pos.get('openLevel', 0.0)
            position.stop_loss = pos.get('stopLevel', 0.0)
            position.take_profit = pos.get('limitLevel', 0.0)

            # garanteed stop
            if pos.get('controlledRisk', False):
                pass  # @todo

            # @todo stop type (garantee, market, trailing)
            position.trailing_stop = pos.get('trailingStep', 0.0)
            position.trailing_stop_dst = pos.get('trailingStopDistance', 0.0)

            if market:
                position.update_profit_loss(market)

        # remove empty positions, but this can be too done by DELETED signal
        rm_list = []

        for k, position in self._positions.items():
            found = False

            for pos_data in positions:
                pos = pos_data.get('position')

                if position.position_id == pos.get('dealId'):
                    found = True
                    break

            if not found:
                rm_list.append(k)

        for rm_pos in rm_list:
            del self._positions[rm_pos]

    def __fetch_orders(self):
        """
        This is the synchronous REST fetching, but prefer the WS asynchronous and live one.
        Mainly used for initial fetching.
        """
        try:
            orders = self._watcher.connector.orders()
        except Exception as e:
            logger.error("__fetch_orders: %s" % repr(e))
            raise

        # @todo add/update/remove orders
        # and this can be done by signals

    @Trader.mutexed
    def on_update_market(self, market_id, tradable, last_update_time, bid, ofr,
            base_exchange_rate, contract_size=None, value_per_pip=None,
            vol24h_base=None, vol24h_quote=None):

        super().on_update_market(market_id, tradable, last_update_time, bid, ofr, base_exchange_rate, contract_size, value_per_pip, vol24h_base, vol24h_quote)

        # update positions profit/loss for the related market id
        market = self.market(market_id)

        # market must be valid and currently tradeable
        if market:
            for k, position in self._positions.items():
                if position.symbol == market.market_id:
                    position.update_profit_loss(market)
