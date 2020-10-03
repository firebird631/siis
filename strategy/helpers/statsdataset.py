# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy helper to get dataset

from datetime import datetime

from terminal.terminal import Color
from terminal import charmap

from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def get_stats(strategy):
    """
    Generate and return an array of dict with the form :
        symbol: str name of the symbol/market
        pl: float current profit/loss rate 0 based
        perf: float total sum of profit/loss rate 0 based
        trades: list of dict of actives trades
            id: int trade identifier
            ts: float entry UTC timestamp
            d: str 'long' or 'short'
            l: str formatted order price
            aep: str formatted entry price
            axp: str formatted average exit price
            tp: str formatted take-profit price
            sl: str formatted stop-loss price
            pl: float profit/loss rate
            tfs: list of str timeframe generating the trade
            b: best hit price
            w: worst hit price
            bt: best hit price timestamp
            wt: worst hit price timestamp
            q: ordered qty
            e: executed entry qty
            x: executed exit qty
            label: trade label
            upnl: trade unrealized profit loss
            pnlcur: trade profit loss currency
    """
    results = []

    trader = strategy.trader()

    with strategy._mutex:
        try:
            for k, strategy_trader in strategy._strategy_traders.items():
                profit_loss = 0.0
                trades = []
                perf = 0.0

                with strategy_trader._mutex:
                    perf = strategy_trader._stats['perf']
                    best = strategy_trader._stats['best']
                    worst = strategy_trader._stats['worst']

                    success = len(strategy_trader._stats['success'])
                    failed = len(strategy_trader._stats['failed'])
                    roe = len(strategy_trader._stats['roe'])

                    market = trader.market(strategy_trader.instrument.market_id) if trader else None
                    for trade in strategy_trader.trades:
                        trade_pl = trade.estimate_profit_loss(strategy_trader.instrument)

                        trades.append({
                            'id': trade.id,
                            'eot': trade.entry_open_time,
                            'd': trade.direction_to_str(),
                            'l': strategy_trader.instrument.format_price(trade.order_price),
                            'aep': strategy_trader.instrument.format_price(trade.entry_price),
                            'axp': strategy_trader.instrument.format_price(trade.exit_price),
                            'q': strategy_trader.instrument.format_quantity(trade.order_quantity),
                            'e': strategy_trader.instrument.format_quantity(trade.exec_entry_qty),
                            'x': strategy_trader.instrument.format_quantity(trade.exec_exit_qty),
                            'tp': strategy_trader.instrument.format_price(trade.take_profit),
                            'sl': strategy_trader.instrument.format_price(trade.stop_loss),
                            'pl': trade_pl,
                            'tf': timeframe_to_str(trade.timeframe),
                            's': trade.state_to_str(),
                            'b': strategy_trader.instrument.format_price(trade.best_price()),
                            'w': strategy_trader.instrument.format_price(trade.worst_price()),
                            'bt': trade.best_price_timestamp(),
                            'wt': trade.worst_price_timestamp(),
                            'label': trade.label,
                            'upnl': "%.f" % trade.unrealized_profit_loss,
                            'pnlcur': trade.profit_loss_currency
                        })

                        profit_loss += trade_pl

                results.append({
                    'mid': strategy_trader.instrument.market_id,
                    'sym': strategy_trader.instrument.symbol,
                    'pl': profit_loss,
                    'perf': perf,
                    'trades': trades,
                    'best': best,
                    'worst': worst,
                    'success': success,
                    'failed': failed,
                    'roe': roe
                })
        except Exception as e:
            error_logger.error(repr(e))

    return results
