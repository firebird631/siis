# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy helper to get dataset

import logging
logger = logging.getLogger('siis.strategy.helpers.aggtradedataset')
error_logger = logging.getLogger('siis.error.strategy.helpers.aggtradedataset')


def get_agg_trades(strategy):
    """
    Generate and return an array of :
        mid: str name of the market id
        sym: str name of the symbol
        pl: float profit/loss rate
        perf: perf
        worst: worst
        best: best
        success: success
        failed: failed
        roe: roe
    """
    results = []

    with strategy._mutex:
        try:
            for k, strategy_trader in strategy._strategy_traders.items():
                pl = 0.0
                perf = 0.0

                with strategy_trader._mutex:
                    perf = strategy_trader._stats['perf']
                    best = strategy_trader._stats['best']
                    worst = strategy_trader._stats['worst']

                    high = strategy_trader._stats['high']
                    low = strategy_trader._stats['low']
                    closed = strategy_trader._stats['closed']

                    rpnl = strategy_trader.instrument.adjust_quote(strategy_trader._stats['rpnl'])

                    success = len(strategy_trader._stats['success'])
                    failed = len(strategy_trader._stats['failed'])
                    roe = len(strategy_trader._stats['roe'])

                    mid = strategy_trader.instrument.market_id
                    sym = strategy_trader.instrument.symbol

                    num_trades = len(strategy_trader.trades)
                    num_actives_trades = 0

                    for trade in strategy_trader.trades:
                        # current UPNL %
                        pl += trade.estimate_profit_loss(strategy_trader.instrument)

                        if trade.is_active():
                            num_actives_trades += 1

                if pl != 0.0 or num_trades > 0 or success > 0 or failed > 0 or roe > 0:
                    results.append({
                        'mid': mid,
                        'sym': sym,
                        'pl': pl,
                        'num-open-trades': len(strategy_trader.trades),
                        'perf': perf,
                        'best': best,
                        'worst': worst,
                        'success': success,
                        'failed': failed,
                        'roe': roe,
                        'high': high,
                        'low': low,
                        'num-closed-trades': closed,
                        'rpnl': rpnl,
                        'rpnl-currency': strategy_trader.instrument.quote,
                        'num-actives-trades': num_actives_trades
                    })
        except Exception as e:
            error_logger.error(repr(e))

    return results
