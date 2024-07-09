# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Perf trade view.

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

    def refresh(self):
        if not self._strategy_service:
            return

        strategy = self._strategy_service.strategy()
        if strategy:
            num = 0

            try:
                columns, table, total_size = agg_trades_stats_table(
                    strategy, *self.table_format(), summ=True, group=self._group, ordering=self._ordering)

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

            self.set_title("[Performance %i] %s::%s <%s>" % (
                num, strategy.name, strategy.identifier, " - ".join(display_opts)))
        else:
            self.set_title("[Performances 0] No configured strategy <>")
