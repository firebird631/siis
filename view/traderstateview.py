# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Trader state view.

import time
import threading
import hashlib

from datetime import datetime

from common.utils import timeframe_to_str
from common.signal import Signal

from terminal.terminal import Terminal, Color
from terminal import charmap

from view.tableview import TableView

from strategy.helpers.traderstatedataset import get_strategy_trader_state


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

    def __init__(self, service, strategy_service):
        super().__init__("traderstate", service)

        self._mutex = threading.RLock()
        self._strategy_service = strategy_service
        self._market_id = None
        self._signals_state = {}

        self._upd_freq = TraderStateView.REFRESH_RATE
        self._report_mode = 0

        self._reported_activity = False
        self._reported_bootstraping = False
        self._reported_ready = False
        self._reported_affinity = 5

        # listen to its service
        self.service.add_listener(self)

    def count_items(self):
        if not self._strategy_service:
            return 0

        return 1

    def on_key_pressed(self, key):
        super().on_key_pressed(key)

        if (key == 'KEY_STAB' or key == 'KEY_BTAB') and Terminal.inst().mode == Terminal.MODE_DEFAULT:
            self.toggle_update_freq()
        elif key == 'KEY_LEFT':
            self.prev_instrument()
        elif key == 'KEY_RIGHT':
            self.next_instrument()

    def on_char(self, char):
        super().on_char(char)

        if char == '+':
            with self._mutex:
                self._report_mode += 1
                self._refresh = 0.0
        elif char == '-':
            with self._mutex:
                self._report_mode = max(0, self._report_mode - 1)
                self._refresh = 0.0

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

    def need_refresh(self):
        if self._refresh < 0:
            return False

        return time.time() - self._refresh >= self._upd_freq

    def prev_instrument(self):
        if not self._strategy_service:
            return

        strategy = self._strategy_service.strategy()
        if strategy:
            instruments_ids = strategy.instruments_ids()

            if not instruments_ids:
                with self._mutex:
                    self._market_id = None
                    self._refresh = 0.0

                return

            if self._market_id is None:
                with self._mutex:
                    self._market_id = instruments_ids[0]
                    self._refresh = 0.0

                return

            with self._mutex:
                index = instruments_ids.index(self._market_id)
                if index > 0:
                    self._market_id = instruments_ids[index-1]
                else:
                    self._market_id = instruments_ids[-1]

                self._refresh = 0.0

    def next_instrument(self):
        if not self._strategy_service:
            return

        strategy = self._strategy_service.strategy()
        if strategy:
            instruments_ids = strategy.instruments_ids()

            if not instruments_ids:
                with self._mutex:
                    self._market_id = None
                    self._refresh = 0.0

                return

            if self._market_id is None:
                with self._mutex:
                    self._market_id = instruments_ids[0]
                    self._refresh = 0.0
                
                return

            with self._mutex:
                index = instruments_ids.index(self._market_id)
                if index < len(instruments_ids)-1:
                    self._market_id = instruments_ids[index+1]
                else:
                    self._market_id = instruments_ids[0]

                self._refresh = 0.0

    def receiver(self, signal):
        if not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if Signal.SIGNAL_STRATEGY_SIGNAL_ENTRY <= signal.signal_type <= Signal.SIGNAL_STRATEGY_ALERT:
                with self._mutex:
                    # force refresh on signal
                    self._refresh = 0.0

    def trader_state_table(self, strategy, style='', offset=None, limit=None, col_ofs=None):
        market_id = None
        report_mode = 0
        data = []

        with self._mutex:
            market_id = self._market_id
            report_mode = self._report_mode

        if market_id:
            strategy_trader_state = get_strategy_trader_state(strategy, market_id, report_mode)
        else:
            return [], [], (0, 0)

        if report_mode >= strategy_trader_state.get('num-modes', 1):
            with self._mutex:
                # refreh with mode
                self._report_mode = strategy_trader_state.get('num-modes', 1) - 1
                strategy_trader_state = get_strategy_trader_state(strategy, market_id, report_mode)

        members = strategy_trader_state.get('members', [])
        states = []
        columns = [m[1] for m in members]
        states = strategy_trader_state.get('data', [])
        total_size = (len(columns), len(states))

        for i, col in enumerate(members):
            if col[0] == "direction":
                columns[i] = charmap.ARROWUPDN
            elif col[1] == "timeframe":
                columns[i] = "TF"

        # for title
        self._reported_activity = strategy_trader_state.get('activity', False)
        self._reported_bootstraping = strategy_trader_state.get('bootstraping', False)
        self._reported_ready = strategy_trader_state.get('ready', False)
        self._reported_affinity = strategy_trader_state.get('affinity', 5)

        if offset is None:
            offset = 0

        if limit is None:
            limit = len(states)

        limit = offset + limit

        states = states[offset:limit]

        for state in states:
            row = list(state)

            for i, d in enumerate(row):
                if members[i][0] == "direction":
                    if d == "L" or str(d) == "1":
                        row[i] = Color.colorize(charmap.ARROWUP, Color.GREEN)
                    elif d == "S" or str(d) == "-1":
                        row[i] = Color.colorize(charmap.ARROWDN, Color.RED)

                elif members[i][0] == "datetime":
                    row[i] = datetime.fromtimestamp(d).strftime(self._datetime_format) if (type(d) is float and d > 0) else ""

            data.append(row[col_ofs:])

        return columns[col_ofs:], data, total_size

    def refresh(self):
        if not self._strategy_service:
            return

        strategy = self._strategy_service.strategy()
        if strategy:
            if self._market_id:
                num = 0

                market_id = ""
                report_mode = 0

                reported_activity = False
                reported_bootstraping = False

                with self._mutex:
                    market_id = self._market_id
                    report_mode = self._report_mode
                    
                    reported_activity = self._reported_activity
                    reported_bootstraping = self._reported_bootstraping
                    reported_ready = self._reported_ready
                    reported_affinity = self._reported_affinity

                    try:
                        columns, table, total_size = self.trader_state_table(strategy, *self.table_format())
                        self.table(columns, table, total_size)
                        num = total_size[1]
                    except Exception as e:
                        import traceback
                        error_logger.error(str(traceback.format_exc()))
                        error_logger.error(str(e))

                state = " - ".join((
                    "active" if reported_activity else "disabled",
                    ("ready" if reported_ready else "pending") + ("(%s)" % reported_affinity),
                    "bootstraping" if reported_bootstraping else "computing"))

                self.set_title("Trader state for strategy %s - %s on %s - mode %s - %s" % (strategy.name, strategy.identifier, market_id, report_mode, state))
            else:
                self.set_title("Trader state - No selected market")
        else:
            self.set_title("Trader state - No configured strategy")
