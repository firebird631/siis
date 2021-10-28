# @date 2018-08-25
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Trader/autotrader connector for ig.com

import traceback
import time
import base64
import uuid
import copy

from datetime import datetime

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
error_logger = logging.getLogger('siis.error.trader.ig')
order_logger = logging.getLogger('siis.order.trader.ig')
traceback_logger = logging.getLogger('siis.traceback.trader.ig')


class IGTrader(Trader):
    """
    IG market trader.
    """

    REST_OR_WS = False  # True if REST API sync else do with the state returned by WS events

    def __init__(self, service):
        super().__init__("ig.com", service)

        self._watcher = None
        self._account = IGAccount(self)

        self._last_position_update = 0
        self._last_order_update = 0
        self._last_market_update = 0

    @property
    def authenticated(self):
        return self.connected and self._watcher.connector.authenticated

    @property
    def connected(self):
        return self._watcher is not None and self._watcher.connector is not None and self._watcher.connector.connected

    def connect(self):
        super().connect()

        # retrieve the ig.com watcher and take its connector
        with self._mutex:
            self._watcher = self.service.watcher_service.watcher(self._name)

            if self._watcher:
                self.service.watcher_service.add_listener(self)

        if self._watcher and self._watcher.connected:
            self.on_watcher_connected(self._watcher.name)

    def disconnect(self):
        super().disconnect()

        with self._mutex:
            if self._watcher:
                self.service.watcher_service.remove_listener(self)
                self._watcher = None

    def on_watcher_connected(self, watcher_name):
        super().on_watcher_connected(watcher_name)

        logger.info("- Trader ig.com retrieving data...")

        with self._mutex:
            # initials orders and positions
            try:
                self.__fetch_orders()
            except:
                pass

            try:
                self.__fetch_positions()
            except:
                pass

            self.account.update(self._watcher.connector)

        logger.info("Trader ig.com got data. Running.")

    def on_watcher_disconnected(self, watcher_name):
        super().on_watcher_disconnected(watcher_name)

    def pre_update(self):
        super().pre_update()

        if self._watcher is None:
            self.connect()

        # elif self._watcher.connector is None or not self._watcher.connector.connected:
        #     # wait for the watcher be connected
        #     retry = 0
        #     while self._watcher.connector is None or not self._watcher.connector.connected:
        #         retry += 1

        #         if retry >= int(5 / 0.01):
        #             self._watcher.connect()

        #             # and wait 0.5 second to be connected
        #             time.sleep(0.5)

        #         # don't waste the CPU
        #         time.sleep(0.01)

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

            with self._mutex:
                try:
                    self._account.update(self._watcher.connector)
                except Exception as e:
                    error_logger.error(repr(e))
                    traceback_logger.error(traceback.format_exc())

            #
            # positions
            #

            with self._mutex:
                try:
                    # only once per 10 seconds to avoid API excess
                    if time.time() - self._last_position_update >= 10.0:
                        self.__fetch_positions()
                        self._last_position_update = time.time()
                except Exception as e:
                    error_logger.error(repr(e))
                    traceback_logger.error(traceback.format_exc())

            #
            # orders
            #

            with self._mutex:
                try:
                    # only once per 10 seconds to avoid API excess
                    if time.time() - self._last_order_update >= 10.0:
                        self.__fetch_orders()
                        self._last_order_update = time.time()
                except Exception as e:
                    error_logger.error(repr(e))
                    traceback_logger.error(traceback.format_exc())

        return True

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop
        time.sleep(0.005)

    #
    # ordering
    #

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

    def create_order(self, order, market_or_instrument):
        """
        Create a market or limit order using the REST API. Take care to does not make too many calls per minutes.
        """
        if not order or not market_or_instrument:
            return Order.REASON_INVALID_ARGS

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse order because of missing connector" % (self.name,))
            return Order.REASON_ERROR

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

        quote_id = None
        deal_reference = order.ref_order_id

        currency_code = market_or_instrument.quote
        expiry = market_or_instrument.expiry

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

        logger.info("Trader %s order %s %s @%s %s" % (self.name, order.direction_to_str(), epic, limit_level, size))

        try:
            results = self._watcher.connector.ig.create_open_position(
                currency_code, direction, epic, expiry,
                force_open, guaranteed_stop, level,
                limit_distance, limit_level, order_type,
                quote_id, size, stop_distance, stop_level, time_in_force,
                deal_reference)

            order_logger.info(results)

            if results.get('dealStatus', '') == 'ACCEPTED':
                # dealId is the IG given unique id, dealReference is the query dealId that have given its
                # order creation dealRef can be specified to have in return its ref (as signature for us)
                order.set_order_id(results['dealReference'])
                order.set_position_id(results['dealId'])

                # but it's in local account timezone, not createdDateUTC...
                # but API v2 provides that
                # @todo look with header v=2 in place of v=1
                order.created_time = datetime.strptime(results.get('createdDate', '1970/01/01 00:00:00:000'),
                                                       "%Y/%m/%d %H:%M:%S:%f").timestamp()
                order.transact_time = datetime.strptime(results.get('createdDate', '1970/01/01 00:00:00:000'),
                                                        "%Y/%m/%d %H:%M:%S:%f").timestamp()

                if not order.created_time:
                    order.created_time = self.timestamp
                if not order.transact_time:
                    order.created_time = self.timestamp

                # executed price (no change in limit, but useful when market order)
                order.entry_price = results.get('level')
            else:
                error_logger.error("Trader %s rejected order %s of %s %s - cause : %s !" % (
                    self.name, order.direction_to_str(), size, epic, results.get('reason')))

                # @todo reason to error
                return Order.REASON_ERROR

        except IGException as e:
            error_logger.error("Trader %s except on order %s of %s %s - cause : %s !" % (
                self.name, order.direction_to_str(), size, epic, repr(e)))

            # @todo reason to error
            return Order.REASON_ERROR

        return Order.REASON_OK

    def cancel_order(self, order_id, market_or_instrument):
        if not order_id or not market_or_instrument:
            return Order.REASON_INVALID_ARGS

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse to cancel order because of missing connector" % (self.name,))
            return Order.REASON_ERROR

        try:
            results = self._watcher.connector.ig.delete_working_order(order_id)
            order_logger.info(results)

            if results.get('dealReference', '') != 'ACCEPTED':
                error_logger.error("%s rejected cancel order %s - %s !" % (self.name, order_id,
                                                                           market_or_instrument.market_id))

                # @todo reason to error
                return Order.REASON_ERROR

        except IGException as e:
            error_logger.error("%s except on order %s cancellation - cause : %s !" % (self.name, order_id, str(e)))

            # @todo reason to error
            return Order.REASON_ERROR

        return Order.REASON_OK

    def close_position(self, position_id, market_or_instrument, direction, quantity, market=True, limit_price=None):
        """
        Close an existing position by its position identifier.
        @param position_id str Unique position identifier (dealId)
        @param market_or_instrument boolean True if close at market (no limit price)
        @param direction
        @param quantity
        @param market
        @param limit_price
        """
        if not position_id or not market_or_instrument:
            return False

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse to close position because of missing connector" % (self.name,))
            return False

        epic = market_or_instrument.market_id
        expiry = market_or_instrument.expiry
        deal_id = position_id
        quote_id = None
        size = quantity

        if deal_id:
            # dealId then no epic neither expiry
            epic = None
            expiry = None

        if market:
            order_type = 'MARKET'
            level = None
        else:
            order_type = 'LIMIT'
            level = limit_price

        direction = 'SELL' if direction == Position.LONG else 'BUY'

        try:
            results = self._watcher.connector.ig.close_open_position(deal_id, direction, epic, expiry, level, order_type, quote_id, size)
            order_logger.info(results)
     
            if results.get('dealStatus', '') != 'ACCEPTED':
                error_logger.error("%s rejected close position %s - %s !" % (self.name, position_id, market_or_instrument.market_id))
                return False

        except IGException as e:
            error_logger.error("%s except close position %s - %s - cause : %s !" % (self.name, position_id, market_or_instrument.market_id, str(e)))
            return False

        return True

    def modify_position(self, position_id, market_or_instrument, stop_loss_price=None, take_profit_price=None):
        if not position_id or not market_or_instrument:
            return False

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse to modify position because of missing connector" % (self.name,))
            return False

        limit_level = None
        stop_level = None

        if take_profit_price:
            limit_level = take_profit_price
        if stop_loss_price:
            stop_level = stop_loss_price

        try:
            results = self._watcher.connector.ig.update_open_position(limit_level, stop_level, position_id)
            order_logger.info(results)

            if results.get('dealStatus', '') != 'ACCEPTED':
                error_logger.error("%s rejected modify position %s - %s !" % (self.name, position_id, market_or_instrument.market_id))
                return False

        except IGException as e:
            error_logger.error("%s except modify position %s - %s - cause : %s !" % (self.name, position_id, market_or_instrument.market_id, str(e)))
            return False

        return True

    #
    # global accessors
    #

    def positions(self, market_id):
        """
        Returns current positions for an instrtument. If the trader does not use a WS API it is possible
        to constat a latency between the reality and what it returns. Prefers use WS API as possible.
        @deprecated
        """
        positions = []

        with self._mutex:
            for k, position in self._positions.items():
                if position.symbol == market_id:
                    positions.append(copy.copy(position))

        return positions

    def market(self, market_id, force=False):
        """
        Fetch from the watcher and cache it. It rarely changes so assume it once per connection.
        @param force Force to update the cache
        """
        with self._mutex:
            market = self._markets.get(market_id)
    
            if (market is None or force) and self._watcher is not None and self._watcher.connected:
                try:
                    market = self._watcher.fetch_market(market_id)
                except Exception as e:
                    logger.error("fetch_market('%s'): %s" % (market_id, repr(e)))
                    return None

                if market:
                    with self._mutex:
                        self._markets[market_id] = market

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
            error_logger.error("fetch positions: %s" % repr(e))
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

                position.entry(direction, epic, quantity, leverage=position.leverage)

                # position are merged by epic but might be independents
                self._positions[deal_id] = position

            # account local tz, but createdDateUTC exists in API v2 (look at HTTP header v=2)
            position.created_time = datetime.strptime(pos.get('createdDate', '1970/01/01 00:00:00:000'), "%Y/%m/%d %H:%M:%S:%f").timestamp()

            position.entry_price = pos.get('openLevel', 0.0)
            position.stop_loss = pos.get('stopLevel', 0.0)
            position.take_profit = pos.get('limitLevel', 0.0)

            # guarantee stop
            if pos.get('controlledRisk', False):
                pass  # @todo

            # @todo stop type (guarantee, market, trailing)
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
            error_logger.error("fetch orders: %s" % repr(e))
            raise

        # @todo add/update/remove orders
        # and this can be done by signals

    def on_update_market(self, market_id, tradable, last_update_time, bid, ask,
            base_exchange_rate, contract_size=None, value_per_pip=None,
            vol24h_base=None, vol24h_quote=None):

        super().on_update_market(market_id, tradable, last_update_time, bid, ask, base_exchange_rate, contract_size, value_per_pip, vol24h_base, vol24h_quote)

        # update positions profit/loss for the related market id
        market = self.market(market_id)

        # market must be valid
        if market is None:
            return

        with self._mutex:
            for k, position in self._positions.items():
                if position.symbol == market.market_id:
                    position.update_profit_loss(market)
