# @date 2018-08-24
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# Strategy helper to get dataset

from datetime import datetime

from terminal.terminal import Color
from terminal import charmap

from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def get_agg_trades(strategy):
    """
    Generate and return an array of :
        mid: str name of the market id
        sym: str name of the symbol
        pl: flaot profit/loss rate
        perf: perf
        worst: worst
        best: best
        success: success
        failed: failed
        roe: roe
    """
    results = []
    trader = strategy.trader()

    with strategy._mutex:
        try:
            for k, strategy_trader in strategy._strategy_traders.items():
                pl = 0.0
                perf = 0.0

                with strategy_trader._mutex:
                    perf = strategy_trader._stats['perf']
                    best = strategy_trader._stats['best']
                    worst = strategy_trader._stats['worst']

                    success = len(strategy_trader._stats['success'])
                    failed = len(strategy_trader._stats['failed'])
                    roe = len(strategy_trader._stats['roe'])

                    mid = strategy_trader.instrument.market_id
                    sym = strategy_trader.instrument.symbol

                    num = len(strategy_trader.trades)

                    for trade in strategy_trader.trades:
                        pl += trade.estimate_profit_loss(strategy_trader.instrument)

                if pl != 0.0 or num > 0 or success > 0 or failed > 0 or roe > 0:
                    results.append({
                        'mid': mid,
                        'sym': sym,
                        'pl': pl,
                        'perf': perf,
                        'best': best,
                        'worst': worst,
                        'success': success,
                        'failed': failed,
                        'roe': roe
                    })
        except Exception as e:
            error_logger.error(repr(e))

    return results
