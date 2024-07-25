# @date 2024-07-03
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# terminal statistic commands and registration

from strategy.helpers.closedtradedataset import get_closed_trades
from strategy.indicator.utils import down_sample, MM_n
from strategy.learning.trainer import log_summary
from terminal.command import Command

from terminal.terminal import Terminal, Color
from terminal.plot import plot

from talib import STDDEV as ta_STDDEV, SMA as ta_SMA, TRANGE as ta_TRANGE
import numpy as np

import logging

error_logger = logging.getLogger('siis.app.statisticcommands')


class DrawStatsCommand(Command):
    """
    Display in CLI some statistics plots.
    @todo cumulative pnl might be computed using trade notional quantity and average by total notional quantity
        to make the difference between strategy having trades of different quantities
    @todo add an option to display like as the log_summary of the strategy
    """

    SUMMARY = "to display a CLI chart of a statistic"
    HELP = (
        "param1: <market-id> for strategy only (optional)",
        "paramN: One or many of [cum-cli|mfe|mae|etd|eef|xef|tef]",
    )

    CHARTS = ("cum-pnl",
              "pnl", "mfe", "mae", "etd", "eef", "xef", "tef",
              "avg-pnl", "avg-mfe", "avg-mae", "avg-etd", "avg-eef", "avg-xef", "avg-tef",
              "std-pnl", "std-mfe", "std-mae", "std-etd", "std-eef", "std-xef", "std-tef")

    def __init__(self, commands_handler, strategy_service):
        super().__init__('draw-stat', None)

        self._commands_handler = commands_handler

        self._strategy_service = strategy_service

    def execute(self, args):
        if len(args) == 0:
            return False, "Need at least a chart"

        market_id = None
        arg_offset = 0

        if len(args) >= 1:
            # specific market
            strategy = self._strategy_service.strategy()
            if strategy:
                instrument = strategy.find_instrument(args[0])
                if instrument:
                    market_id = instrument.market_id
                    arg_offset += 1

        for arg in args[arg_offset:]:
            if arg not in DrawStatsCommand.CHARTS:
                return False, "Invalid chart name %s" % arg

        closed_trades = get_closed_trades(self._strategy_service.strategy())
        if not closed_trades:
            return False, "No samples to draw"

        x_series = []

        if market_id:
            # filter for only one market
            closed_trades = [x for x in closed_trades if x['market-id'] == market_id]

        # time or trade number
        colors = []
        # y_serie = [x['stats']['last-realized-exit-datetime'] for x in closed_trades]
        # y_serie = list(range(1, len(closed_trades)+1))

        # sort by exit datetime to compute cumulative PNL
        closed_trades.sort(key=lambda x: str(x['stats']['last-realized-exit-datetime']))

        max_width = Terminal.inst().view("content").width - 3
        max_height = Terminal.inst().view("content").height - 4

        for series_name in set(args[arg_offset:]):
            avg = False
            stddev = False

            if series_name.startswith('avg-'):
                avg = True
            elif series_name.startswith('std-'):
                stddev = True

            if series_name == "cum-pnl":
                self.compute_cumulative_pnl(closed_trades, x_series, colors)

            elif series_name.endswith("pnl"):
                self.compute_pnl(closed_trades, x_series, colors, avg, stddev)

            elif series_name.endswith("mfe"):
                self.compute_mfe(closed_trades, x_series, colors, avg, stddev)

            elif series_name.endswith("mae"):
                self.compute_mae(closed_trades, x_series, colors, avg, stddev)

            elif series_name.endswith("etd"):
                self.compute_etd(closed_trades, x_series, colors, avg, stddev)

            elif series_name.endswith("tef"):
                self.compute_tef(closed_trades, x_series, colors, avg, stddev)

            elif series_name.endswith("eef"):
                self.compute_eef(closed_trades, x_series, colors, avg, stddev)

            elif series_name.endswith("xef"):
                self.compute_xef(closed_trades, x_series, colors, avg, stddev)

        # if ratio is more than 13 could issue
        for i in range(0, len(x_series)):
            if len(x_series[i]) > max_width:
                x_series[i] = list(down_sample(x_series[i], int(np.ceil(len(x_series[i])/max_width))))

        if x_series:
            # @todo depend if rate, pct or any price
            fmt = "{:6.2f}"

            content = plot(x_series if len(x_series) > 1 else x_series[0], {
                "height": max_height, "colors": colors})  # "format": fmt,
            Terminal.inst().message(content, view="content")

        return True, None

    def compute_pnl(self, closed_trades, x_series, colors, avg=False, stddev=False):
        series = []

        if len(closed_trades) < 1:
            return False, "Need at least 1 samples"

        if (avg or stddev) and len(closed_trades) < 8:
            return False, "Need at least 8 samples"

        for t in closed_trades:
            series.append(t['profit-loss-pct'])

        if avg:
            x_series.append(list(MM_n(7, series)))
            colors.append(Color.UTERM_COLORS_MAP[Color.WHITE])
        elif stddev:
            x, t, b = compute_std_dev(series)

            x_series.append(list(x))
            colors.append(Color.UTERM_COLORS_MAP[Color.WHITE])

            x_series.append(list(t))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])

            x_series.append(list(b))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])
        else:
            x_series.append(series)
            colors.append(Color.UTERM_COLORS_MAP[Color.WHITE])

    def compute_cumulative_pnl(self, closed_trades, x_series, colors):
        series = []
        cum_pnl = 0.0

        for t in closed_trades:
            cum_pnl += t['profit-loss-pct']
            series.append(cum_pnl)

        x_series.append(series)
        colors.append(Color.UTERM_COLORS_MAP[Color.WHITE])

    def compute_tef(self, closed_trades, x_series, colors, avg=False, stddev=False):
        series = []

        if len(closed_trades) < 1:
            return False, "Need at least 1 samples"

        if (avg or stddev) and len(closed_trades) < 8:
            return False, "Need at least 8 samples"

        for t in closed_trades:
            aep = float(t['avg-entry-price'])
            axp = float(t['avg-exit-price'])
            best = float(t['stats']['best-price'])
            worst = float(t['stats']['worst-price'])

            to_eff_pct = (axp - aep) / (best - worst)
            series.append(to_eff_pct * 100.0)

        if avg:
            x_series.append(list(MM_n(7, series)))
            colors.append(Color.UTERM_COLORS_MAP[Color.BLUE])
        elif stddev:
            x, t, b = compute_std_dev(series)

            x_series.append(list(x))
            colors.append(Color.UTERM_COLORS_MAP[Color.BLUE])

            x_series.append(list(t))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])

            x_series.append(list(b))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])
        else:
            x_series.append(series)
            colors.append(Color.UTERM_COLORS_MAP[Color.BLUE])

    def compute_eef(self, closed_trades, x_series, colors, avg=False, stddev=False):
        series = []

        if len(closed_trades) < 1:
            return False, "Need at least 1 samples"

        if (avg or stddev) and len(closed_trades) < 8:
            return False, "Need at least 8 samples"

        for t in closed_trades:
            aep = float(t['avg-entry-price'])
            best = float(t['stats']['best-price'])
            worst = float(t['stats']['worst-price'])

            en_eff_pct = (best - aep) / (best - worst)
            series.append(en_eff_pct * 100.0)

        if avg:
            x_series.append(list(MM_n(7, series)))
            colors.append(Color.UTERM_COLORS_MAP[Color.BLUE])
        elif stddev:
            x, t, b = compute_std_dev(series)

            x_series.append(list(x))
            colors.append(Color.UTERM_COLORS_MAP[Color.BLUE])

            x_series.append(list(t))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])

            x_series.append(list(b))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])
        else:
            x_series.append(series)
            colors.append(Color.UTERM_COLORS_MAP[Color.BLUE])

    def compute_xef(self, closed_trades, x_series, colors, avg=False, stddev=False):
        series = []

        if len(closed_trades) < 1:
            return False, "Need at least 1 samples"

        if (avg or stddev) and len(closed_trades) < 8:
            return False, "Need at least 8 samples"

        for t in closed_trades:
            axp = float(t['avg-exit-price'])
            best = float(t['stats']['best-price'])
            worst = float(t['stats']['worst-price'])

            ex_eff_pct = (axp - worst) / (best - worst)
            series.append(ex_eff_pct * 100.0)

        if avg:
            x_series.append(list(MM_n(7, series)))
            colors.append(Color.UTERM_COLORS_MAP[Color.BLUE])
        elif stddev:
            x, t, b = compute_std_dev(series)

            x_series.append(list(x))
            colors.append(Color.UTERM_COLORS_MAP[Color.BLUE])

            x_series.append(list(t))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])

            x_series.append(list(b))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])
        else:
            x_series.append(series)
            colors.append(Color.UTERM_COLORS_MAP[Color.BLUE])

    def compute_mfe(self, closed_trades, x_series, colors, avg, stddev):
        series = []

        if len(closed_trades) < 1:
            return False, "Need at least 1 samples"

        if (avg or stddev) and len(closed_trades) < 8:
            return False, "Need at least 8 samples"

        for t in closed_trades:
            aep = float(t['avg-entry-price'])
            best = float(t['stats']['best-price'])

            # always positive, 0 is worst
            if t['direction'] == "long" and aep:
                mfe_pct = (best - aep) / aep - (t['stats']['fees-pct'] * 0.01)
            elif t['direction'] == "short" and aep:
                mfe_pct = (aep - best) / aep - (t['stats']['fees-pct'] * 0.01)
            else:
                mfe_pct = 0

            series.append(mfe_pct * 100.0)

        if avg:
            x_series.append(list(MM_n(7, series)))
            colors.append(Color.UTERM_COLORS_MAP[Color.GREEN])
        elif stddev:
            x, t, b = compute_std_dev(series)

            x_series.append(list(x))
            colors.append(Color.UTERM_COLORS_MAP[Color.GREEN])

            x_series.append(list(t))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])

            x_series.append(list(b))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])
        else:
            x_series.append(series)
            colors.append(Color.UTERM_COLORS_MAP[Color.GREEN])

    def compute_mae(self, closed_trades, x_series, colors, avg, stddev):
        series = []

        if len(closed_trades) < 1:
            return False, "Need at least 1 samples"

        if (avg or stddev) and len(closed_trades) < 8:
            return False, "Need at least 8 samples"

        for t in closed_trades:
            aep = float(t['avg-entry-price'])
            worst = float(t['stats']['worst-price'])

            # always negative, 0 is best
            if t['direction'] == "long" and aep:
                mae_pct = (worst - aep) / aep - (t['stats']['fees-pct'] * 0.01)
            elif t['direction'] == "short" and aep:
                mae_pct = (aep - worst) / aep - (t['stats']['fees-pct'] * 0.01)
            else:
                mae_pct = 0

            series.append(mae_pct * 100.0)

        if avg:
            x_series.append(list(MM_n(7, series)))
            colors.append(Color.UTERM_COLORS_MAP[Color.RED])
        elif stddev:
            x, t, b = compute_std_dev(series)

            x_series.append(list(x))
            colors.append(Color.UTERM_COLORS_MAP[Color.RED])

            x_series.append(list(t))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])

            x_series.append(list(b))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])
        else:
            x_series.append(series)
            colors.append(Color.UTERM_COLORS_MAP[Color.RED])

    def compute_etd(self, closed_trades, x_series, colors, avg, stddev):
        series = []

        if len(closed_trades) < 1:
            return False, "Need at least 1 samples"

        if (avg or stddev) and len(closed_trades) < 8:
            return False, "Need at least 8 samples"

        for t in closed_trades:
            axp = float(t['avg-exit-price'])
            best = float(t['stats']['best-price'])

            # always negative, 0 is best
            if t['direction'] == "long" and axp:
                etd_pct = (axp - best) / best - (t['stats']['fees-pct'] * 0.01)
            elif t['direction'] == "short" and axp:
                etd_pct = (best - axp) / best - (t['stats']['fees-pct'] * 0.01)
            else:
                etd_pct = 0

            series.append(etd_pct * 100.0)

        if avg:
            x_series.append(list(MM_n(7, series)))
            colors.append(Color.UTERM_COLORS_MAP[Color.YELLOW])
        elif stddev:
            x, t, b = compute_std_dev(series)

            x_series.append(list(x))
            colors.append(Color.UTERM_COLORS_MAP[Color.YELLOW])

            x_series.append(list(t))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])

            x_series.append(list(b))
            colors.append(Color.UTERM_COLORS_MAP[Color.PURPLE])
        else:
            x_series.append(series)
            colors.append(Color.UTERM_COLORS_MAP[Color.YELLOW])

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, list(DrawStatsCommand.CHARTS) + strategy.symbols_ids(), args, tab_pos, direction)
        elif len(args) > 1:
            return self.iterate(len(args) - 1, DrawStatsCommand.CHARTS, args, tab_pos, direction)

        return args, 0


