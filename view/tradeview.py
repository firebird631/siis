# @date 2019-06-28
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Active trades view.

from view.tableview import TableView
from terminal.terminal import Terminal

from strategy.helpers.activetradetable import trades_stats_table

import logging
error_logger = logging.getLogger('siis.view.trade')


class TradeView(TableView):
    """
    Active trade view.
    """

    def __init__(self, service, strategy_service):
        super().__init__("strategy", service)

        self._strategy_service = strategy_service
        self._ordering = True  # initially most recent first
        self._pl_pip = False   # P/L in percent or pip

    def on_key_pressed(self, key):
        super().on_key_pressed(key)

        if Terminal.inst().mode == Terminal.MODE_DEFAULT:
            if key == '*':
                # toggle percent or pip display
                self._pl_pip = not self._pl_pip

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
                    pl_pip=self._pl_pip)

                self.table(columns, table, total_size)
                num = total_size[1]
            except Exception as e:
                error_logger.error(str(e))

            self.set_title("Active trades (%i/%i)%s for strategy %s - %s" % (
                num_actives_trades, num, self.display_mode_str(), strategy.name, strategy.identifier))
        else:
            self.set_title("Active trades - No configured strategy")
