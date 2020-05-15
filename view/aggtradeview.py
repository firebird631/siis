# @date 2019-06-28
# @author Frederic SCHERMA
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

    def refresh(self):
        if not self._strategy_service:
            return

        appliances = self._strategy_service.get_appliances()
        if len(appliances) > 0 and -1 < self._item < len(appliances):
            appliance = appliances[self._item]
            num = 0

            try:
                columns, table, total_size = agg_trades_stats_table(appliance, *self.table_format(), summ=True)

                self.table(columns, table, total_size)
                num = total_size[1]
            except Exception as e:
                error_logger.error(str(e))

            self.set_title("Perf per market trades (%i) for strategy %s - %s" % (num, appliance.name, appliance.identifier))
        else:
            self.set_title("Perf per market trades - No configured strategy")
