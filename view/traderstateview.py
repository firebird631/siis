# @date 2019-06-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# Trader state view.

import threading
import hashlib

from datetime import datetime

from common.utils import timeframe_to_str
from common.signal import Signal

from terminal.terminal import Terminal, Color
from terminal import charmap

from view.tableview import TableView

import logging
logger = logging.getLogger('siis.view.traderstate')
error_logger = logging.getLogger('siis.error.view.traderstate')


class TraderStateView(TableView):
    """
    Trader state view.
    Display a specific strategy trader for an instrument, in details,
    the differents globals states, and the per timeframes states and indicators.
    It depend of the specific implementation per strategy.
    """

    REFRESH_RATE = 60
    FAST_REFRESH_RATE = 10
    VERY_FAST_REFRESH_RATE = 1

    #into the title, appname/market last-bid/last-ofr/last-spread
    COLUMNS = ('Name', 'TF', charmap.ARROWUPDN)

    def __init__(self, service, strategy_service):
        super().__init__("traderstate", service)

        self._mutex = threading.RLock()
        self._strategy_service = strategy_service
        self._market_id = None
        self._signals_state = {}

        self._upd_freq = TraderStateView.REFRESH_RATE

        # listen to its service
        self.service.add_listener(self)

    def count_items(self):
        if not self._strategy_service:
            return 0

        return (self._strategy_service.get_traders())

    def on_key_pressed(self, key):
        super().on_key_pressed(key)

        if key == 'KEY_STAB' or key == 'KEY_BTAB':
            self.toggle_update_freq()
        elif key == 'KEY_LEFT':
            self.prev_instrument()
        elif key == 'KEY_RIGHT':
            self.next_instrument()

    def toggle_update_freq(self):
        if self._upd_freq == TraderStateView.REFRESH_RATE:
            self._upd_freq = TraderStateView.FAST_REFRESH_RATE
            Terminal.inst().action("Change to fast refresh rate", view="status")

        elif self._upd_freq == TraderStateView.FAST_REFRESH_RATE:
            self._upd_freq = TraderStateView.VERY_FAST_REFRESH_RATE
            Terminal.inst().action("Change to very-fast refresh rate", view="status")

        elif self._upd_freq == TraderStateView.VERY_FAST_REFRESH_RATE:
            self._upd_freq = TraderStateView.REFRESH_RATE
            Terminal.inst().action("Change to default refresh rate", view="status")

    def prev_instrument(self):
        if not self._strategy_service:
            return

        appliances = self._strategy_service.get_appliances()
        if len(appliances) > 0 and -1 < self._item < len(appliances):
            appliance = appliances[self._item]
            instruments_ids = appliance.instruments_ids()

            if not instruments_ids:
                with self._mutex:
                    self._market_id = None

                return

            if self._market_id is None:
                with self._mutex:
                    self._market_id = instruments_ids[0]

                return

            with self._mutex:
                index = instruments_ids.index(self._market_id)
                if index > 0:
                    self._market_id = instruments_ids[index-1]
                else:
                    self._market_id = instruments_ids[-1]

    def next_instrument(self):
        if not self._strategy_service:
            return

        appliances = self._strategy_service.get_appliances()
        if len(appliances) > 0 and -1 < self._item < len(appliances):
            appliance = appliances[self._item]
            instruments_ids = appliance.instruments_ids()

            if not instruments_ids:
                with self._mutex:
                    self._market_id = None

                return

            if self._market_id is None:
                with self._mutex:
                    self._market_id = instruments_ids[0]
                
                return

            with self._mutex:
                index = instruments_ids.index(self._market_id)
                if index < len(instruments_ids)-1:
                    self._market_id = instruments_ids[index+1]
                else:
                    self._market_id = instruments_ids[0]

    def receiver(self, signal):
        if not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_ALERT:
                with self._mutex:
                    # force refresh on signal
                    self._refresh = 0.0

    def trader_state_table(self, appliance, style='', offset=None, limit=None, col_ofs=None):
        data = []

        states = []
        # states = self._signals_state.get(appliance.identifier, [])
        # columns, table, total_size = trader_state_table(appliance, *self.table_format(), summ=True)
        total_size = (len(TraderStateView.COLUMNS), len(states))

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(states)

        limit = offset + limit

        states = states[offset:limit]

        for state in states:
            pass
        #     row = (
        #     )

        #     data.append(row[col_ofs:])

        return TraderStateView.COLUMNS[col_ofs:], data, total_size

    def refresh(self):
        if not self._strategy_service:
            return

        appliances = self._strategy_service.get_appliances()
        if len(appliances) > 0 and -1 < self._item < len(appliances):
            if self._market_id:
                appliance = appliances[self._item]
                num = 0

                with self._mutex:
                    try:
                        columns, table, total_size = self.trader_state_table(appliance, *self.table_format())
                        self.table(columns, table, total_size)
                        num = total_size[1]
                    except Exception as e:
                        import traceback
                        error_logger.error(str(traceback.format_exc()))
                        error_logger.error(str(e))

                # @todo price...
                self.set_title("Trader state for strategy %s - %s on %s" % (appliance.name, appliance.identifier, self._market_id))
            else:
                self.set_title("Trader state - No selected market")
        else:
            self.set_title("Trader state - No configured strategy")
