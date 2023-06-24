# @date 2018-08-25
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Trader connector for binance.com

from __future__ import annotations

from typing import TYPE_CHECKING, List, Union, Optional, Tuple

if TYPE_CHECKING:
    from trader.service import TraderService
    from trader.position import Position
    from instrument.instrument import Instrument
    from watcher.connector.binance.watcher import BinanceWatcher

import time
import traceback

from trader.trader import Trader

from .account import BinanceAccount

from trader.asset import Asset
from trader.order import Order
from trader.market import Market

from database.database import Database

from connector.binance.exceptions import *
from connector.binance.client import Client

from trader.traderexception import TraderException

import logging
logger = logging.getLogger('siis.trader.binance')
error_logger = logging.getLogger('siis.error.trader.binance')
order_logger = logging.getLogger('siis.order.trader.binance')
traceback_logger = logging.getLogger('siis.traceback.trader.binance')


class BinanceTrader(Trader):
    """
    Binance market trader.
    
    @note __update_asset use the last tick price in way to compute the average price of the owned asset quantity,
        but querying the prices cost an extra API credit plus an important latency we cannot offer during live.
    """

    COMPUTE_ASSET_PRICE = False

    _watcher: Union[BinanceWatcher, None]

    def __init__(self, service: TraderService):
        super().__init__("binance.com", service)

        self._watcher = None
        self._account = BinanceAccount(self)

        self._quotes = []
        self._ready = False

    @property
    def watcher(self) -> BinanceWatcher:
        return self._watcher

    @property
    def authenticated(self) -> bool:
        return self.connected and self._watcher.connector.authenticated

    @property
    def connected(self) -> bool:
        return self._watcher is not None and self._watcher.connector is not None and self._watcher.connector.connected

    def connect(self):
        super().connect()

        # retrieve the binance.com watcher and take its connector
        with self._mutex:
            self._watcher = self.service.watcher_service.watcher(self._name)
            self._ready = False

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
                self._ready = False

    def on_watcher_connected(self, watcher_name: str):
        super().on_watcher_connected(watcher_name)

        # markets and orders
        logger.info("- Trader %s retrieving data..." % self._name)

        # insert the assets (fetch after)
        try:
            balances = self._watcher.connector.balances()
        except Exception as e:
            balances = []

        with self._mutex:
            try:
                # fill the list with quotes symbols
                symbols = self._watcher.connector.client.get_exchange_info()
                for symbol in symbols['symbols']:
                    if symbol['quoteAsset'] not in self._quotes:
                        self._quotes.append(symbol['quoteAsset'])

                # and add any asset of the balance
                for balance in balances:
                    asset_name = balance['asset']
                    self.__get_or_add_asset(asset_name)

                self.account.update(self._watcher.connector)

            except Exception as e:
                error_logger.error(repr(e))

        # fetch the asset from the DB and after signal fetch from binance
        Database.inst().load_assets(self.service, self, self.name, self.account.name)

        logger.info("Trader %s got data. Running." % self._name)

    def on_watcher_disconnected(self, watcher_name: str):
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

        if not self._ready:
            return False

        #
        # account data update (normal case don't call REST)
        #

        with self._mutex:
            self._account.update(self._watcher.connector)

        return True

    def post_update(self):
        super().post_update()

        # don't wast the CPU 5 ms loop
        time.sleep(0.005)

    #
    # ordering
    #

    def create_order(self, order: Order, market_or_instrument: Union[Market, Instrument]) -> int:
        """
        Create a market or limit order using the REST API. Take care to do not make too many calls per minutes.
        """
        if not order or not market_or_instrument:
            return Order.REASON_INVALID_ARGS

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse order because of missing connector" % (self.name,))
            return Order.REASON_ERROR

        # order type
        if order.order_type == Order.ORDER_MARKET:
            order_type = Client.ORDER_TYPE_MARKET

        elif order.order_type == Order.ORDER_LIMIT:
            order_type = Client.ORDER_TYPE_LIMIT

        elif order.order_type == Order.ORDER_STOP:
            order_type = Client.ORDER_TYPE_STOP_LOSS

        # @todo OCO, take profit market, take profit limit, stop loss limit

        else:
            error_logger.error("Trader %s refuse order because the order type is unsupported %s in order %s !" % (
                self.name, market_or_instrument.symbol, order.ref_order_id))

            return Order.REASON_INVALID_ARGS

        symbol = order.symbol
        side = Client.SIDE_BUY if order.direction == Order.LONG else Client.SIDE_SELL

        # @todo as option for the order strategy
        time_in_force = Client.TIME_IN_FORCE_GTC

        if order.quantity < market_or_instrument.min_size:
            # reject if lesser than min size
            error_logger.error("Trader %s refuse order because the min size is not reached (%s<%s) %s in order %s !" % (
                self.name, order.quantity, market_or_instrument.min_size, symbol, order.ref_order_id))

            return Order.REASON_INVALID_ARGS

        # adjust quantity to step min and max, and round to decimal place of min size, and convert it to str
        # quantity = market_or_instrument.format_quantity(market_or_instrument.adjust_quantity(order.quantity))
        quantity = market_or_instrument.adjust_quantity(order.quantity)
        notional = quantity * (order.price or market_or_instrument.market_ask)

        if notional < market_or_instrument.min_notional:
            # reject if lesser than min notional
            error_logger.error("Trader %s refuse order because the min notional is not reached (%s<%s) %s in order %s !" % (
                self.name, notional, market_or_instrument.min_notional, symbol, order.ref_order_id))

            return Order.REASON_INVALID_ARGS

        data = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity,
            'newOrderRespType': Client.ORDER_RESP_TYPE_RESULT,
            'recvWindow': 10000
        }

        # limit order need timeInForce
        if order.order_type == Order.ORDER_LIMIT:
            data['price'] = market_or_instrument.format_price(order.price)
            data['timeInForce'] = time_in_force

        elif order.order_type == Order.ORDER_STOP:
            data['stopPrice'] = market_or_instrument.format_price(order.stop_price)

        elif order.order_type == Order.ORDER_STOP_LIMIT:
            data['price'] = market_or_instrument.format_price(order.price)
            data['stopPrice'] = market_or_instrument.format_price(order.stop_price)
            data['timeInForce'] = time_in_force

        elif order.order_type == Order.ORDER_TAKE_PROFIT:
            data['stopPrice'] = market_or_instrument.format_price(order.stop_price)

        elif order.order_type == Order.ORDER_TAKE_PROFIT_LIMIT:
            data['price'] = market_or_instrument.format_price(order.price)
            data['stopPrice'] = market_or_instrument.format_price(order.stop_price)
            data['timeInForce'] = time_in_force

        data['newClientOrderId'] = order.ref_order_id
        # data['icebergQty'] = 0.0

        logger.info("Trader %s order %s %s %s @%s" % (self.name, order.direction_to_str(), data.get('quantity'),
                                                      symbol, data.get('price')))

        result = None
        reason = None

        try:
            result = self._watcher.connector.client.create_order(**data)
            # result = self._watcher.connector.client.create_test_order(**data)
        except BinanceRequestException as e:
            reason = str(e)
        except BinanceAPIException as e:
            reason = str(e)
        except BinanceOrderException as e:
            reason = str(e)

        if reason:
            error_logger.error("Trader %s rejected order %s %s %s - reason : %s !" % (
                self.name, order.direction_to_str(), quantity, symbol, reason))

            # @todo reason to error
            return Order.REASON_ERROR

        if result:
            if result.get('status', "") == Client.ORDER_STATUS_REJECTED:
                error_logger.error("Trader %s rejected order %s %s %s !" % (self.name, order.direction_to_str(),
                                                                            quantity, symbol))
                order_logger.error(result)

                return Order.REASON_ERROR

            if 'orderId' in result:
                order_logger.info(result)

                order.set_order_id(result['orderId'])

                order.created_time = result['transactTime'] * 0.001
                order.transact_time = result['transactTime'] * 0.001

                # if result['executedQty']:
                #     # partially or fully executed quantity
                #     order.set_executed(float(result['executedQty']), result.get['status'] == "FILLED", float(result['price']))

                return Order.REASON_OK

        # unknown error
        error_logger.error("Trader %s rejected order %s %s %s !" % (self.name, order.direction_to_str(),
                                                                    quantity, symbol))
        order_logger.error(result)

        return Order.REASON_ERROR

    def cancel_order(self, order_id: str, market_or_instrument: Union[Market, Instrument]) -> int:
        """
        Cancel a pending or partially filled order.
        """
        if not order_id or not market_or_instrument:
            return Order.REASON_INVALID_ARGS

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse order because of missing connector" % (self.name,))
            return Order.REASON_ERROR

        symbol = market_or_instrument.market_id

        data = {
            # 'newClientOrderId': ref_order_id,
            'symbol': symbol,
            'orderId': order_id,
            'recvWindow': 10000
        }

        reason = None
        result = None

        try:
            result = self._watcher.connector.client.cancel_order(**data)
        except BinanceRequestException as e:
            reason = str(e)
        except BinanceAPIException as e:
            reason = str(e)
        except BinanceOrderException as e:
            reason = str(e)

        if reason:
            # Unknown order sent : reason.code -2011
            error_logger.error("Trader %s rejected cancel order %s %s reason %s !" % (self.name, order_id, symbol,
                                                                                      reason))

            return Order.REASON_ERROR

        if result:
            if result.get('status', "") == Client.ORDER_STATUS_REJECTED:
                error_logger.error("Trader %s rejected cancel order %s %s reason %s !" % (self.name, order_id, symbol,
                                                                                          reason))
                order_logger.error(result)

                return Order.REASON_ERROR

            order_logger.info(result)

        # ok
        return Order.REASON_OK

    def close_position(self, position_id: str, market_or_instrument: Union[Market, Instrument],
                       direction: int, quantity: float, market: bool = True,
                       limit_price: Optional[float] = None) -> bool:
        """
        Not supported.
        """
        if not position_id or not market_or_instrument:
            return False

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse to close position because of missing connector" % (self.name,))
            return False

        return False

    def modify_position(self, position_id: str, market_or_instrument: Union[Market, Instrument],
                        stop_loss_price: Optional[float] = None, take_profit_price: Optional[float] = None) -> bool:
        """
        Not supported.
        """
        if not position_id or not market_or_instrument:
            return False
        
        if not self._watcher.connector:
            error_logger.error("Trader %s refuse to close position because of missing connector" % (self.name,))
            return False

        return False

    def positions(self, market_id: str) -> List[Position]:
        """
        Not supported.
        @deprecated
        """
        return []

    def market(self, market_id: str, force: bool = False) -> Union[Market, None]:
        """
        Fetch from the watcher and cache it. It rarely changes so assume it once per connection.
        @param market_id: str Market id
        @param force Force to update the cache
        """
        with self._mutex:
            market = self._markets.get(market_id)

        if (market is None or force) and self._watcher is not None and self._watcher.connected:
            try:
                market = self._watcher.fetch_market(market_id)
            except Exception as e:
                logger.error("fetch_market: %s" % repr(e))
                return None

            if market:
                with self._mutex:
                    self._markets[market_id] = market

        return market

    def order_info(self, order_id: str, market_or_instrument: Union[Market, Instrument]) -> Union[dict, None]:
        """
        Retrieve the detail of an order.
        """
        if not order_id or not market_or_instrument:
            return None

        if not self._watcher.connector:
            error_logger.error("Trader %s refuse to retrieve order info because of missing connector" % self.name)
            return None

        results = None

        try:
            results = self._watcher.connector.order_info(market_or_instrument.market_id, order_id)
        except Exception:
            # None as error
            return None

        if results and str(results.get('orderId', 0)) == order_id:
            order_data = results
            logger.debug(str(order_data))

            try:
                symbol = order_data['symbol']
                market = self.market(symbol)

                if not market:
                    return None

                price = None
                stop_price = None
                completed = False
                order_ref_id = order_data['clientOrderId']
                event_timestamp = order_data['updateTime'] * 0.001 if 'updateTime' in order_data else order_data['time'] * 0.001

                if order_data['status'] == Client.ORDER_STATUS_NEW:
                    status = 'opened'
                elif order_data['status'] == Client.ORDER_STATUS_PENDING_CANCEL:
                    # @note not exactly the same meaning
                    status = 'pending'
                elif order_data['status'] == Client.ORDER_STATUS_FILLED:
                    status = 'closed'
                    completed = True
                    if 'updateTime' in order_data:
                        event_timestamp = order_data['updateTime'] * 0.001
                elif order_data['status'] == Client.ORDER_STATUS_PARTIALLY_FILLED:
                    status = 'opened'
                    completed = False
                    if 'updateTime' in order_data:
                        event_timestamp = order_data['updateTime'] * 0.001
                elif order_data['status'] == Client.ORDER_STATUS_CANCELED:
                    status = 'canceled'
                    # status = 'deleted'
                elif order_data['status'] == Client.ORDER_STATUS_EXPIRED:
                    status = 'expired'
                    # completed = True ? and on watcher WS...
                else:
                    status = ""

                # 'type' and 'origType'
                if order_data['type'] == Client.ORDER_TYPE_LIMIT:
                    order_type = Order.ORDER_LIMIT
                    price = float(order_data['price']) if 'price' in order_data else None

                elif order_data['type'] == Client.ORDER_TYPE_MARKET:
                    order_type = Order.ORDER_MARKET

                elif order_data['type'] == Client.ORDER_TYPE_STOP_LOSS:
                    order_type = Order.ORDER_STOP
                    price = float(order_data['price']) if 'price' in order_data else None
                    stop_price = float(order_data['stopPrice']) if 'stopPrice' in order_data else None

                elif order_data['type'] == Client.ORDER_TYPE_STOP_LOSS_LIMIT:
                    order_type = Order.ORDER_STOP_LIMIT
                    price = float(order_data['price']) if 'price' in order_data else None
                    stop_price = float(order_data['stopPrice']) if 'stopPrice' in order_data else None

                elif order_data['type'] == Client.ORDER_TYPE_TAKE_PROFIT_LIMIT:
                    order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    price = float(order_data['price']) if 'price' in order_data else None
                    stop_price = float(order_data['stopPrice']) if 'stopPrice' in order_data else None

                elif order_data['type'] == Client.ORDER_TYPE_LIMIT_MAKER:
                    order_type = Order.ORDER_TAKE_PROFIT
                    stop_price = float(order_data['stopPrice']) if 'stopPrice' in order_data else None

                else:
                    order_type = Order.ORDER_MARKET

                if order_data['timeInForce'] == Client.TIME_IN_FORCE_GTC:
                    time_in_force = Order.TIME_IN_FORCE_GTC
                elif order_data['timeInForce'] == Client.TIME_IN_FORCE_IOC:
                    time_in_force = Order.TIME_IN_FORCE_IOC
                elif order_data['timeInForce'] == Client.TIME_IN_FORCE_FOK:
                    time_in_force = Order.TIME_IN_FORCE_FOK
                else:
                    time_in_force = Order.TIME_IN_FORCE_GTC

                post_only = False
                cumulative_commission_amount = 0.0  # @todo

                cumulative_filled = float(order_data['executedQty'])
                order_volume = float(order_data['origQty'])
                fully_filled = completed

                # trades = array of trade ids related to order (if trades info requested and data available)
                trades = []

                order_info = {
                    'id': order_id,
                    'symbol': symbol,
                    'status': status,
                    'ref-id': order_ref_id,
                    'direction': Order.LONG if order_data['side'] == Client.SIDE_BUY else Order.SHORT,
                    'type': order_type,
                    'timestamp': event_timestamp,
                    'quantity': order_volume,
                    'cumulative-filled': cumulative_filled,
                    'cumulative-commission-amount': cumulative_commission_amount,
                    'quote-transacted': float(order_data.get('cummulativeQuoteQty', "0.0")),
                    'price': price,
                    'stop-price': stop_price,
                    'time-in-force': time_in_force,
                    'post-only': post_only,
                    # 'close-only': ,
                    'fully-filled': fully_filled
                    # 'trades': trades
                }

                # @todo average execution price
                if 'price' in order_data:
                    order_info['exec-price'] = float(order_data['price'])

                return order_info

            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

                # error during processing
                return None

        # empty means success returns but does not exist
        return {
            'id': None
        }

    #
    # slots
    #

    def on_assets_loaded(self, assets: Union[List[Asset], None]):
        if assets is None:
            return

        logger.info("Trader %s retrieving asset and orders..." % self._name)

        with self._mutex:
            try:
                # doesn't erase them because need the last list of markets
                for asset in assets:
                    # set data from fetched one
                    local_asset = self._assets.get(asset.symbol)
                    if local_asset:
                        # update stored asset
                        local_asset.update_price(asset.last_update_time, asset.last_trade_id, asset.price)
                        local_asset.set_quantity(asset.quantity, 0)  # no idea of locked/free set all locked
                    else:
                        # store it
                        self._assets[asset.symbol] = asset

                # and fetch them to be synced + opened orders
                self.__fetch_assets()
                self.__fetch_orders()

                # can deal with
                self._ready = True

                logger.info("Trader %s got asset and orders." % self._name)

            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

    #
    # protected
    #

    def __fetch_assets(self):
        """
        Fetch recent asset and update the average unit price per asset and set it into positions.

        @note Asset must be fetched before from DB if existing.
        @todo prefetch/compute option
        """
        query_time = time.time()

        try:
            balances_list = self._watcher.connector.balances()
            # dust_log = self._watcher.connector.get_dust_log()
            exchange_info = self._watcher._symbols_data  # self._watcher.connector.client.get_exchange_info()
        except Exception as e:
            error_logger.error("__fetch_assets: %s" % repr(e))
            raise TraderException(self.name, "__fetch_assets: %s" % repr(e))

        #
        # symbols details by asset and market
        #

        symbols = {}
        markets = {}

        for k, symbol in exchange_info.items():
            # for k, symbol in exchange_info.get('symbols', {}).items():
            # store asset precisions
            symbols[symbol['baseAsset']] = {
                'precision': symbol['baseAssetPrecision']
            }
            symbols[symbol['quoteAsset']] = {
                'precision': symbol['quotePrecision']
            }

            # store market details
            markets[symbol['symbol']] = symbol

        #
        # balances used for fee must be put at the last
        #

        balances = {}  # to a dict

        for balance in balances_list:           
            asset_name = balance['asset']
            balance['trades'] = []

            #
            # find the most appropriate quote if necessary
            #

            asset = self.__get_or_add_asset(asset_name)
            asset.precision = symbols.get(asset.symbol, {'precision': 8})['precision']

            balance['quote'] = asset.quote
            balances[asset.symbol] = balance

        #
        # prefetch for currently non-empty assets
        #

        if self.COMPUTE_ASSET_PRICE:
            for k, balance in balances.items():
                asset_name = balance['asset']

                locked = float(balance['locked'])
                free = float(balance['free'])

                quote_symbol = balance['quote']
                asset = self.__get_or_add_asset(asset_name)

                quantity = free + locked

                # not empty balance or was not empty but not it is
                if quantity or (not quantity and asset.quantity):
                    quantity = free + locked

                    last_update_time = asset.last_update_time
                    last_trade_id = asset.last_trade_id

                    # get recent deposits and withdraws
                    deposits = []  # self._watcher.connector.deposits(asset_name, last_update_time)
                    withdraws = []  # self._watcher.connector.withdraws(asset_name, last_update_time)

                    #
                    # small balances (@todo to be sure they does not appears in transactions list)
                    #

                    # @deprecated
                    # for dust in dust_log:
                    #   for log in dust['logs']:
                    #       if log['fromAsset'] == asset_name:
                    #           time = 0  # 'operateTime': '2018-10-08 20:11:18' @todo is UTC or LOCAL ? ...
                    #           if time > last_update_time:  # strictly greater than
                    #               price = self.history_price(asset_name+quote_symbol, float(log['operateTime'])*0.001)
                    #               balance['trades'].append({
                    #                   'id': 0,  # no id only for trades
                    #                   'time': time,
                    #                   'quote': quote_symbol,
                    #                   'price': price,
                    #                   'qty': log['amount'],
                    #                   # 'commission': log['serviceChargeAmount']  # think its already minus from transferedAmount
                    #                   'isBuyer': False  # as seller to dec qty
                    #               })

                    #           balances['BNB']['trade'].append((log['transferedAmount'], time, True))  # as buyer to inc qty

                    #
                    # deposits are like buy trades
                    #

                    # @deprecated
                    for deposit in deposits:
                        # only success deposits at insertTime (we don't know precisely the moment and the price of
                        # the buy it's all we have to deal with)
                        if deposit['status'] == 1:
                            timestamp = float(deposit['insertTime'])*0.001
                            if timestamp > last_update_time:  # strictly greater than
                                price = self.history_price(asset_name+quote_symbol, timestamp)
                                balance['trades'].append({
                                    'id': 0,  # no id only for trades
                                    'time': deposit['insertTime'],
                                    'quote': quote_symbol,
                                    'price': price,
                                    'qty': deposit['amount'],
                                    'isBuyer': True
                                })

                    #
                    # withdraws are like sell trades
                    #

                    # @deprecated
                    for withdraw in withdraws:
                        if withdraw['status'] == 6:
                            timestamp = float(withdraw['applyTime'])*0.001
                            if timestamp > last_update_time:  # strictly greater than
                                price = self.history_price(asset_name+quote_symbol, timestamp)
                                fee = 0.0
                                # @todo compute withdraw fee
                                # fee = symbols[symbol['baseAsset']]['']

                                balance['trades'].append({
                                    'id': 0,
                                    'time': withdraw['applyTime'],
                                    'quote': quote_symbol,
                                    'price': price,
                                    'qty': withdraw['amount'],
                                    'isBuyer': False,
                                    'commission': fee
                                })

                    #
                    # trades (buy or sell)
                    #

                    # for each quote get trades for every quotes
                    for qs in self._quotes:
                        symbol = asset_name + qs

                        if self._watcher.has_instrument(symbol):
                            # query for post last update trades only
                            trades_per_quote = self._watcher.connector.trades_for(symbol, timestamp=last_update_time)  # from_id=last_trade_id)

                            # related market details
                            market = markets[symbol]

                            for trade in trades_per_quote:
                                timestamp = float(trade['time'])*0.001

                                # check only recent trades not strictly because multiple trade at same
                                # last time are possibles
                                if timestamp >= last_update_time and trade['id'] > last_trade_id:
                                    # compute the preferred quote-price
                                    quote_base = market['quoteAsset']
                                    quote_quote = market['quoteAsset']
                                    quote_price = 1.0

                                    if (quote_base != quote_symbol) and (quote_base != quote_quote):
                                        # find a quote price if trade quote is not the preferred quote symbol for this asset
                                        # and if we have a quote for it (counter-example is USDT asset,
                                        # it's a base with price constant to 1.0)
                                        quote_quote = balances[quote_base]['quote']

                                        if self._watcher.has_instrument(quote_base+quote_quote):
                                            quote_price = self.history_price(quote_base+quote_quote, timestamp)
                                        else:
                                            logger.warning("Missing symbol " + quote_base+quote_quote)

                                    # counterpart in the quote asset
                                    balances[quote_base]['trades'].append({
                                        'id': 0,
                                        'time': trade['time'],
                                        'quote': quote_quote,
                                        'price': quote_price,
                                        'qty': float(trade['qty']) * float(trade['price']),
                                        'isBuyer': not trade['isBuyer']  # neg
                                    })

                                    # quote-price will be needed to convert into BTC, 'price' define the price of the asset
                                    trade['quote'] = quote_symbol
                                    trade['quote-price'] = quote_price
                                    balance['trades'].append(trade)

                                    # fee asset trade
                                    if trade['commission']:
                                        fee_asset = trade['commissionAsset']
                                        fee_quote = balances[fee_asset]['quote']

                                        if self._watcher.has_instrument(fee_asset+fee_quote):
                                            fee_price = self.history_price(fee_asset+fee_quote, timestamp)
                                        elif self._watcher.has_instrument(fee_quote+fee_asset):
                                            fee_price = 1.0 / self.history_price(fee_quote+fee_asset, timestamp)
                                        else:
                                            fee_price = 1.0

                                        balances[fee_asset]['trades'].append({
                                            'id': 0,
                                            'time': trade['time'],
                                            'quote': fee_quote,
                                            'price': fee_price,
                                            'qty': float(trade['commission']),
                                            'isBuyer': False  # always minus
                                        })

        #
        # compute entry price
        #

        for k, balance in balances.items():
            asset_name = balance['asset']
            locked = float(balance['locked'])
            free = float(balance['free'])       

            asset = self.__get_or_add_asset(asset_name)

            # ordered by time first and id second, older first, remove trades when quantity reach 0
            trades = sorted(balance['trades'], key=lambda _trade: (_trade['time'], _trade['id']))

            # compute the entry price
            last_update_time = asset.last_update_time
            last_trade_id = asset.last_trade_id

            prev_qty = asset.quantity  # previous computed quantity
            prev_price = asset.price   # and price

            curr_qty = 0.0
            curr_price = 0.0

            quantity = free + locked

            # only if qty is not zero or zero but asset previous qty is not zero
            if quantity or (not quantity and asset.quantity):
                realized_trades = trades

                # start with previous quantity, adjusted during previous step
                curr_price = prev_price
                curr_qty = prev_qty

                for trade in realized_trades:
                    buy_or_sell = trade['isBuyer']
                    trade_qty = float(trade['qty'])
                    timestamp = float(trade['time']) * 0.001

                    if not trade['price']:
                        continue

                    # base price always expressed in the same quote, time in seconds
                    price = float(trade['price']) * trade.get('quote-price', 1.0)

                    # in BTC
                    if curr_qty+trade_qty > 0.0:
                        if buy_or_sell:
                            # adjust price when buying
                            curr_price = ((price*trade_qty) + (curr_price*curr_qty)) / (curr_qty+trade_qty)
                            curr_price = max(0.0, round(curr_price, asset.precision))

                        curr_qty += trade_qty if buy_or_sell else -trade_qty
                        curr_qty = max(0.0, round(curr_qty, asset.precision))
                    else:
                        curr_price = 0.0
                        curr_qty = 0

                    last_trade_id = max(last_trade_id, trade['id'])
                    last_update_time = max(last_update_time, timestamp)  # time in seconds

                if not last_update_time:
                    last_update_time = query_time

                #
                # settings results
                #

                if not curr_price and quantity > 0:
                    if self._watcher.has_instrument(asset_name+asset.quote):
                        curr_price = self.history_price(asset_name+asset.quote, time.time()-60.0)
                    elif self._watcher.has_instrument(asset.quote+asset_name):
                        curr_price = 1.0 / self.history_price(asset.quote+asset_name, time.time()-60.0)
                    else:
                        curr_price = 1.0
                        logger.warning("Unsupported quote for asset " + asset_name)

                # update the asset
                asset.update_price(query_time, last_trade_id, curr_price)
                asset.set_quantity(locked, free)

                quantity_deviation = abs(quantity-curr_qty) / (quantity or 1.0)

                if asset.market_ids:
                    # take the first market to use it to compute the profit/loss
                    market = self._markets.get(asset.market_ids[0])
                    asset.update_profit_loss(market)

                    if quantity_deviation >= 0.001:
                        # significant deviation...
                        logger.debug("%s deviation of computed quantity for %s from %s but must be %s" % (
                            self._name, asset_name, market.format_quantity(curr_qty), market.format_quantity(quantity)))
                else:
                    if quantity_deviation >= 0.001:
                        # significant deviation...
                        logger.debug("%s deviation of computed quantity for %s from %.8f but must be %.8f" % (
                            self._name, asset_name, curr_qty, quantity))

                # store in database with the last computed entry price
                Database.inst().store_asset((
                    self._name, self.account.name,
                    asset_name, str(asset.last_trade_id), int(asset.last_update_time*1000.0),
                    asset.quantity, asset.format_price(asset.price), asset.quote))
            else:
                # no more quantity at time just before the query was made
                asset.update_price(query_time, asset.last_trade_id, 0.0)
                asset.set_quantity(0.0, 0.0)

                # store in database with the last computed entry price
                Database.inst().store_asset((
                    self._name, self.account.name,
                    asset_name, str(asset.last_trade_id), int(asset.last_update_time*1000.0),
                    0.0, 0.0, asset.quote))

    def __get_or_add_asset(self, asset_name: str, precision: int = 8):
        if asset_name in self._assets:
            return self._assets[asset_name]

        asset = Asset(self, asset_name, precision)
        self._assets[asset_name] = asset

        # and find related watched markets
        for qs in self._quotes:
            if asset_name+qs in self._markets:
                if qs == self._account.currency:
                    asset.add_market_id(asset_name+qs, True)
                    asset.quote = qs
                elif qs == self._account.alt_currency:
                    asset.add_market_id(asset_name+qs)
                    asset.quote = qs

        if not asset.quote:
            # find the most appropriate quote for each asset.
            if asset.symbol != self._account.currency and self._watcher.has_instrument(
                    asset.symbol+self._account.currency):
                asset.quote = self._account.currency
            elif asset.symbol != self._account.alt_currency and self._watcher.has_instrument(
                    asset.symbol+self._account.alt_currency):
                asset.quote = self._account.alt_currency
            elif self._watcher.has_instrument(asset.symbol+'USD'):
                asset.quote = 'USD'

            if not asset.quote:
                logger.warning("No found quote for asset %s" % asset.symbol)

        return asset

    def __fetch_orders(self, signals=False):
        """
        This is the synchronous REST fetching, but prefer the WS asynchronous and live one.
        Mainly used for initial fetching.
        """
        try:
            open_orders = self._watcher.connector.open_orders()  # API cost 40 
        except Exception as e:
            logger.error("__fetch_orders: %s" % repr(e))
            raise

        orders = {}

        for data in open_orders:
            market = self.market(data['symbol'])

            if data['status'] == 'NEW':  # might be...
                order = Order(self, data['symbol'])

                order.set_order_id(data['orderId'])
                order.quantity = float(data.get('origQty', "0.0"))
                order.executed = float(data.get('executedQty', "0.0"))

                order.direction = Order.LONG if data['side'] == 'BUY' else Order.SHORT

                if data['type'] == 'LIMIT':
                    order.order_type = Order.ORDER_LIMIT
                    order.price = float(data['price']) if 'price' in data else None

                elif data['type'] == 'LIMIT_MAKER':
                    order.order_type = Order.ORDER_LIMIT # _MAKER
                    order.price = float(data['price']) if 'price' in data else None

                elif data['type'] == 'MARKET':
                    order.order_type = Order.ORDER_MARKET

                elif data['type'] == 'STOP_LOSS':
                    order.order_type = Order.ORDER_STOP
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                elif data['type'] == 'STOP_LOSS_LIMIT':
                    order.order_type = Order.ORDER_STOP_LIMIT
                    order.price = float(data['price']) if 'price' in data else None
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                elif data['type'] == 'TAKE_PROFIT':
                    order.order_type = Order.ORDER_TAKE_PROFIT
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                elif data['type'] == 'TAKE_PROFIT_LIMIT':
                    order.order_type = Order.ORDER_TAKE_PROFIT_LIMIT
                    order.price = float(data['price']) if 'price' in data else None
                    order.stop_price = float(data['stopPrice']) if 'stopPrice' in data else None

                order.created_time = data['time'] * 0.001
                order.transact_time = data['updateTime'] * 0.001

                if data['timeInForce'] == 'GTC':
                    order.time_in_force = Order.TIME_IN_FORCE_GTC
                elif data['timeInForce'] == 'IOC':
                    order.time_in_force = Order.TIME_IN_FORCE_IOC
                elif data['timeInForce'] == 'FOK':
                    order.time_in_force = Order.TIME_IN_FORCE_FOK
                else:
                    order.time_in_force = Order.TIME_IN_FORCE_GTC

                # "icebergQty": "0.0"  # @todo a day when I'll be rich
                orders[order.order_id] = order

        # if signals:
        #     # deleted (for signals if no WS)
        #     deleted_list = self._orders.keys() - orders.keys()
        #     # @todo

        #     # created (for signals if no WS)
        #     created_list = orders.keys() - self._orders.keys()
        #     # @todo

        if orders:
            with self._mutex:
                self._orders = orders

    #
    # markets
    #

    def on_update_market(self, market_id: str, tradeable: bool, last_update_time: float, bid: float, ask: float,
                         base_exchange_rate: Optional[float] = None,
                         contract_size: Optional[float] = None, value_per_pip: Optional[float] = None,
                         vol24h_base: Optional[float] = None, vol24h_quote: Optional[float] = None):

        super().on_update_market(market_id, tradeable, last_update_time, bid, ask, base_exchange_rate,
                                 contract_size, value_per_pip, vol24h_base, vol24h_quote)

        # update trades profit/loss for the related market id
        market = self.market(market_id)

        # market must be valid
        if market is None:
            return

        with self._mutex:
            try:
                # update profit/loss (informational) for each asset
                for k, asset in self._assets.items():
                    if asset.symbol == market.base and asset.quote == market.quote:
                        asset.update_profit_loss(market)

            except Exception as e:
                error_logger.error(repr(e))
                traceback_logger.error(traceback.format_exc())

    #
    # assets
    #

    @Trader.mutexed
    def on_asset_updated(self, asset_name: str, locked: float, free: float):
        """
        @todo update as kraken trader
        """
        asset = self.__get_or_add_asset(asset_name)
        if asset is not None:
            # significant deviation...
            if abs((locked+free)-asset.quantity) / ((locked+free) or 1.0) >= 0.001:
                logger.debug("%s deviation of computed quantity for %s from %s but must be %s" % (
                    self._name, asset_name, asset.quantity, (locked+free)))

            asset.set_quantity(locked, free)

            if asset.quote and asset.symbol != asset.quote:
                preferred_market = self._markets.get(asset.symbol+asset.quote)
                if preferred_market:
                    asset.update_profit_loss(preferred_market)

            # store in database with the last update quantity
            Database.inst().store_asset((
                self._name, self.account.name,
                asset_name, str(asset.last_trade_id), int(asset.last_update_time*1000.0),
                asset.quantity, asset.price, asset.quote))

        # call base for stream
        super().on_asset_updated(asset_name, locked, free)

    def __update_asset(self, order_type, asset, market, trade_id, exec_price, trade_qty, buy_or_sell, timestamp):
        """
        @note Taking last quote price might be at the timestamp of the trade, but it cost an API call
        credit and plus a delay. Then assume the last tick price is enough precise.

        @todo fix it
        """
        curr_price = asset.price
        curr_qty = asset.quantity

        base_precision = market.base_precision if market else 8
        quote_price = 1.0

        if market and asset.quote and asset.symbol != self._account.currency and market.quote != self._account.currency:
            # asset is not USDT, quote is not USDT, get its price at trade time
            if self._watcher.has_instrument(market.quote+self._account.currency):
                # direct (potential REST call)
                quote_price = self.history_price(market.quote+self._account.currency, timestamp)
            elif self._watcher.has_instrument(self._account.currency+market.quote):
                # indirect (potential REST call)
                history_price = self.history_price(self._account.currency + market.quote, timestamp)
                if history_price > 0.0:
                    quote_price = 1.0 / history_price
            else:
                quote_price = 0.0  # might not occur
                logger.warning("Unsupported quote asset " + market.quote)

        price = exec_price * quote_price

        # in USDT
        if curr_qty+trade_qty > 0.0:
            if buy_or_sell:
                # adjust price when buying
                curr_price = ((price*trade_qty) + (curr_price*curr_qty)) / (curr_qty+trade_qty)
                curr_price = max(0.0, round(curr_price, base_precision))

            curr_qty += trade_qty if buy_or_sell else -trade_qty
            curr_qty = max(0.0, round(curr_qty, base_precision))
        else:
            curr_price = 0.0
            curr_qty = 0

        if not curr_price and trade_qty > 0:
            if asset.symbol == self._account.currency:
                curr_price = 1.0
            else:
                # base price in USDT at trade time
                if self._watcher.has_instrument(asset.symbol+self._account.currency):
                    # direct
                    curr_price = self.history_price(asset.symbol+self._account.currency, timestamp)
                elif self._watcher.has_instrument(self._account.currency+asset.symbol):
                    # indirect
                    curr_price = 1.0 / self.history_price(self._account.currency+asset.symbol, timestamp)
                else:
                    curr_price = 0.0  # might not occur
                    logger.warning("Unsupported asset " + asset.symbol)

        #
        # adjust asset
        #

        # price
        asset.update_price(timestamp, trade_id or asset.last_trade_id, curr_price)

        # and qty
        if buy_or_sell:
            # more free
            asset.set_quantity(asset.locked, asset.free+trade_qty)
        else:
            if order_type in (Order.ORDER_MARKET, Order.ORDER_STOP, Order.ORDER_TAKE_PROFIT):
                # taker, less free
                asset.set_quantity(asset.locked, max(0.0, asset.free-trade_qty))
            else:
                # market, less locked
                asset.set_quantity(max(0.0, asset.locked-trade_qty), asset.free)

        if asset.quote and asset.symbol != asset.quote:
            preferred_market = self._markets.get(asset.symbol+asset.quote)
            if preferred_market:
                asset.update_profit_loss(preferred_market)

        # store in database with the last computed entry price
        Database.inst().store_asset((
            self._name, self.account.name,
            asset.symbol, str(asset.last_trade_id), int(asset.last_update_time*1000.0),
            asset.quantity, asset.price, asset.quote))

    #
    # order slots
    #

    @Trader.mutexed
    def on_order_traded(self, market_id: str, order_data: dict, ref_order_id: str):
        """
        Order update, trade order in that case, is always successes by an asset update signal.
        Binance order modification is not possible, need cancel and recreate.

        @note Consume 1 API credit to get the asset quote price at the time of the trade.
        """
        market = self._markets.get(market_id)
        if market is None:
            # not interested in this market
            return

        order = self._orders.get(order_data['id'])
        if order is None:
            # not found (might not occur)
            order = Order(self, order_data['symbol'])
            order.set_order_id(order_data['id'])

            # its might be the creation timestamp, but it will be the trade execution
            order.created_time = order_data['timestamp']

            order.direction = order_data['direction']
            order.order_type = order_data['type']
            order.time_in_force = order_data['time-in-force']

            order.quantity = order_data['quantity']

            order.price = order_data.get('price')
            order.stop_price = order_data.get('stop-price')

            self._orders[order_data['id']] = order

        order.executed += order_data['filled']

        if order_data.get('fully-filled', False):
            # fully filled, mean to delete
            if order_data['id'] in self._orders:
                del self._orders[order_data['id']]

        #
        # compute avg price and new qty
        #

        if order_data['trade-id']:
            # need assets and market info
            base_asset = self.__get_or_add_asset(market.base)
            quote_asset = self.__get_or_add_asset(market.quote)

            quote_market = None

            # same asset used for commission
            buy_or_sell = order_data['direction'] == Order.LONG

            # base details in the trade order
            base_trade_qty = order_data['filled']
            base_exec_price = order_data['exec-price']

            # price of the quote asset expressed in preferred quote at time of the trade (need a REST call)
            quote_trade_qty = order_data['quote-transacted']  # or base_trade_qty * base_exec_price
            quote_exec_price = 1.0

            if quote_asset.quote and quote_asset.symbol != quote_asset.quote:
                # quote price to be fetched
                if self._watcher.has_instrument(quote_asset.symbol+quote_asset.quote):
                    # direct, and get the related market
                    quote_market = self._markets.get(quote_asset.symbol+quote_asset.quote)                    
                    quote_exec_price = self.history_price(quote_asset.symbol+quote_asset.quote,
                                                          order_data['timestamp'])

                elif self._watcher.has_instrument(quote_asset.quote+quote_asset.symbol):
                    # indirect, but cannot have the market
                    quote_exec_price = 1.0 / self.history_price(quote_asset.quote+quote_asset.symbol,
                                                                order_data['timestamp'])

            # base asset
            self.__update_asset(order.order_type, base_asset, market, order_data['trade-id'], base_exec_price,
                                base_trade_qty, buy_or_sell, order_data['timestamp'])

            # quote asset
            self.__update_asset(order.order_type, quote_asset, quote_market, None, quote_exec_price,
                                quote_trade_qty, not buy_or_sell, order_data['timestamp'])

            # commission asset
            if order_data['commission-asset'] == base_asset.symbol:
                self.__update_asset(Order.ORDER_MARKET, base_asset, market, None, base_exec_price,
                                    order_data['commission-amount'], False, order_data['timestamp'])
            else:
                commission_asset = self.__get_or_add_asset(order_data['commission-asset'])
                commission_asset_market = None
                quote_exec_price = 1.0

                if commission_asset.quote and commission_asset.symbol != commission_asset.quote:
                    # commission asset price to be fetched
                    if self._watcher.has_instrument(commission_asset.symbol+commission_asset.quote):
                        # direct, and get the related market
                        commission_asset_market = self.market(commission_asset.symbol+commission_asset.quote)
                        quote_exec_price = commission_asset_market.price

                    elif self._watcher.has_instrument(commission_asset.quote+commission_asset.symbol):
                        # indirect, but cannot have the market
                        quote_exec_price = 1.0 / self.history_price(commission_asset.quote+commission_asset.symbol,
                                                                    order_data['timestamp'])

                self.__update_asset(Order.ORDER_MARKET, commission_asset, commission_asset_market, None,
                                    quote_exec_price, order_data['commission-amount'], False, order_data['timestamp'])

    def on_order_deleted(self, market_id: str, order_id: str, ref_order_id: str):
        with self._mutex:
            if order_id in self._orders:
                del self._orders[order_id]

    def on_order_canceled(self, market_id: str, order_id: str, ref_order_id: str):
        with self._mutex:
            if order_id in self._orders:
                del self._orders[order_id]

    #
    # misc
    #

    def asset_quantities(self) -> List[Tuple[str, float, float]]:
        """
        Returns a list of triplet with (symbol, locked qty, free qty) for any non-empty balance of assets.
        """
        with self._mutex:
            balances = [(k, asset.locked, asset.free) for k, asset in self._assets.items()]
            return balances
