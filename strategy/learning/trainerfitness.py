# @date 2023-04-11
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2023 Dream Overflow
# Trainer fitness adjustment methods implementations

from __future__ import annotations

import logging
import math

logger = logging.getLogger('siis.tools.trainerfitness')
error_logger = logging.getLogger('siis.tools.error.trainerfitness')
traceback_logger = logging.getLogger('siis.tools.traceback.trainerfitness')


def get_stats(parent: dict, path: str, default=None, min_value=None, max_value=None):
    root = parent

    tokens = path.split('.')
    for token in tokens:
        if token in root:
            root = root[token]
        else:
            return default

    if type(root) is str:
        try:
            if root.endswith('%'):
                v = float(root[:-1]) * 0.01
            else:
                v = float(root)
        except ValueError:
            return default
    else:
        v = root

    if min_value is not None and max_value is not None:
        v = min(max_value, max(min_value, v))
    elif min_value is not None:
        v = max(min_value, v)
    if max_value is not None:
        v = min(max_value, v)

    return v


def trainer_fitness(candidate: dict, selection: int):
    """
    Adjust the fitness result according to the selection method.
    @param candidate: dict with complete result set
    @param selection: TrainerCommander selection mode
    @return: float adjusted fitness
    """
    from strategy.learning.trainer import TrainerCommander

    if not candidate:
        return 0.0

    perf = get_stats(candidate, 'performance')

    # default to best performance
    fitness = -perf

    # fitness adjustment according to the selection method
    if selection == TrainerCommander.BEST_WINRATE:
        # fitness is global performance multiply by best win-rate
        succeed = get_stats(candidate, 'succeed-trades', 0)
        total_trades = get_stats(candidate, 'total-trades', 0)

        sf_rate = succeed / total_trades if total_trades > 0 else 0.0

        if sf_rate < 0.45:
            # poor win rate, penalty
            fitness = 9999
        else:
            fitness = -(perf * ((0.55 + sf_rate) ** 2))

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

        if tp_win_rate < 0.45:
            fitness = 9999
        else:
            fitness = -(perf * ((0.55 + tp_win_rate) ** 2))

    elif selection == TrainerCommander.HIGHER_AVG_MFE:
        # fitness performance x higher average MFE factor
        avg_mfe_rate = get_stats(candidate, "percent.mfe.avg")

        if avg_mfe_rate is not None:
            fitness = -perf * avg_mfe_rate

    elif selection == TrainerCommander.LOWER_AVG_MAE:
        # fitness performance x lower average MAE factor
        avg_mae_rate = get_stats(candidate, "percent.mae.avg")

        if avg_mae_rate is not None:
            fitness = -perf * math.pow(1.0 - avg_mae_rate, 2)

    elif selection == TrainerCommander.LOWER_AVG_ETD:
        # fitness performance x lower average ETD factor
        avg_etd_rate = get_stats(candidate, "percent.etd.avg")

        if avg_etd_rate is not None:
            fitness = -perf * math.pow(1.0 - avg_etd_rate, 2)

    elif selection == TrainerCommander.BEST_STDDEV_MFE:
        # higher average MFE and the lower MFE std-dev
        std_mfe_rate = get_stats(candidate, "percent.mfe.std-dev")
        avg_mfe_rate = get_stats(candidate, "percent.mfe.avg")

        if std_mfe_rate is not None and avg_mfe_rate is not None:
            fitness = -perf * (avg_mfe_rate / std_mfe_rate)

    elif selection == TrainerCommander.BEST_STDDEV_MAE:
        # lower average MAE and the lower MAE std-dev
        std_mae_rate = get_stats(candidate, "percent.mae.std-dev")
        avg_mae_rate = get_stats(candidate, "percent.mae.avg")

        if std_mae_rate is not None and avg_mae_rate is not None:
            fitness = -perf * (avg_mae_rate / std_mae_rate)

    elif selection == TrainerCommander.BEST_STDDEV_ETD:
        # lower average ETD and the lower ETD std-dev
        std_etd_rate = get_stats(candidate, "percent.etd.std-dev")
        avg_etd_rate = get_stats(candidate, "percent.etd.avg")

        if std_etd_rate is not None and avg_etd_rate is not None:
            fitness = -perf * (avg_etd_rate / std_etd_rate)

    elif selection == TrainerCommander.HIGHER_AVG_EEF:
        # fitness performance x higher average entry efficiency
        avg_eef_rate = get_stats(candidate, "percent.entry-efficiency.avg", min_value=-1.0, max_value=1.0)

        # @todo issue perf negative avec rate positive => fitness negatif
        if avg_eef_rate is not None:
            fitness = -perf * avg_eef_rate

    elif selection == TrainerCommander.HIGHER_AVG_XEF:
        # fitness performance x higher average exit efficiency
        avg_xef_rate = get_stats(candidate, "percent.exit-efficiency.avg", min_value=-1.0, max_value=1.0)

        if avg_xef_rate is not None:
            fitness = -perf * avg_xef_rate

    elif selection == TrainerCommander.HIGHER_AVG_TEF:
        # fitness performance x higher average total (entry and exit) efficiency
        avg_tef_rate = get_stats(candidate, "percent.total-efficiency.avg", min_value=-1.0, max_value=1.0)

        if avg_tef_rate is not None:
            fitness = -perf * avg_tef_rate

    elif selection == TrainerCommander.BEST_WIN_LOSS_RATE:
        # fitness performance x higher winning/loosing rate
        avg_win_loss_rate = get_stats(candidate, "percent.avg-win-loss-rate")

        if avg_win_loss_rate is not None:
            fitness = -perf * avg_win_loss_rate

    return fitness
