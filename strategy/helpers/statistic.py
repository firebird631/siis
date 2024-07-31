# @date 2024-07-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# Strategy helper to compute some statistics like max time to recover.

from datetime import datetime
from typing import List

from common.utils import UTC, truncate
from instrument.instrument import Instrument
from strategy.helpers.closedtradedataset import get_closed_trades

import scipy.stats as stats
import numpy as np

import logging
logger = logging.getLogger('siis.strategy.helpers.statistics')
error_logger = logging.getLogger('siis.error.strategy.helpers.statistics')


RISK_FREE_RATE_OF_RETURN = 0.0


def parse_datetime(dt_str: str) -> float:
    return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=UTC()).timestamp()


class BaseSampler(object):
    name: str = ""

    samples: List[float]
    max_value: float = 0.0
    min_value: float = 0.0
    cumulated: float = 0.0

    avg: float = 0.0      # valid after finalize
    std_dev: float = 0.0  # valid after finalize

    def __init__(self, name):
        self.name = name
        self.samples = []

    def add_sample(self, value):
        self.samples.append(value)
        self.cumulated += value

        if len(self.samples):
            self.min_value = min(self.min_value, value)
            self.max_value = max(self.max_value, value)
        else:
            self.min_value = self.max_value = value

    @property
    def count(self):
        return len(self.samples)

    def finalize(self):
        self.avg = np.average(np.array(self.samples)) if len(self.samples) > 0 else 0.0
        self.std_dev = np.std(np.array(self.samples), ddof=1) if len(self.samples) > 1 else 0.0

        return self

    def fmt_value(self, value):
        return value

    def dumps(self, to_dict):
        to_dict[self.name] = {
            'min': self.fmt_value(self.min_value),
            'max': self.fmt_value(self.max_value),
            'cum': self.fmt_value(self.cumulated),
            'avg': self.fmt_value(self.avg),
            'std-dev': self.fmt_value(self.std_dev)
        }


class PercentSampler(BaseSampler):

    def __init__(self, name):
        super().__init__(name)

    def fmt_value(self, value):
        return "%.2f%%" % (value * 100.0)


class StrategyStatistics:
    """
    Contains results of compute_strategy_time_statistics.
    """
    class BaseStats:
        max_time_to_recover: float = 0.0

        estimate_profit_per_month: float = 0.0

        avg_win_loss_rate: float = 0.0  # avg_winning_trade / avg_loosing_trade

        sharpe_ratio: float = 1.0
        sortino_ratio: float = 1.0
        ulcer_index: float = 0.0

        samplers: List[BaseSampler]

        def __init__(self):
            self.samplers = []

        def add_sampler(self, sampler):
            self.samplers.append(sampler)

        def fmt_value(self, value):
            return value

        def dumps(self, to_dict):
            to_dict["max-time-to-recover"] = "%.3f" % self.max_time_to_recover
            to_dict['estimate-profit-per-month'] = self.fmt_value(self.estimate_profit_per_month)
            to_dict['avg-win-loss-rate'] = truncate(self.avg_win_loss_rate, 2)

            to_dict['sharpe-ratio'] = self.sharpe_ratio
            to_dict['sortino-ratio'] = self.sortino_ratio
            to_dict['ulcer-index'] = self.ulcer_index

            for sampler in self.samplers:
                sampler.dumps(to_dict)

    class PercentStats(BaseStats):

        samplers: List[PercentSampler]

        def __init__(self):
            super().__init__()

        def add_sampler(self, sampler):
            self.samplers.append(sampler)

        def fmt_value(self, value):
            return "%.2f%%" % (value * 100.0)

    longest_flat_period: float = 0.0
    avg_time_in_market: float = 0.0

    num_traded_days: int = 0
    avg_trades_per_day: float = 0.0  # excluding weekend

    currency: BaseStats = BaseStats()
    percent: PercentStats = PercentStats()

    def dumps(self, to_dict):
        to_dict["longest-flat-period"] = "%.3f" % self.longest_flat_period
        to_dict["avg-time-in-market"] = "%.3f" % self.avg_time_in_market
        to_dict['num-traded-days'] = truncate(self.num_traded_days, 2)
        to_dict['avg-trades-per-day'] = truncate(self.avg_trades_per_day, 2)

        to_dict['percent'] = {}
        self.percent.dumps(to_dict['percent'])

        to_dict['currency'] = {}
        self.currency.dumps(to_dict['currency'])


