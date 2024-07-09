# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Historical trades view.

import traceback

from terminal.terminal import Terminal
from view.tableview import TableView

from common.signal import Signal
from strategy.helpers.closedtradetable import closed_trades_stats_table

import logging
error_logger = logging.getLogger('siis.error.view.tradehistory')
traceback_logger = logging.getLogger('siis.traceback.view.tradehistory')


class TradeHistoryView(TableView):
    """
    Historical trade view.
    # @todo Could use local table and add row from signal data but need more complete signal data
    """

    REFRESH_RATE = 60.0

    def __init__(self, service, strategy_service):
        super().__init__("stats", service)

        self._strategy_service = strategy_service
        self._ordering = True  # initially most recent first

        self._quantities = True  # display quantity related columns
        self._stats = False  # display statistics related columns

        # listen to its service
        self.service.add_listener(self)

    def on_key_pressed(self, key):
        super().on_key_pressed(key)

        if (key == 'KEY_STAB' or key == 'KEY_BTAB') and Terminal.inst().mode == Terminal.MODE_DEFAULT:
            # make a loop over the two booleans
            if self._stats and self._quantities:
                self._quantities = False
                self._stats = False
            elif not self._stats and not self._quantities:
                self._quantities = True
                self._stats = False
            elif not self._stats and self._quantities:
                self._quantities = False
                self._stats = True
            elif self._stats and not self._quantities:
                self._quantities = True
                self._stats = True

            # force to refresh
            self._refresh = 0.0

    def receiver(self, signal):
        if not signal:
            return

        if signal.source == Signal.SOURCE_STRATEGY:
            if signal.signal_type == Signal.SIGNAL_STRATEGY_TRADE_EXIT:
                with self._mutex:
                    if "exit" in signal.data.get('way'):
                        self._refresh = 0.0

    def refresh(self):
        if not self._strategy_service:
            return

        strategy = self._strategy_service.strategy()
        if strategy:
            num = 0

            try:
                columns, table, total_size = closed_trades_stats_table(
                    strategy, *self.table_format(),
                    quantities=self._quantities, stats=self._stats, percents=self._percent, pips=self._opt1,
                    group=self._group, ordering=self._ordering, datetime_format=self._datetime_format)

                self.table(columns, table, total_size)
                num = total_size[1]
            except Exception as e:
                error_logger.error(str(e))
                traceback_logger.error(traceback.format_exc())

            # display options
            display_opts = []
            if self._group:
                display_opts.append("Group")
            if self._ordering:
                display_opts.append("Desc.")
            else:
                display_opts.append("Asc.")
            if self._opt1:
                display_opts.append("Pips")
            if self._percent:
                display_opts.append("%")
            if self._quantities:
                display_opts.append("Quantities")
            if self._stats:
                display_opts.append("Stats")

            self.set_title("[Closed trades %i] %s::%s <%s>" % (
                num, strategy.name, strategy.identifier, " - ".join(display_opts)))
        else:
            self.set_title("[Closed Trades 0] No configured strategy <>")
