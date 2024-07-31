# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Perf trade view.
from terminal.terminal import Terminal
from view.tableview import TableView

from strategy.helpers.aggtradetable import agg_trades_stats_table

import logging
error_logger = logging.getLogger('siis.view.aggtrade')


class AggTradeView(TableView):
    """
    Perf trade view.
    """

    def __init__(self, service, strategy_service):
        super().__init__("perf", service)

        self._strategy_service = strategy_service

        self._quantities = True  # display quantity related columns
        self._stats = False  # display statistics related columns

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

    def refresh(self):
        if not self._strategy_service:
            return

        strategy = self._strategy_service.strategy()
        if strategy:
            num = 0

            try:
                columns, table, total_size = agg_trades_stats_table(
                    strategy, *self.table_format(), summ=True,
                    quantities=self._quantities, stats=self._stats,
                    group=self._group, ordering=self._ordering)

                self.table(columns, table, total_size)
                num = total_size[1]
            except Exception as e:
                error_logger.error(str(e))

            # display options
            display_opts = []
            if self._group:
                display_opts.append("Group")
            if self._ordering:
                display_opts.append("Desc.")
            else:
                display_opts.append("Asc.")
            if self._quantities:
                display_opts.append("Quantities")
            if self._stats:
                display_opts.append("Stats")

            self.set_title("[Performance %i] %s::%s <%s>" % (
                num, strategy.name, strategy.identifier, " - ".join(display_opts)))
        else:
            self.set_title("[Performances 0] No configured strategy <>")
