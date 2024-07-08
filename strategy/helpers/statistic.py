# @date 2024-07-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# Strategy helper to compute some statistics like max time to recover.

from datetime import datetime

from common.utils import UTC
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


class StrategyStatistics:
    """
    Contains results of compute_strategy_time_statistics.
    """
    class BaseUnit:
        max_time_to_recover: float = 0.0

        estimate_profit_per_month: float = 0.0

        avg_trade: float = 0.0

        avg_winning_trade: float = 0.0
        avg_loosing_trade: float = 0.0
        avg_win_loss_rate: float = 0.0  # avg_winning_trade / avg_loosing_trade

        sharpe_ratio: float = 1.0
        sortino_ratio: float = 1.0
        ulcer_index: float = 0.0

        def fmt_value(self, value):
            return value

        def dumps(self, to_dict):
            to_dict["max-time-to-recover"] = self.fmt_value(self.max_time_to_recover)
            to_dict['estimate-profit-per-month'] = self.fmt_value(self.estimate_profit_per_month)
            to_dict['avg-trade'] = self.fmt_value(self.avg_trade)
            to_dict['avg-winning-trade'] = self.fmt_value(self.avg_winning_trade)
            to_dict['avg-loosing-trade'] = self.fmt_value(self.avg_loosing_trade)
            to_dict['avg-win-loss-rate'] = self.fmt_value(self.avg_win_loss_rate)

            to_dict['sharpe-ratio'] = self.sharpe_ratio
            to_dict['sortino-ratio'] = self.sortino_ratio
            to_dict['ulcer-index'] = self.ulcer_index

    class PercentUnit(BaseUnit):
        def fmt_value(self, value):
            return "%.2f%%" % (value * 100.0)

    longest_flat_period: float = 0.0
    avg_time_in_market: float = 0.0

    num_traded_days: int = 0
    avg_trades_per_day: float = 0.0  # excluding weekend

    currency: BaseUnit = BaseUnit()
    percent: PercentUnit = PercentUnit()

    def dumps(self, to_dict):
        to_dict["longest-flat-period"] = self.longest_flat_period
        to_dict["avg-time-in-market"] = self.avg_time_in_market
        to_dict['num-traded-days'] = self.num_traded_days
        to_dict['avg-trades-per-day'] = self.avg_trades_per_day

        self.percent.dumps(to_dict['percent'])
        self.currency.dumps(to_dict['currency'])