def compute_strategy_statistics(strategy):
    """
    Compute some strategy statistics.
    Monthly draw-down are computed from daily sample of the account (trader). That's mean the balance value and PNL
    be correctly computed else the Ulcer ratio would be incorrect.
    Trader balance could be incorrect when backtesting using different market settlement/quote currencies or when
    the account currency is different from these above or if the base exchange rate for each instrument is invalid
    with some watchers.

    @param strategy: Current valid strategy.
    @return: A dataclass StrategyTimeStatistics

    @note The Configured percent mode is without reinvestment.
    """
    if not strategy:
        return StrategyStatistics()

    trader = strategy.trader()
    if not trader:
        return StrategyStatistics()

    max_time_to_recover_pct = 0.0  # in seconds
    max_time_to_recover = 0.0  # in seconds

    longest_flat_period = 0.0  # in seconds

    time_in_market_samples = []

    profit_per_month_pct = [0.0]
    profit_per_month = [0.0]
    draw_down_per_month_pct = [0.0]
    draw_down_per_month = [0.0]

    draw_downs_sqr_pct = []
    draw_downs_sqr = []

    first_trade_ts = 0.0
    last_trade_ts = 0.0

    any_trade_pnl = BaseSampler("trade-pnl")
    any_trade_pnl_pct = PercentSampler("trade-pnl")

    winning_trade_pnl = BaseSampler("winning-trade-pnl")
    winning_trade_pnl_pct = PercentSampler("winning-trade-pnl")
    loosing_trade_pnl = BaseSampler("loosing-trade-pnl")
    loosing_trade_pnl_pct = PercentSampler("loosing-trade-pnl")

    mfe_sampler = PercentSampler("mfe")
    mae_sampler = PercentSampler("mae")
    etd_sampler = PercentSampler("etd")

    eef_sampler = PercentSampler("entry-efficiency")
    xef_sampler = PercentSampler("exit-efficiency")
    tef_sampler = PercentSampler("total-efficiency")

    with strategy.mutex:
        closed_trades = get_closed_trades(strategy)
        num_trades = len(closed_trades)

        if num_trades <= 0:
            return StrategyStatistics()

        cum_pnl_pct = 0.0
        max_pnl_pct = 0.0
        max_pnl_pct_ts = 0.0

        cum_pnl = 0.0
        max_pnl = 0.0
        max_pnl_ts = 0.0

        prev_trade = None

        # sort by exit datetime to compute statistics
        closed_trades.sort(key=lambda x: str(x['stats']['last-realized-exit-datetime']))

        for t in closed_trades:
            # parse trade info
            direction = 1 if t['direction'] == "long" else -1
            # fees = t['stats']['fees-pct'] * 0.01
            entry_price = float(t['avg-entry-price'])
            exit_price = float(t['avg-exit-price'])
            best_price = float(t['stats']['best-price'])
            worst_price = float(t['stats']['worst-price'])

            trade_fre_ts = parse_datetime(t['stats']['first-realized-entry-datetime'])
            trade_lrx_ts = parse_datetime(t['stats']['last-realized-exit-datetime'])

            # cumulative PNL
            any_trade_pnl_pct.add_sample(t['profit-loss-pct'] * 0.01)
            any_trade_pnl.add_sample(t['stats']['profit-loss'])

            # but this cumulative is used for max time to recover
            cum_pnl_pct += t['profit-loss-pct'] * 0.01
            cum_pnl += t['stats']['profit-loss']

            # max time to recover (by percentage)
            if cum_pnl_pct >= max_pnl_pct:
                max_pnl_pct = cum_pnl_pct
                max_time_to_recover_pct = max(max_time_to_recover_pct, trade_lrx_ts - max_pnl_pct_ts)
                max_pnl_pct_ts = trade_lrx_ts

            # max time to recover (by currency)
            if cum_pnl >= max_pnl:
                max_pnl = cum_pnl
                max_time_to_recover = max(max_time_to_recover, trade_lrx_ts - max_pnl_ts)
                max_pnl_ts = trade_lrx_ts

            # longest flat period and average trades per day
            if prev_trade:
                prev_fre_ts = parse_datetime(prev_trade['stats']['first-realized-entry-datetime'])
                prev_lrx_ts = parse_datetime(prev_trade['stats']['last-realized-exit-datetime'])

                longest_flat_period = max(longest_flat_period, trade_fre_ts - prev_lrx_ts)

                # new monthly sample
                elapsed_months = int((Instrument.basetime(Instrument.TF_MONTH, trade_fre_ts) - Instrument.basetime(
                        Instrument.TF_MONTH, prev_fre_ts)) / Instrument.TF_MONTH)

                if elapsed_months > 0:
                    profit_per_month_pct += [0.0] * elapsed_months
                    profit_per_month += [0.0] * elapsed_months

            # average time in market
            time_in_market_samples.append(trade_lrx_ts - trade_fre_ts)

            # for avg num trades per day
            if first_trade_ts == 0.0:
                first_trade_ts = trade_fre_ts

            last_trade_ts = trade_fre_ts

            # winning, loosing trade profit/loss
            if t['profit-loss-pct'] > 0:
                winning_trade_pnl_pct.add_sample(t['profit-loss-pct'] * 0.01)
            elif t['profit-loss-pct'] < 0:
                loosing_trade_pnl_pct.add_sample(t['profit-loss-pct'] * 0.01)

            if t['stats']['profit-loss'] > 0:
                winning_trade_pnl.add_sample(t['stats']['profit-loss'])
            elif t['stats']['profit-loss'] < 0:
                loosing_trade_pnl.add_sample(t['stats']['profit-loss'])

            # cumulative per month
            profit_per_month_pct[-1] += t['profit-loss-pct'] * 0.01
            profit_per_month[-1] += t['stats']['profit-loss']

            # draw-downs square samples for Ulcer ratio (relative or absolute percentage)
            # draw_downs_sqr_pct.append(((1.0 + cum_pnl_pct) / (1.0 + max_pnl_pct) - 1.0) ** 2)
            draw_downs_sqr_pct.append((cum_pnl_pct - max_pnl_pct) ** 2)
            draw_downs_sqr.append((cum_pnl - max_pnl) ** 2)

            # MFE, MAE, ETD (gross value, no trade fees)
            if entry_price != 0.0:
                mfe_sampler.add_sample(direction * (best_price - entry_price) / entry_price)
                mae_sampler.add_sample(direction * (entry_price - worst_price) / entry_price)
            else:
                mfe_sampler.add_sample(0.0)
                mae_sampler.add_sample(0.0)

            if exit_price != 0.0:
                etd_sampler.add_sample(direction * (best_price - exit_price) / exit_price)
            else:
                etd_sampler.add_sample(0.0)

            # efficiency
            if best_price - worst_price != 0.0:
                eef_sampler.add_sample((best_price - entry_price) / (best_price - worst_price))
                xef_sampler.add_sample((exit_price - worst_price) / (best_price - worst_price))
                tef_sampler.add_sample((exit_price - entry_price) / (best_price - worst_price))
            else:
                eef_sampler.add_sample(0.0)
                xef_sampler.add_sample(0.0)
                tef_sampler.add_sample(0.0)

            # keep the previous trade details
            prev_trade = t

    # per month draw-down from trader account samples
    prev_sample_month = 0

    for n in range(0, len(trader.account.stats_samples)):
        sample_bt = Instrument.basetime(Instrument.TF_MONTH, trader.account.stats_samples[n].timestamp)

        if prev_sample_month == 0:
            prev_sample_month = sample_bt

        elapsed_months = int((sample_bt - prev_sample_month) / Instrument.TF_MONTH)
        if elapsed_months > 0:
            draw_down_per_month_pct += [0.0] * elapsed_months
            draw_down_per_month += [0.0] * elapsed_months

        # a positive value
        draw_down_per_month_pct[-1] = max(draw_down_per_month_pct[-1], trader.account.stats_samples[n].draw_down_rate)
        draw_down_per_month[-1] = max(draw_down_per_month[-1], trader.account.stats_samples[n].draw_down)

    # results
    results = StrategyStatistics()

    results.percent.max_time_to_recover = max_time_to_recover_pct
    results.currency.max_time_to_recover = max_time_to_recover

    results.longest_flat_period = longest_flat_period

    results.avg_time_in_market = np.average(np.array(time_in_market_samples))

    first_day_ts = Instrument.basetime(Instrument.TF_DAY, first_trade_ts)
    last_day_ts = Instrument.basetime(Instrument.TF_DAY, last_trade_ts)

    # at least one day because of min one trade
    results.num_traded_days = int((last_day_ts - first_day_ts) / Instrument.TF_DAY) + 1

    results.avg_trades_per_day_inc_we = num_trades / results.num_traded_days
    results.avg_trades_per_day = results.avg_trades_per_day_inc_we * (252 / 365)

    # estimate profitability per month
    # results.percent.estimate_profit_per_month = (1.0 + cum_pnl_pct) ** (1.0 * (30.5 / results.num_traded_days)) - 1.0
    results.percent.estimate_profit_per_month = cum_pnl_pct * (30.5 / results.num_traded_days)
    results.currency.estimate_profit_per_month = cum_pnl * (30.5 / results.num_traded_days)

    # Sharpe Ratio
    if len(profit_per_month_pct) > 1:
        # Sharpe ratio (Student t distribution)
        results.percent.sharpe_ratio = ((results.percent.estimate_profit_per_month - RISK_FREE_RATE_OF_RETURN) /
                                        np.std(np.array(profit_per_month_pct), ddof=1))
        results.currency.sharpe_ratio = ((results.currency.estimate_profit_per_month - RISK_FREE_RATE_OF_RETURN) /
                                         np.std(np.array(profit_per_month), ddof=1))

        # Sortino ratio (Student t distribution)
        results.percent.sortino_ratio = ((results.percent.estimate_profit_per_month - RISK_FREE_RATE_OF_RETURN) /
                                         np.std(np.array(draw_down_per_month_pct), ddof=1))
        results.currency.sortino_ratio = ((results.currency.estimate_profit_per_month - RISK_FREE_RATE_OF_RETURN) /
                                          np.std(np.array(draw_down_per_month), ddof=1))

        # Ulcer index
        results.percent.ulcer_index = np.sqrt(np.mean(np.array(draw_downs_sqr_pct)))
        results.currency.ulcer_index = np.sqrt(np.mean(np.array(draw_downs_sqr)))

    # Total PNL, Winning PNL, Loosing PNL
    results.percent.add_sampler(any_trade_pnl_pct.finalize())
    results.currency.add_sampler(any_trade_pnl.finalize())
    results.percent.add_sampler(winning_trade_pnl_pct.finalize())
    results.currency.add_sampler(winning_trade_pnl.finalize())
    results.percent.add_sampler(loosing_trade_pnl_pct.finalize())
    results.currency.add_sampler(loosing_trade_pnl.finalize())

    # Win/Loss Rate (after finalize)
    results.percent.avg_win_loss_rate = winning_trade_pnl_pct.avg / -loosing_trade_pnl_pct.avg if (
            loosing_trade_pnl_pct.avg != 0) else 1.0

    results.currency.avg_win_loss_rate = winning_trade_pnl.avg / -loosing_trade_pnl.avg if (
            loosing_trade_pnl.avg != 0) else 1.0

    # MFE, MAE, ETD
    results.percent.add_sampler(mfe_sampler.finalize())
    results.percent.add_sampler(mae_sampler.finalize())
    results.percent.add_sampler(etd_sampler.finalize())

    # efficiency
    results.percent.add_sampler(eef_sampler.finalize())
    results.percent.add_sampler(xef_sampler.finalize())
    results.percent.add_sampler(tef_sampler.finalize())

    return results
