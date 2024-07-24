# @date 2023-04-07
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Trainer selection of the final best candidate

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Union, List

import logging

from config.utils import get_stats

logger = logging.getLogger('siis.strategy.learning.trainerselect')
error_logger = logging.getLogger('siis.error.strategy.learning.trainerselect')
traceback_logger = logging.getLogger('siis.traceback.strategy.learning.trainerselect')


def trainer_selection(results: List, learning_parameters: dict, method: int):
    """
    Simple implementation to select the best candidate from the evaluated ones.
    @return: A single candidate or None.
    @todo Improve model for high avg efficiencies
    @todo Implements for Sharpe ratio, Sortino ratio, Ulcer index
    """
    from strategy.learning.trainer import TrainerCommander

    best_result = None

    min_perf = get_stats(learning_parameters, "trainer.min-performance", 0.0)
    min_profit = get_stats(learning_parameters, "trainer.min-profit", 0.0)

    # comparators
    max_perf = min_perf
    max_profit = min_profit
    max_sf_rate = 0.0
    min_loss_series = sys.float_info.max
    best_take_profit_rate = 0.0
    max_avg_mfe_rate = sys.float_info.min
    max_avg_mae_rate = sys.float_info.min
    max_avg_etd_rate = sys.float_info.min
    best_std_mfe_rate = 9999
    best_std_etd_rate = 9999
    best_std_mae_rate = 9999
    max_avg_eef_rate = 0.0
    max_avg_xef_rate = 0.0
    max_avg_tef_rate = 0.0
    max_sharpe_ratio = 0.0
    max_sortino_ratio = 0.0
    min_ulcer_index = sys.float_info.max
    max_avg_win_loss_rate = 0.0

    # simple method, the best overall performance
    for candidate in results:
        if not candidate:
            continue

        # check the minimal performance if configured
        performance = get_stats(candidate, "performance", 0.0)
        if performance < min_perf:
            continue

        # and minimum profit in currency if configured
        profit = get_stats(candidate, 'currency.profit-loss.cum', 0.0)
        if profit < min_profit:
            continue

        if method == TrainerCommander.BEST_PERF:
            # only keep the best performance PNL percentage
            if performance > max_perf:
                max_perf = performance
                best_result = candidate

        elif method == TrainerCommander.BEST_PROFIT:
            # select best from the best profit in currency
            if profit > max_profit:
                max_profit = profit
                best_result = candidate

        elif method == TrainerCommander.BEST_WINRATE:
            # only keep the best win-rate
            succeed = get_stats(candidate, 'succeed-trades', 0)
            total_trades = get_stats(candidate, 'total-trades', 0)

            sf_rate = succeed / total_trades if total_trades > 0 else 0.0

            if sf_rate > max_sf_rate:
                max_sf_rate = sf_rate
                best_result = candidate

        elif method == TrainerCommander.LOWER_CONT_LOSS:
            # only keep the less max contiguous losses
            loss_series = candidate.get('max-loss-series', 0)

            if loss_series < min_loss_series:
                min_loss_series = loss_series
                best_result = candidate

        elif method == TrainerCommander.TAKE_PROFIT_RATIO:
            # only keep the best number of trade at take-profit
            tp_gain = get_stats(candidate, 'take-profit-in-gain', 0)
            total_trades = get_stats(candidate, 'total-trades', 0)

            take_profit_rate = tp_gain / total_trades if total_trades > 0 else 0.0

            if take_profit_rate > best_take_profit_rate:
                best_take_profit_rate = take_profit_rate
                best_result = candidate

        elif method == TrainerCommander.BEST_AVG_MFE:
            # only keep the best average MFE rate
            avg_mfe_rate = get_stats(candidate, "percent.mfe.avg")

            if avg_mfe_rate is not None:
                if avg_mfe_rate > max_avg_mfe_rate:
                    max_avg_mfe_rate = avg_mfe_rate
                    best_result = candidate

        elif method == TrainerCommander.BEST_AVG_MAE:
            # one having the lower average MAE rate
            avg_mae_rate = get_stats(candidate, "percent.mae.avg")

            if avg_mae_rate is not None:
                if avg_mae_rate > max_avg_mae_rate:
                    max_avg_mae_rate = avg_mae_rate
                    best_result = candidate

        elif method == TrainerCommander.BEST_AVG_ETD:
            # one having the lower average ETD rate
            avg_etd_rate = get_stats(candidate, "percent.etd.avg")
            if avg_etd_rate is not None:
                if avg_etd_rate > max_avg_etd_rate:
                    max_avg_etd_rate = avg_etd_rate
                    best_result = candidate

        elif method == TrainerCommander.BEST_STDDEV_MFE:
            # one have the lower std-dev MFE
            std_mfe_rate = get_stats(candidate, "percent.mfe.std-dev")

            if std_mfe_rate is not None:
                if std_mfe_rate < best_std_mfe_rate:
                    best_std_mfe_rate = std_mfe_rate
                    best_result = candidate

        elif method == TrainerCommander.BEST_STDDEV_MAE:
            # one have the lower std-dev MAE
            std_mae_rate = get_stats(candidate, "percent.mae.std-dev")

            if std_mae_rate is not None:
                if std_mae_rate < best_std_mae_rate:
                    best_std_mae_rate = std_mae_rate
                    best_result = candidate

        elif method == TrainerCommander.BEST_STDDEV_ETD:
            # one have the lower std-dev ETD
            std_etd_rate = get_stats(candidate, "percent.etd.std-dev")

            if std_etd_rate is not None:
                if std_etd_rate < best_std_etd_rate:
                    best_std_etd_rate = std_etd_rate
                    best_result = candidate

        elif method == TrainerCommander.HIGHER_AVG_EEF:
            # only keep the best average entry efficiency rate
            avg_eef_rate = get_stats(candidate, "percent.entry-efficiency.avg", min_value=-1.0, max_value=1.0)

            if avg_eef_rate is not None:
                if avg_eef_rate > max_avg_eef_rate:
                    max_avg_eef_rate = avg_eef_rate
                    best_result = candidate

        elif method == TrainerCommander.HIGHER_AVG_XEF:
            # only keep the best average exit efficiency rate
            avg_xef_rate = get_stats(candidate, "percent.exit-efficiency.avg", min_value=-1.0, max_value=1.0)

            if avg_xef_rate is not None:
                if avg_xef_rate > max_avg_xef_rate:
                    max_avg_xef_rate = avg_xef_rate
                    best_result = candidate

        elif method == TrainerCommander.HIGHER_AVG_TEF:
            # only keep the best average total (entry and exit) efficiency rate
            avg_tef_rate = get_stats(candidate, "percent.total-efficiency.avg", min_value=-1.0, max_value=1.0)

            if avg_tef_rate is not None:
                if avg_tef_rate > max_avg_tef_rate:
                    max_avg_tef_rate = avg_tef_rate
                    best_result = candidate

        elif method == TrainerCommander.BEST_WIN_LOSS_RATE:
            # only keep the best winning/loosing PNL rate
            avg_win_loss_rate = get_stats(candidate, "percent.avg-win-loss-rate")

            if avg_win_loss_rate is not None:
                if avg_win_loss_rate > max_avg_win_loss_rate:
                    max_avg_win_loss_rate = avg_win_loss_rate
                    best_result = candidate

        elif method == TrainerCommander.BEST_SHARPE_RATIO:
            # higher Sharpe ratio
            sharpe_ratio = get_stats(candidate, "percent.sharpe-ratio")

            if sharpe_ratio is not None:
                if sharpe_ratio > max_sharpe_ratio:
                    max_sharpe_ratio = sharpe_ratio
                    best_result = candidate

        elif method == TrainerCommander.BEST_SORTINO_RATIO:
            # higher Sortino ratio
            sortino_ratio = get_stats(candidate, "percent.sortino-ratio")

            if sortino_ratio is not None:
                if sortino_ratio > max_sortino_ratio:
                    max_sortino_ratio = sortino_ratio
                    best_result = candidate

        elif method == TrainerCommander.BEST_ULCER_INDEX:
            # lower Ulcer index
            ulcer_index = get_stats(candidate, "percent.ulcer-index")

            if ulcer_index is not None:
                if ulcer_index > min_ulcer_index:
                    min_ulcer_index = ulcer_index
                    best_result = candidate

    return best_result