def compute_strategy_statistics(strategy):
    """
    Compute some strategy statistics.
    Monthly draw-down are computed from daily sample of the account (trader). That's mean the balance value and PNL
    be correctly computed else the Ulcer ratio would be incorrect.
    Trader balance could be incorrect when backtesting using different market settlement/quote currency or when
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

    avg_time_in_market_samples = []

    profit_per_month_pct = [0.0]
    profit_per_month = [0.0]
    draw_down_per_month_pct = [0.0]
    draw_down_per_month = [0.0]

    draw_downs_sqr_pct = []
    draw_downs_sqr = []

    first_trade_ts = 0.0
    last_trade_ts = 0.0

    num_trades_even = 0
    num_trades_win = 0
    num_trades_loss = 0

    with strategy._mutex:
        closed_trades = get_closed_trades(strategy)
        num_trades = len(closed_trades)

        if num_trades <= 0:
            return StrategyStatistics()

        cum_pnl_pct = 0.0
        cum_winning_pnl_pct = 0.0
        cum_loosing_pnl_pct = 0.0  # as positive value
        max_pnl_pct = 0.0
        max_pnl_pct_ts = 0.0

        cum_pnl = 0.0
        cum_winning_pnl = 0.0
        cum_loosing_pnl = 0.0  # as positive value
        max_pnl = 0.0
        max_pnl_ts = 0.0

        prev_trade = None

        # sort by exit datetime to compute statistics
        closed_trades.sort(key=lambda x: str(x['stats']['last-realized-exit-datetime']))

        for t in closed_trades:
            cum_pnl_pct += t['profit-loss-pct']
            cum_pnl += t['profit-loss']

            trade_fre_ts = parse_datetime(t['stats']['first-realized-entry-datetime'])
            trade_lrx_ts = parse_datetime(t['stats']['last-realized-exit-datetime'])

            # max time to recover percentile
            if cum_pnl_pct >= max_pnl_pct:
                max_pnl_pct = cum_pnl_pct
                max_time_to_recover_pct = max(max_time_to_recover_pct, trade_lrx_ts - max_pnl_pct_ts)
                max_pnl_pct_ts = trade_lrx_ts

            # max time to recover currency
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
                elapsed_months = int((Instrument.basetime(trade_fre_ts, Instrument.TF_MONTH) - Instrument.basetime(
                        prev_fre_ts, Instrument.TF_MONTH)) / Instrument.TF_MONTH)

                if elapsed_months > 0:
                    profit_per_month_pct += [0.0] * elapsed_months
                    profit_per_month += [0.0] * elapsed_months

            # average time in market
            avg_time_in_market_samples.append(trade_lrx_ts - trade_fre_ts)

            # for avg num trades per day
            if first_trade_ts == 0.0:
                first_trade_ts = trade_fre_ts

            last_trade_ts = trade_fre_ts

            if round(t['profit-loss-pct'] * 10) == 0.0:
                num_trades_even += 1
            elif t['profit-loss-pct'] > 0:
                num_trades_win += 1
                cum_winning_pnl_pct += t['profit-loss-pct']
                cum_winning_pnl += t['profit-loss']
            elif t['profit-loss-pct'] < 0:
                num_trades_loss += 1
                cum_loosing_pnl_pct += -t['profit-loss-pct']
                cum_loosing_pnl += -t['profit-loss']
            else:
                num_trades_even += 1

            # cumulative per month
            profit_per_month_pct[-1] += t['profit-loss-pct']
            profit_per_month[-1] += t['profit-loss']

            # draw-downs square samples for Ulcer ratio
            # draw_downs_sqr_pct.append(((1.0 + cum_pnl_pct) / (1.0 + max_pnl_pct) - 1.0) ** 2)
            draw_downs_sqr_pct.append((cum_pnl_pct - max_pnl_pct) ** 2)
            draw_downs_sqr.append((cum_pnl - max_pnl) ** 2)

            # keep the previous trade details
            prev_trade = t

    # per month draw-down from trader account samples
    prev_sample_month = 0

    for n in range(0, len(trader.account.stats_samples)):
        if prev_sample_month == 0:
            prev_sample_month = Instrument.basetime(trader.account.stats_samples[n].timestamp, Instrument.TF_MONTH)

        sample_bt = Instrument.basetime(trader.account.stats_samples[n].timestamp, Instrument.TF_MONTH)

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

    results.avg_time_in_market = np.average(np.array(avg_time_in_market_samples))

    first_day_ts = Instrument.basetime(first_trade_ts, Instrument.TF_DAY)
    last_day_ts = Instrument.basetime(last_trade_ts, Instrument.TF_DAY)

    # at least one day because of min one trade
    results.num_traded_days = int((last_day_ts - first_day_ts) / Instrument.TF_DAY) + 1

    results.avg_trades_per_day_inc_we = num_trades / results.num_traded_days
    results.avg_trades_per_day = results.avg_trades_per_day_inc_we * (252 / 365)

    # estimate profitability per month
    # results.percent.estimate_profit_per_month = (1.0 + cum_pnl_pct) ** (1.0 * (30.5 / results.num_traded_days)) - 1.0
    results.percent.estimate_profit_per_month = cum_pnl_pct * (30.5 / results.num_traded_days)
    results.currency.estimate_profit_per_month = cum_pnl * (30.5 / results.num_traded_days)

    # average trade
    results.percent.avg_trade = cum_pnl_pct / num_trades
    results.currency.avg_trade = cum_pnl / num_trades

    results.percent.avg_winning_trade = cum_winning_pnl_pct / num_trades_win if num_trades_win > 0 else 0.0
    results.currency.avg_winning_trade = cum_winning_pnl / num_trades_win if num_trades_win > 0 else 0.0
    results.percent.avg_loosing_trade = cum_loosing_pnl_pct / num_trades_loss if num_trades_loss > 0 else 0.0
    results.currency.avg_loosing_trade = cum_loosing_pnl / num_trades_loss if num_trades_loss > 0 else 0.0

    results.percent.avg_win_loss_rate = results.percent.avg_winning_trade / results.percent.avg_loosing_trade if (
        results.percent.avg_loosing_trade) else 1.0

    results.currency.avg_win_loss_rate = results.currency.avg_winning_trade / results.currency.avg_loosing_trade if (
        results.currency.avg_loosing_trade) else 1.0

    # Sharpe Ratio
    if len(profit_per_month_pct) > 1:
        # Sharpe ratio
        results.percent.sharpe_ratio = ((results.percent.estimate_profit_per_month - RISK_FREE_RATE_OF_RETURN) /
                                        np.std(np.array(profit_per_month_pct), ddof=1))
        results.currency.sharpe_ratio = ((results.currency.estimate_profit_per_month - RISK_FREE_RATE_OF_RETURN) /
                                         np.std(np.array(profit_per_month), ddof=1))

        # Sortino ratio
        results.percent.sortino_ratio = ((results.percent.estimate_profit_per_month - RISK_FREE_RATE_OF_RETURN) /
                                         np.std(np.array(draw_down_per_month_pct), ddof=1))
        results.currency.sortino_ratio = ((results.currency.estimate_profit_per_month - RISK_FREE_RATE_OF_RETURN) /
                                          np.std(np.array(draw_down_per_month), ddof=1))

        # Ulcer index
        results.percent.ulcer_index = np.sqrt(np.mean(np.array(draw_downs_sqr_pct)))
        results.currency.ulcer_index = np.sqrt(np.mean(np.array(draw_downs_sqr)))

    return results
