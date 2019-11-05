# @date 2019-06-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# View manager service.

import collections
import threading
import os
import time
import logging
import traceback

from datetime import datetime, timedelta

from trader.position import Position

from common.baseservice import BaseService
from common.signal import Signal

from terminal.terminal import Terminal

from common.utils import timeframe_to_str

from view.view import View
from view.viewexception import ViewServiceException


class ViewService(BaseService):
    """
    View manager service.
    It support the refreh of actives views, receive signal from others services.
    @todo
    """

    def __init__(self, options):
        super().__init__("view")

        self.strategy_service = None
        self.trader_service = None
        self.watcher_service = None

        self._mutex = threading.RLock()  # reentrant locker
        self._signals = collections.deque()  # filtered received signals

        self._views = {}

    def lock(self, blocking=True, timeout=-1):
        self._mutex.acquire(blocking, timeout)

    def unlock(self):
        self._mutex.release()

    def init(self):
        self.setup_default()

    def terminate(self):
        pass
 
    @property
    def name(self):
        return "view"

    def ping(self, timeout):
        pass

    def watchdog(self, watchdog_service, timeout):
        pass

    def set_active_view(self, view_id):
        Terminal.inst().switch_view(view_id)

    def on_key_pressed(self, key):
        # progagate to active view
        if key:
            vt = Terminal.inst().active_content()
            if vt:
                view = self._views.get(vt.name)
                if view:
                    self.view.on_key_pressed(key)

    def receiver(self, signal):
        pass

    def sync(self):
        vt = Terminal.inst().active_content()
        if vt:
            view = self._views.get(vt.name)
            if view:
                self.view.refreh()
    
        # @todo remove it
        self.refresh_strategies_stats()
        self.refresh_traders_stats()

    def add_view(self, view):
        if not view:
            return

        with self._mutex:
            if view in self._views:
                raise ViewServiceException("View %s already registred" % view.id)

            view.create()
            self._views[view.id] = view

    def remove_view(self, view_id):
        with self._mutex:
            if view_id in self._views:
                view = self._views[view_id]
                if view:
                    view.destroy()

                del self._views[view_id]

    def toggle_percents(self):
        with self._mutex:
            for k, view in self._views.items():
                view.toggle_percents()

    def setup_default(self):
        pass
        # view = TableView("")
        # self.add_view(view)

    #
    # view @deprecated must uses the new views handlers
    #

    def refresh_strategies_stats(self):
        # @todo must be in distinct View
        pass
    #     if not self.strategy_service:
    #         return

    #     if not (Terminal.inst().is_active('strategy') or Terminal.inst().is_active('perf') or Terminal.inst().is_active('stats')):
    #         return

    #     appliances = appl = self.strategy_service.get_appliances()
    #     if self._displayed_strategy >= len(appliances):
    #         self._displayed_strategy = 0

    #     appl = None

    #     if not appliances:
    #         return

    #     appl = self.strategy_service.get_appliances()[self._displayed_strategy]

    #     if not appl:
    #         return

    #     if Terminal.inst().is_active('strategy') or Terminal.inst().is_active('perf'):
    #         # strategy view
    #         if Terminal.inst().is_active('strategy'):
    #             num = 0

    #             try:                
    #                 columns, table, total_size = appl.trades_stats_table(*Terminal.inst().active_content().format(),
    #                     quantities=True, percents=self._display_percents)

    #                 Terminal.inst().table(columns, table, total_size, view='strategy')
    #                 num = total_size[1]
    #             except Exception as e:
    #                 error_logger.error(repr(e))                    

    #             Terminal.inst().info("Active trades (%i) for strategy %s - %s" % (num, appl.name, appl.identifier), view='strategy-head')

    #         # perf view
    #         if Terminal.inst().is_active('perf'):
    #             num = 0

    #             try:
    #                 columns, table, total_size = appl.agg_trades_stats_table(*Terminal.inst().active_content().format(), summ=True)
    #                 Terminal.inst().table(columns, table, total_size, view='perf')
    #                 num = total_size[1]
    #             except Exception as e:
    #                 error_logger.error(repr(e))

    #             Terminal.inst().info("Perf per market trades (%i) for strategy %s - %s" % (num, appl.name, appl.identifier), view='perf-head')

    #     # stats view
    #     if Terminal.inst().is_active('stats'):
    #         num = 0

    #         try:
    #             columns, table, total_size = appl.closed_trades_stats_table(*Terminal.inst().active_content().format(),
    #                 quantities=True, percents=self._display_percents)

    #             Terminal.inst().table(columns, table, total_size, view='stats')
    #             num = total_size[1]
    #         except Exception as e:
    #                 error_logger.error(repr(e))

    #         Terminal.inst().info("Trade history (%i) for strategy %s - %s" % (num, appl.name, appl.identifier), view='stats-head')

    def refresh_traders_stats(self):
        pass
    #     if not self.trader_service:
    #         return

    #     # account view
    #     if Terminal.inst().is_active('account'):
    #         traders = self.trader_service.get_traders()

    #         if len(traders) > 0:
    #             trader = next(iter(traders))
    #             num = 0

    #             try:
    #                 columns, table, total_size = trader.account_table(*Terminal.inst().active_content().format())
    #                 Terminal.inst().table(columns, table, total_size, view='account')
    #                 num = total_size[1]
    #             except:
    #                 pass

    #             Terminal.inst().info("Account details (%i) for trader %s - %s" % (num, trader.name, trader.account.name), view='account-head')

    #     # tickers view
    #     if Terminal.inst().is_active('ticker'):
    #         traders = self.trader_service.get_traders()

    #         if len(traders) > 0:
    #             trader = next(iter(traders))
    #             num = 0

    #             try:
    #                 columns, table, total_size = trader.markets_tickers_table(*Terminal.inst().active_content().format(), prev_timestamp=self._last_strategy_update)
    #                 Terminal.inst().table(columns, table, total_size, view='ticker')
    #                 num = total_size[1]
    #             except:
    #                 pass

    #             Terminal.inst().info("Tickers list (%i) for tader %s on account %s" % (num, trader.name, trader.account.name), view='ticker-head')

    #     # markets view
    #     if Terminal.inst().is_active('market'):
    #         traders = self.trader_service.get_traders()

    #         if len(traders) > 0:
    #             trader = next(iter(traders))
    #             num = 0

    #             try:
    #                 columns, table, total_size = trader.markets_table(*Terminal.inst().active_content().format())
    #                 Terminal.inst().table(columns, table, total_size, view='market')
    #                 num = total_size[1]
    #             except Exception as e:
    #                 error_logger.error(repr(e))

    #             Terminal.inst().info("Market list (%i) trader %s on account %s" % (num, trader.name, trader.account.name), view='market-head')

    #     # assets view
    #     if Terminal.inst().is_active('asset'):
    #         traders = self.trader_service.get_traders()

    #         if len(traders) > 0:
    #             trader = next(iter(traders))
    #             num = 0

    #             try:
    #                 columns, table, total_size = trader.assets_table(*Terminal.inst().active_content().format())
    #                 Terminal.inst().table(columns, table, total_size, view='asset')
    #                 num = total_size[1]
    #             except Exception as e:
    #                 error_logger.error(repr(e))

    #             Terminal.inst().info("Asset list (%i) trader %s on account %s" % (num, trader.name, trader.account.name), view='asset-head')

    #     # position view
    #     if Terminal.inst().is_active('position'):
    #         traders = self.trader_service.get_traders()

    #         if len(traders) > 0:
    #             trader = next(iter(traders))
    #             num = 0

    #             try:
    #                 columns, table, total_size = trader.positions_stats_table(*Terminal.inst().active_content().format(), quantities=True)
    #                 Terminal.inst().table(columns, table, total_size, view='position')
    #                 num = total_size[1]
    #             except Exception as e:
    #                 error_logger.error(repr(e))

    #             Terminal.inst().info("Position list (%i) trader %s on account %s" % (num, trader.name, trader.account.name), view='position-head')

    #     # order view
    #     if Terminal.inst().is_active('order'):
    #         traders = self.trader_service.get_traders()

    #         if len(traders) > 0:
    #             trader = next(iter(traders))
    #             num = 0

    #             try:
    #                 columns, table, total_size = trader.active_orders_table(*Terminal.inst().active_content().format(), quantities=True)
    #                 Terminal.inst().table(columns, table, total_size, view='order')
    #                 num = total_size[1]
    #             except Exception as e:
    #                 error_logger.error(repr(e))

    #             Terminal.inst().info("Order list (%i) trader %s on account %s" % (num, trader.name, trader.account.name), view='order-head')

    #     self._last_strategy_update = self.strategy_service.timestamp
