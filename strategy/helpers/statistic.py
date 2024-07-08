# @date 2024-07-08
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2024 Dream Overflow
# Strategy helper to compute some statistics like max time to recover.

from datetime import datetime

from common.utils import UTC
from instrument.instrument import Instrument
from strategy.helpers.closedtradedataset import get_closed_trades

import numpy as np

import logging
logger = logging.getLogger('siis.strategy.helpers.statistics')
error_logger = logging.getLogger('siis.error.strategy.helpers.statistics')


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

        def fmt_value(self, value):
            return value

        def dumps(self, to_dict):
            to_dict["max-time-to-recover"] = self.fmt_value(self.max_time_to_recover)
            to_dict['estimate-profit-per-month'] = self.fmt_value(self.estimate_profit_per_month)
            to_dict['avg-trade'] = self.fmt_value(self.avg_trade)
            to_dict['avg-winning-trade'] = self.fmt_value(self.avg_winning_trade)
            to_dict['avg-loosing-trade'] = self.fmt_value(self.avg_loosing_trade)
            to_dict['avg-win-loss-rate'] = self.fmt_value(self.avg_win_loss_rate)

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
    @param strategy: Current valid strategy.
    @return: A dataclass StrategyTimeStatistics
    @todo Per month profit for ratio
    """
    if not strategy:
        return StrategyStatistics()

    max_time_to_recover_pct = 0.0  # in seconds
    max_time_to_recover_currency = 0.0  # in seconds

    longest_flat_period = 0.0  # in seconds

    # num_trades_cur_day = 0

    avg_time_in_market_samples = []

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
        cum_loosing_pnl_pct = 0.0
        max_pnl_pct = 0.0
        max_pnl_pct_ts = 0.0

        cum_pnl = 0.0
        cum_winning_pnl = 0.0
        cum_loosing_pnl = 0.0
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
                max_time_to_recover_currency = max(max_time_to_recover_currency, trade_lrx_ts - max_pnl_ts)
                max_pnl_ts = trade_lrx_ts

            # longest flat period and average trades per day
            if prev_trade:
                prev_fre_ts = parse_datetime(prev_trade['stats']['first-realized-entry-datetime'])
                prev_lrx_ts = parse_datetime(prev_trade['stats']['last-realized-exit-datetime'])

                longest_flat_period = max(longest_flat_period, trade_fre_ts - prev_lrx_ts)

                # # average trades per day
                # prev_base_bt = Instrument.basetime(prev_fre_ts, Instrument.TF_DAY)
                # trade_base_bt = Instrument.basetime(trade_fre_ts, Instrument.TF_DAY)
                #
                # if prev_base_bt == trade_base_bt:
                #     # one more trade executed the same day
                #     num_trades_cur_day += 1
                # else:
                #     # reset
                #     num_trades_cur_day = 1

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
                cum_loosing_pnl_pct += t['profit-loss-pct']
                cum_loosing_pnl += t['profit-loss']
            else:
                num_trades_even += 1

            # keep the previous trade details
            prev_trade = t

    # results
    results = StrategyStatistics()

    results.percent.max_time_to_recover = max_time_to_recover_pct
    results.currency.max_time_to_recover = max_time_to_recover_currency

    results.longest_flat_period = longest_flat_period

    results.avg_time_in_market = np.average(np.array(avg_time_in_market_samples))

    first_day_ts = Instrument.basetime(first_trade_ts, Instrument.TF_DAY)
    last_day_ts = Instrument.basetime(last_trade_ts, Instrument.TF_DAY)

    results.num_traded_days = int((last_day_ts - first_day_ts) / Instrument.TF_DAY) + 1

    results.avg_trades_per_day_inc_we = num_trades / results.num_traded_days
    results.avg_trades_per_day = results.avg_trades_per_day_inc_we * (252 / 365)

    # estimate profitability per month
    results.percent.estimate_profit_per_month = (1.0 + cum_pnl_pct) ** (1.0 * (30.5 / results.num_traded_days)) - 1.0
    results.currency.estimate_profit_per_month = (1.0 + cum_pnl) ** (1.0 * (30.5 / results.num_traded_days)) - 1.0

    # average trade
    results.percent.avg_trade = cum_pnl_pct / num_trades
    results.currency.avg_trade = cum_pnl / num_trades

    results.percent.avg_winning_trade = cum_winning_pnl_pct / num_trades_win if num_trades_win > 0 else 0.0
    results.currency.avg_winning_trade = cum_winning_pnl / num_trades_win if num_trades_win > 0 else 0.0
    results.percent.avg_loosing_trade = cum_loosing_pnl_pct / num_trades_loss if num_trades_loss > 0 else 0.0
    results.currency.avg_loosing_trade = cum_loosing_pnl / num_trades_loss if num_trades_loss > 0 else 0.0

    results.percent.avg_win_loss_rate = results.percent.avg_winning_trade / results.percent.avg_loosing_trade if (
        results.percent.avg_loosing_trade) else results.percent.avg_loosing_trade

    results.currency.avg_win_loss_rate = results.currency.avg_winning_trade / results.currency.avg_loosing_trade if (
        results.currency.avg_loosing_trade) else results.currency.avg_winning_trade

    # Probability (Student's t-distribution)

    # Sharpe Ratio @todo
    # (Profit per Month – risk free Rate of Return) / standard deviation of monthly profits
    # with risk free Rate of Return = 0

    # Sortino Ratio @todo
    # (Profit per Month – risk free Rate of Return) / standard deviation of monthly drawdown
    # with risk free Rate of Return = 0

    # Ulcer Index @todo
    # Currency : SQRT(Summation((cumulative currency profit - maximum realized currency profit) ^2 ) / Total # of trades)
    # Percent : SQRT(Summation((1 + cumulative percent profit / (1 + maximum realized percent profit) - 1) ^2 ) / Total # of trades)

    return results
