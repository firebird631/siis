# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Active trades view.

import traceback

from view.tableview import TableView
from terminal.terminal import Terminal

from strategy.helpers.activetradetable import trades_stats_table

import logging
error_logger = logging.getLogger('siis.view.trade')
traceback_logger = logging.getLogger('siis.traceback.view.trade')


class TradeView(TableView):
    """
    Active trade view.
    """

    def __init__(self, service, strategy_service):
        super().__init__("strategy", service)

        self._strategy_service = strategy_service
        self._ordering = True  # initially most recent first

    def refresh(self):
        if not self._strategy_service:
            return

        strategy = self._strategy_service.strategy()
        if strategy:
            num = 0
            num_actives_trades = 0

            try:
                columns, table, total_size, num_actives_trades = trades_stats_table(
                    strategy, *self.table_format(), quantities=True, percents=self._percent,
                    group=self._group, ordering=self._ordering, datetime_format=self._datetime_format,
                    pl_pip=self._opt1)

                self.table(columns, table, total_size)
                num = total_size[1]
            except Exception as e:
                error_logger.error(str(e))
                traceback_logger.error(traceback.format_exc())

            self.set_title("Active trades (%i/%i)%s for strategy %s - %s" % (
                num_actives_trades, num, self.display_mode_str(), strategy.name, strategy.identifier))
        else:
            self.set_title("Active trades - No configured strategy")
