# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Trader/autotrader connector for 1broker.com

import http.client
import urllib
import json
import time

from datetime import datetime

from notifier.notifiable import Notifiable
from notifier.signal import Signal

from trader.trader import Trader

from .account import OneBrokerAccount
from trader.position import Position
from trader.order import Order
from terminal.terminal import Terminal

from connector.onebroker.connector import OneBrokerConnector


class OneBrokerTrader(Trader):
    """
    @todo update using the shared connector throught its watcher
    @todo market/ticks/candle checkout
    @todo update order and position through WS API
    @todo cancel_order
    @todo modify_position   
    """

    # @deprecated enums mode
    MODE_MANUAL = 0
    MODE_AUTO = 1
    MODE_ENTER_MANUAL_EXIT_AUTO = 2
    MODE_ENTER_AUTO_EXIT_MANUAL = 3

    def __init__(self, service, name="1broker.com"):
        super().__init__(name, service)

        self._host = "1broker.com"
        self._base_url = "/api/v2/"
        self._checked = False
        self._account = OneBrokerAccount(self)

        trader_config = service.trader_config(self._name)
        if trader_config:
            # manual leverage configuration
            self._leverages_config = trader_config.get('leverage', {})

        self._last_update = 0
        self._connector = None

    def connect(self):
        super().connect()

        try:
            self.lock()

            identity = self.service.identity(self._name)
            if identity:
                self._host = identity.get('host')

                self._connector = OneBrokerConnector(
                    self.service,
                    identity.get('api-key'),
                    self._host)

            self._connector.connect()
        except Exception:
            pass
        finally:
            self.unlock()

    def on_watcher_connected(self, watcher_name):
        super().on_watcher_connected(watcher_name)

        # # initial account update
        # @todo could do here checkout too
        # self.account.update(self._watcher.connector)
        
        # # orders and positions
        # self.lock()
        
        # self.__fetch_orders()
        # self.__fetch_positions()

        # self.unlock()

    def on_watcher_disconnected(self, watcher_name):
        super().on_watcher_disconnected(watcher_name)

    def market(self, market_id, force=False):
        """
        Fetch from the watcher and cache it. It rarely changes so assume it once per connection.
        @param force Force to update the cache
        """
        market = self._markets.get(market_id)
        if (market is None or force) and self._watcher is not None:
            try:
                market = self._watcher.fetch_market(market_id)

                # default leverages
                if market_id in self._leverages_config:
                    market.set_leverages(self._leverages_config[market_id])
                elif '(ANY)' in self._leverages_config:
                    market.set_leverages(self._leverages_config['(ANY)'])
                else:
                    market.set_leverages(tuple(1, 200))

                self._markets[market_id] = market
            except Exception as e:
                logger.error("fetch_market: %s" % repr(e))
                raise

        return market

    def pre_run(self):
        super().pre_run()

        if self._connector.connected:
            try:
                self.checkout()
            except Exception:
                pass

    def post_run(self):
        super().post_run()

    def disconnect(self):
        super().disconnect()

        try:
            self.lock()

            if self._connector is not None:
                self._connector.disconnect()
                self._connector = None

            self._checked = False
        except Exception:
            pass
        finally:
            self.unlock()

    @Trader.mutexed
    def checkout(self):
        self._checked = True

    def pre_update(self):
        if not self._connector.connected:
            # try reconnect
            time.sleep(1.0)
            self.connect()
            return

        if not self._checked:
            self.checkout()

            if not self._checked:
                return

    def update(self):
        super().update()

        #
        # account data update
        #
        try:
            self.lock()
            self._account.update(self.connector)
        except Exception:
            pass
        finally:
            self.unlock()

        #
        # positions and orders
        #
        try:
            self.lock()

            now = time.time()
            # only once per second to avoid API excess
            if now - self._last_update > 0.5:
                self.__fetch_positions_and_orders()
                self._last_update = now
        except Exception:
            pass
        finally:
            self.unlock()               

        # @todo to be moved into strategy
        # half-auto trader strategy
        try:
            self.lock()
            if True:  # if self._mode == OneBrokerTrader.MODE_ENTER_MANUAL_EXIT_AUTO or self._mode == OneBrokerTrader.MODE_AUTO:
                # if exit auto or full auto copy the exit signal automatically
                for pos in p:
                    if pos.get('exit_price'):
                        Terminal.inst().action("position %s exited at %s", pos['position_id'], pos['exit_price'])

                        my_position = None

                        # retrieve the related position
                        for my_pos in self._positions.items():
                            if my_pos.copied_position_id == pos['position_id']:
                                my_position = my_pos
                                Terminal.inst().info("found the copy of %s as %s for close it" % (pos['position_id'], my_pos.copied_position_id))

                        if my_pos is not None:
                            # position retrieved, close request
                            self.close_position(my_pos.position_id)
        except Exception:
            pass
        finally:
            self.unlock()

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop
        time.sleep(0.0001)

    @Trader.mutexed
    def create_order(self, order):
        if not self.has_market(order.symbol):
            logger.error("%s does not support market %s in order %s !" % (self.name, order.symbol, order.order_id))
            return False

        if not self._activity:
            return False

        # order type
        # https://1broker.com/api/v2/ordesr/create.php?token=YOUR_API_TOKEN&pretty=true&symbol=GOLD&margin=0.25&direction=long&leverage=3&order_type=limit&order_type_parameter=950&referral_id=1337&shared=1
        if order.order_type == Order.ORDER_LIMIT:
            order_type = 'limit'
        elif order.order_type == Order.ORDER_STOP:
            order_type = 'stop_entry'
        else:
            order_type = 'market'

        self.lock()
        market = self._markets[order.symbol]
        self.unlock()

        direction = "long" if order.direction == Position.LONG else "short"
        margin = order.quantity

        # min/max leverage or custom leverage from account and conf @todo not here, on strategy and comes from appliance/instrument not trader
        leverage = market.clamp_leverage(order.leverage)

        var = {
            'pretty': 'false',
            'token': self._connector.api_key,
            'symbol': order.symbol,
            'margin': margin,
            'direction': direction,
            'leverage': leverage,
            'order_type': order_type,
            # 'referral_id': '72663',  # @todo referral id to receive profit for software usage, an account cannot refer itself
            'shared': "true" if self.account.shared else "false"
        }

        if order.price:
            var['order_type_parameter'] = order.price  # can be null for market

        if order.stop_loss:
            var['stop_loss'] = order.stop_loss   # can be null
        else:
            # todo compute stop loss from leverage, margin and default account stop loss in percent
            # stop_loss = order.entry_price * (1 - (self._account.default_stop_loss_rate))
            # var['stop_loss'] = stop_loss
            pass

        if order.take_profit:
            var['take_profit'] = order.take_profit   # can be null
        else:
            # todo compute stop loss from leverage, margin and default account take profit in percent
            # take_profit = order.entry_price *
            pass

        url = self._base_url + 'order/create.php?' + urllib.parse.urlencode(var)
        self._connector._conn.request("GET", url)

        response = self._connector._conn.getresponse()
        data = response.read()

        if response.status != 200:
            Terminal.inst().error("Http error create on %s a %s order for %s !" % (self.name, direction, order.symbol))
            return False
        
        data = json.loads(data)

        if data['error'] or data['warning']:
            Terminal.inst().error("API error create on %s a %s order for %s !" % (self.name, direction, order.symbol))
            return False

        p = data['response']

        order.set_order_id(p['order_id'])

        order.created_time = self._parse_datetime(p.get['date_created']).timestamp()
        order.transact_time = self._parse_datetime(p.get['date_created']).timestamp()

        self._orders[order.order_id] = order

        # {
        #   ...
        #   "response": {
        #       "order_id": "1658",
        #       "symbol": "GOLD",
        #       "margin": "0.25",
        #       "leverage": "3",
        #       "direction": "long",
        #       "order_type": "limit",
        #       "order_type_parameter": "950",
        #       "stop_loss": null,
        #       "take_profit": null,
        #       "shared": true,
        #       "date_created": "2016-11-07T13:44:32Z"
        #   }
        # }

        return True

    @Trader.mutexed
    def cancel_order(self, order_id):
        # https://1broker.com/api/v2/order/cancel.php?token=YOUR_API_TOKEN&pretty=true&order_id=18947
        # cancel close postion : https://1broker.com/api/v2/position/close_cancel.php?token=YOUR_API_TOKEN&pretty=true&position_id=4613

        # {
        #   ...
        #   "response": null
        # }

        if not self._activity:
            return False

        order = self._orders.get(order_id)

        if order is None:
            return False

        # @todo

        return False

    @Trader.mutexed
    def close_position(self, position_id, market=True, limit_price=None):
        # https://1broker.com/api/v2/position/close.php?token=YOUR_API_TOKEN&pretty=true&position_id=4613
        # the position will be deleted once really done at the update

        # @todo limit_price then do a position modification in place of the close
        # if limit_price:
        #   var['order_type_parameter'] = limit_price

        if not self._activity:
            return False

        position = self._positions.get(position_id)

        if position is None or not position.is_opened():
            return False

        var = {
            'pretty': 'false',
            'token': self._connector.api_key,
            'position_id': position.position_id
        }

        url = self._base_url + 'position/close.php?' + urllib.parse.urlencode(var)
        self._connector._conn.request("GET", url)

        response = self._connector._conn.getresponse()
        data = response.read()

        direction = "long" if position.direction == Position.LONG else "short"

        if response.status != 200:
            Terminal.inst().error("Http error close on %s a %s order for %s !" % (self.name, direction, position.symbol))
            return False
        
        data = json.loads(data)

        if data['error'] or data['warning']:
            Terminal.inst().error("API error close on %s a %s order for %s !" % (self.name, direction, position.symbol))
            return False

        p = data['response']

        # set position closing until we get confirmation on a next update
        position.closing(limit_price)

        # {
        #   ...
        #   "response": null
        # }

        return True

    @Trader.mutexed
    def modify_position(self, position_id, stop_loss_price=None, take_profit_price=None):
        if not self._activity:
            return False

        position = self._positions.get(position_id)

        if position is None or not position.is_opened():
            return False

        # @todo

        return False

    @property
    def authenticated(self):
        return self.connected # and self._connector.authenticated

    @property
    def connected(self):
        return self._connector and self._connector.connected

    def positions(self, market_id):
        self.lock()

        # fetching is important here because we don't do it every second and we don't use WS API for now
        self.__fetch_positions_and_orders()

        # possible hedging... filter by market id
        positions = []

        for k, position in self._positions.items()
            if position.symbol == market_id:
                positions.append(copy.copy(position))

        self.unlock()
        return positions

    #
    # protected
    #

    def __fetch_positions_and_orders(self):
        #
        # get opened position and once a position occurs with our order_id create the position and make the link
        #

        # https://1broker.com/api/v2/position/open.php?token=YOUR_API_TOKEN&pretty=true
        var = {
            'pretty': 'false',
            'token': self._connector.api_key
        }

        url = self._base_url + 'position/open.php?' + urllib.parse.urlencode(var)
        self._connector._conn.request("GET", url)

        response = self._connector._conn.getresponse()
        data = response.read()

        if response.status != 200:
            Terminal.inst().error("Http error (%s) list positions on %s !" % (response.status, self.name,))
            return None

        data = json.loads(data)

        if data['error'] or data['warning']:
            Terminal.inst().error("API error list positions on %s !" % (self.name,))
            return None

        p = data['response']

        for pos in p:
            # if order_id is one of non linked order and not found in positions list
            order = self._orders.get(pos['order_id'])
            position = self._positions.get(pos['position_id'])

            copy_of = pos['copy_of']

            if order is not None and position is None:
                # an order open to a position

                # insert the new position
                position = Position(self)

                position.set_position_id(pos['position_id'])
                position.set_key(self.service.gen_key())

                # create the position
                position.set_copied_position_id(order.copied_position_id)
                position.entry(
                    Position.LONG if pos['direction'] == 'long' else Position.SHORT,
                    pos['symbol'],
                    pos['margin'],
                    float(pos['take_profit']) if pos['take_profit'] else None,
                    float(pos['stop_loss']) if pos['stop_loss'] else None,
                    float(pos['leverage']),
                    pos['trailing_stop_loss']
                )

                position.author = order.author
                position.entry_price = pos['entry_price']
                position.quantity = float(pos['value'])
                position.shared = pos['shared']
                position.profit_loss = float(pos['profit_loss'])
                position.profit_loss_rate = float(pos['profit_loss_percent']) * 0.01
                position.market_close = pos['market_close']
                position.created_time = datetime.strptime(pos['date_created'], "%Y-%m-%dT%H:%M:%SZ").timestamp() # .%fZ")

                # delete the order
                del self._orders[pos['order_id']]

                # insert the position
                self._positions[position.position_id] = position

            elif position is not None and order is None:
                # only have to update

                # update the position
                position.profit_loss = float(pos['profit_loss'])
                position.profit_loss_rate = float(pos['profit_loss_percent']) * 0.01
                position.market_close = pos['market_close']

                # can be a full update
                if not position.created_time:
                    position.entry(
                        Position.LONG if pos['direction'] == 'long' else Position.SHORT,
                        pos['symbol'],
                        pos['margin'],
                        float(pos['take_profit']) if pos['take_profit'] else None,
                        float(pos['stop_loss']) if pos['stop_loss'] else None,
                        float(pos['leverage']),
                        pos['trailing_stop_loss']
                    )

                    position.entry_price = pos['entry_price']
                    position.quantity = float(pos['value'])
                    position.shared = pos['shared']
                    position.created_time = datetime.strptime(pos['date_created'], "%Y-%m-%dT%H:%M:%SZ").timestamp() # .%fZ")

            elif order is None and position is None:
                # externaly created position or with auto copy of plateforme

                # create from copy of position (lookup for position)
                position = Position(self)

                position.set_position_id(pos['position_id'])
                position.set_key(self.service.gen_key())
                # position.set_order_id(pos['order_id'])

                # create the position
                position.set_copied_position_id(copy_of)
                position.entry(
                    Position.LONG if pos['direction'] == 'long' else Position.SHORT,
                    pos['symbol'],
                    pos['margin'],
                    pos['take_profit'],
                    pos['stop_loss'],
                    float(pos['leverage']),
                    pos['trailing_stop_loss']
                )

                # retrieve the order, the author...
                # position.author = order.author
                position.entry_price = pos['entry_price']
                position.quantity = float(pos['value'])
                position.shared = pos['shared']
                position.profit_loss = float(pos['profit_loss'])
                position.profit_loss_rate = float(pos['profit_loss_percent']) * 0.01
                position.market_close = pos['market_close']
                position.created_time = datetime.strptime(pos['date_created'], "%Y-%m-%dT%H:%M:%SZ").timestamp() # .%fZ")

                # insert the position
                self._positions[position.position_id] = position

                # retrieve the copied position id from database @todo
                logger.info("Retrieve pos %s copied from position %s" % (position.position_id, position.copied_position_id))

        #
        # check for cleared position
        #
        remove_list = []

        for k, position in self._positions.items():
            found = False

            for pos in p:
                if pos['position_id'] == position.position_id:
                    found = True
                    break

            if not found:
                # cleared but a copied trader or himself externaly
                remove_list.append(k)

        for k in remove_list:
             del self._positions[k]
