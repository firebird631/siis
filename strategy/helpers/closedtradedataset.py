# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy helper to get dataset

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def get_closed_trades(strategy):
    """
    Like as get_stats but only return the array of the trade, and complete history.
    """
    results = []

    with strategy._mutex:
        try:
            for k, strategy_trader in strategy._strategy_traders.items():
                with strategy_trader._mutex:
                    def append_trade(market_id, symbol, trades, trade):
                        trades.append({
                            'mid': market_id,
                            'sym': symbol,
                            'id': trade['id'],
                            'eot': trade['eot'],
                            'xot': trade['xot'],
                            'l': trade['l'],
                            'lreot': trade['lreot'],
                            'lrxot': trade['lrxot'],
                            'freot': trade['freot'],
                            'frxot': trade['frxot'],
                            'd': trade['d'],
                            'aep': trade['aep'],
                            'axp': trade['axp'],
                            'q': trade['q'],
                            'e': trade['e'],
                            'x': trade['e'],
                            'tp': trade['tp'],
                            'sl': trade['sl'],
                            'pl': trade['pl'],
                            'tf': trade['tf'],
                            's': trade['s'],
                            'c': trade['c'],
                            'b': trade['b'],
                            'bt': trade['bt'],
                            'w': trade['w'],
                            'wt': trade['wt'],
                            'label': trade['label'],
                            'fees': trade['fees'],
                            'rpnl': trade['rpnl'],
                            'pnlcur': trade['pnlcur']
                        })

                    for trade in strategy_trader._stats['success']:
                        append_trade(strategy_trader.instrument.market_id, strategy_trader.instrument.symbol, results, trade)

                    for trade in strategy_trader._stats['failed']:
                        append_trade(strategy_trader.instrument.market_id, strategy_trader.instrument.symbol, results, trade)

                    for trade in strategy_trader._stats['roe']:
                        append_trade(strategy_trader.instrument.market_id, strategy_trader.instrument.symbol, results, trade)

        except Exception as e:
            error_logger.error(repr(e))

    return results
