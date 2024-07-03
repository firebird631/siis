# @date 2024-07-03
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# terminal statistic commands and registration

from strategy.helpers.closedtradedataset import get_closed_trades
from terminal.command import Command

from terminal.terminal import Terminal
from terminal.plot import plot

import numpy as np


class DrawCumulativePNLCommand(Command):
    SUMMARY = "to unset an alias of command"

    def __init__(self, commands_handler, strategy_service):
        super().__init__('drawcumulativepnl', None)

        self._commands_handler = commands_handler

        self._strategy_service = strategy_service

    def execute(self, args):
        if len(args) > 1:
            return False, "Only market symbol parameters is supported"

        strategy = self._strategy_service.strategy()

        if len(args) == 1:
            market_id = args[0]

            instrument = strategy.find_instrument(market_id)
            market_id = instrument.market_id if instrument else None
        else:
            market_id = None

        closed_trades = get_closed_trades(self._strategy_service.strategy())

        cum_pnl = 0.0
        x_serie = []
        y_serie = []

        n = 1

        if market_id:
            # filter for only one market
            closed_trades = [x for x in closed_trades if x['market-id'] == market_id]

        # sort by exit datetime to compute cumulative PNL
        closed_trades.sort(key=lambda x: str(x['stats']['last-realized-exit-datetime']))

        max_width = Terminal.inst().view("content").width - 3
        max_height = Terminal.inst().view("content").height - 3

        for t in closed_trades:
            cum_pnl += t['profit-loss-pct']
            x_serie.append(cum_pnl)
            y_serie.append(n)

            n += 1

        if len(x_serie) > max_width:
            x_serie = np.reshape(x_serie, max_width).mean(axis=1)

        content = plot(x_serie, {"height": max_height, "format": "{:5.2f}"})
        Terminal.inst().message(content, view="content")

        return True, None

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, strategy.symbols_ids(), args, tab_pos, direction)

        return args, 0


def register_statistic_commands(commands_handler, strategy_service):
    commands_handler.register(DrawCumulativePNLCommand(commands_handler, strategy_service))
