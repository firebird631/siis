# @date 2023-04-11
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Trainer fitness adjustment methods implementations

from __future__ import annotations

import logging
import math

import numpy as np
from scipy import stats

from config.utils import get_stats

logger = logging.getLogger('siis.tools.trainerfitness')
error_logger = logging.getLogger('siis.tools.error.trainerfitness')
traceback_logger = logging.getLogger('siis.tools.traceback.trainerfitness')


def compute_t_value(confidence: float, sample_size: int):
    dof = sample_size - 1
    alpha = 1 - confidence
    return stats.t.ppf(1 - alpha * 0.5, dof)


def p_n_major(p: float, v: float, sample_size: int, confidence: float = 0.95, n: float = 1.0):
    # p from -1..n
    t_value = compute_t_value(confidence, sample_size)
    return p * (1 + t_value * v * n)


def p_n_minor(p: float, v: float, sample_size: int, confidence: float = 0.95, n: float = 1.0):
    # p from -1..n
    t_value = compute_t_value(confidence, sample_size)
    return p * (1 - t_value * v * n)


def error_margin(t_value: float, sample_size: int, std_dev: float, mean: float):
    err = t_value * (std_dev / np.sqrt(sample_size))

    return mean - err, mean + err


def trainer_fitness(candidate: dict, selection: int):
    """
    Adjust the fitness result according to the selection method.
    @param candidate: dict with complete result set
    @param selection: TrainerCommander selection mode
    @return: float adjusted fitness
    @todo Implements for Sharpe ratio, Sortino ratio, Ulcer index
    """
    from strategy.learning.trainer import TrainerCommander

    if not candidate:
        return 0.0

    perf = get_stats(candidate, 'performance')
    total_trades = get_stats(candidate, 'total-trades')

    # default to best performance
    fitness = -perf

    if perf < 0.0:
        return fitness

    # fitness adjustment according to the selection method
    if selection == TrainerCommander.BEST_WINRATE:
        # fitness is global performance multiply by best win-rate
        succeed = get_stats(candidate, 'succeed-trades', 0)
        total_trades = get_stats(candidate, 'total-trades', 0)

        sf_rate = succeed / total_trades if total_trades > 0 else 0.0
        fitness = -(perf * ((0.5 + sf_rate) ** 2))

    elif selection == TrainerCommander.LOWER_CONT_LOSS:
        # fitness performance x by neg number contiguous loss
        max_loss_series = get_stats(candidate, 'max-loss-series')

        if max_loss_series is not None:
            # 100 means 10 contiguous loss or more are very penalised
            fitness = -perf * (100 - max_loss_series * max_loss_series)

    elif selection == TrainerCommander.TAKE_PROFIT_RATIO:
        # fitness is global performance multiply by rate of number in winning take profit
        tp_gain = get_stats(candidate, 'take-profit-in-gain', 0)
        total_trades = get_stats(candidate, 'total-trades', 0)

        tp_win_rate = tp_gain / total_trades if total_trades > 0 else 0
        fitness = -(perf * ((0.5 + tp_win_rate) ** 2))

    elif selection == TrainerCommander.BEST_AVG_MFE:
        # fitness performance x higher average MFE factor
        avg_mfe_rate = get_stats(candidate, "percent.mfe.avg")

        if avg_mfe_rate is not None:
            # for MFE 0 is worst, 1 or more better
            fitness = -perf * (1.0 + avg_mfe_rate)

    elif selection == TrainerCommander.BEST_AVG_MAE:
        # fitness performance x lower average MAE factor
        avg_mae_rate = get_stats(candidate, "percent.mae.avg")

        if avg_mae_rate is not None:
            # for MAE 0 is better -1 is worst
            fitness = -perf * (1.0 + avg_mae_rate)

    elif selection == TrainerCommander.BEST_AVG_ETD:
        # fitness performance x lower average ETD factor
        avg_etd_rate = get_stats(candidate, "percent.etd.avg")

        if avg_etd_rate is not None:
            # for ETD 0 is better -1 is worst
            fitness = -perf * (1.0 + avg_etd_rate)

    elif selection == TrainerCommander.BEST_STDDEV_MFE:
        # higher average MFE and the lower MFE std-dev
        std_mfe_rate = get_stats(candidate, "percent.mfe.std-dev")
        avg_mfe_rate = get_stats(candidate, "percent.mfe.avg")

        if std_mfe_rate is not None and avg_mfe_rate is not None and total_trades > 1:
            fitness = -p_n_minor(perf, -std_mfe_rate, total_trades, 0.95)

    elif selection == TrainerCommander.BEST_STDDEV_MAE:
        # lower average MAE and the lower MAE std-dev
        std_mae = get_stats(candidate, "percent.mae.std-dev")
        avg_mae_rate = get_stats(candidate, "percent.mae.avg")

        if std_mae is not None and avg_mae_rate is not None and total_trades > 1:
            fitness = -p_n_minor(perf, std_mae, total_trades, 0.95)

    elif selection == TrainerCommander.BEST_STDDEV_ETD:
        # lower average ETD and the lower ETD std-dev
        std_etd = get_stats(candidate, "percent.etd.std-dev")
        avg_etd_rate = get_stats(candidate, "percent.etd.avg")

        if std_etd is not None and avg_etd_rate is not None and total_trades > 1:
            fitness = -p_n_minor(perf, std_etd, total_trades, 0.95)

    elif selection == TrainerCommander.HIGHER_AVG_EEF:
        # fitness performance x higher average entry efficiency
        avg_eef_rate = get_stats(candidate, "percent.entry-efficiency.avg", min_value=-1.0, max_value=1.0)

        if avg_eef_rate is not None:
            fitness = -perf * (1.0 + avg_eef_rate)

    elif selection == TrainerCommander.HIGHER_AVG_XEF:
        # fitness performance x higher average exit efficiency
        avg_xef_rate = get_stats(candidate, "percent.exit-efficiency.avg", min_value=-1.0, max_value=1.0)

        if avg_xef_rate is not None:
            fitness = -perf * (1.0 + avg_xef_rate)

    elif selection == TrainerCommander.HIGHER_AVG_TEF:
        # fitness performance x higher average total (entry and exit) efficiency
        avg_tef_rate = get_stats(candidate, "percent.total-efficiency.avg", min_value=-1.0, max_value=1.0)

        if avg_tef_rate is not None:
            fitness = -perf * (1.0 + avg_tef_rate)

    elif selection == TrainerCommander.BEST_WIN_LOSS_RATE:
        # fitness performance x higher winning/loosing rate
        avg_win_loss_rate = get_stats(candidate, "percent.avg-win-loss-rate")

        if avg_win_loss_rate is not None:
            fitness = -perf * avg_win_loss_rate

    elif selection == TrainerCommander.BEST_SHARPE_RATIO:
        # higher Sharpe ratio
        sharpe_ratio = get_stats(candidate, "percent.sharpe-ratio")

        if sharpe_ratio is not None and not math.isnan(sharpe_ratio) and total_trades > 1:
            fitness = -p_n_major(perf, sharpe_ratio, total_trades, 0.95, 1.0)

    elif selection == TrainerCommander.BEST_SORTINO_RATIO:
        # higher Sortino ratio
        sortino_ratio = get_stats(candidate, "percent.sortino-ratio")

        if sortino_ratio is not None and not math.isnan(sortino_ratio) and total_trades > 1:
            fitness = -p_n_major(perf, sortino_ratio, total_trades, 0.95, 1.0)

    elif selection == TrainerCommander.BEST_ULCER_INDEX:
        # lower Ulcer index
        ulcer_index = get_stats(candidate, "percent.ulcer-index")

        if ulcer_index is not None and not math.isnan(ulcer_index) and total_trades > 1:
            fitness = -p_n_minor(perf, ulcer_index, total_trades, 0.95, 1.0)

    return fitness