def compute_std_dev(series, factor=1.0):
    npa = np.array(series)

    basis = ta_SMA(npa, 7)
    dev = factor * ta_STDDEV(npa, 7)

    top_series = basis + dev
    bottom_series = basis - dev

    return basis, top_series, bottom_series


class StatsSummaryCommand(Command):
    """
    Display statistics summary.
    """

    SUMMARY = "to display statistic summary"
    HELP = (
        "param1: <market-id> for strategy only (optional)",
    )

    def __init__(self, commands_handler, strategy_service):
        super().__init__('stats', None)

        self._commands_handler = commands_handler

        self._strategy_service = strategy_service

    def execute(self, args):
        market_id = None

        if len(args) >= 1:
            # specific market
            strategy = self._strategy_service.strategy()
            if strategy:
                instrument = strategy.find_instrument(args[0])
                if instrument:
                    market_id = instrument.market_id

        summary = {}
        self._strategy_service.strategy().dumps_trainer_report(summary)
        log_summary(summary)

        return True, "Summary done"

    def completion(self, args, tab_pos, direction):
        if len(args) <= 1:
            strategy = self._strategy_service.strategy()
            if strategy:
                return self.iterate(0, list(DrawStatsCommand.CHARTS) + strategy.symbols_ids(), args, tab_pos, direction)
        elif len(args) > 1:
            return self.iterate(len(args) - 1, DrawStatsCommand.CHARTS, args, tab_pos, direction)

        return args, 0


def register_statistic_commands(commands_handler, strategy_service):
    commands_handler.register(DrawStatsCommand(commands_handler, strategy_service))
    commands_handler.register(StatsSummaryCommand(commands_handler, strategy_service))
