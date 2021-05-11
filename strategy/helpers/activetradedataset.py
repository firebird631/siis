# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy helper to get dataset

from common.utils import timeframe_to_str

import logging
logger = logging.getLogger('siis.strategy')
error_logger = logging.getLogger('siis.error.strategy')


def get_all_active_trades(strategy):
    """
    Generate and return an array of all the actives trades :
        symbol: str market identifier
        id: int trade identifier
        eot: float first entry open UTC timestamp
        xot: float first exit open UTC timestamp
        freot: float first realized trade in entry UTC timestamp
        frxot: float firest realized trade in exit UTC timestamp
        lreot: float last realized trade in entry UTC timestamp
        lrxot: float last realized trade in exit UTC timestamp
        d: str 'long' or 'short'
        l: str formatted order price
        tp: str formatted take-profit price
        sl: str formatted stop-loss price
        rate: float profit/loss rate
        tfs: list of str timeframe generating the trade
        b: best hit price
        w: worst hit price
        bt: best hit price timestamp
        wt: worst hit price timestamp
        q: ordered qty
        e: executed entry qty
        x: executed exit qty
        aep: average entry price
        axp: average exit price
        label: trade label
        upnl: trade unrealized profit loss
        pnlcur: trade profit loss currency
        fees: total fees rate (entry+exit)
        leop : last exec open price
    """
    results = []
    trader = strategy.trader()

    with strategy._mutex:
        try:
            for k, strategy_trader in strategy._strategy_traders.items():
                with strategy_trader._mutex:
                    for trade in strategy_trader.trades:
                        profit_loss = trade.estimate_profit_loss(strategy_trader.instrument)

                        results.append({
                            'mid': strategy_trader.instrument.market_id,
                            'sym': strategy_trader.instrument.symbol,
                            'id': trade.id,
                            'eot': trade.entry_open_time,
                            'xot': trade.exit_open_time,
                            'freot': trade.first_realized_entry_time,
                            'frxot': trade.first_realized_exit_time,
                            'lreot': trade.last_realized_entry_time,
                            'lrxot': trade.last_realized_exit_time,
                            'd': trade.direction_to_str(),
                            'l': strategy_trader.instrument.format_price(trade.order_price),
                            'aep': strategy_trader.instrument.format_price(trade.entry_price),
                            'axp': strategy_trader.instrument.format_price(trade.exit_price),
                            'q': strategy_trader.instrument.format_quantity(trade.order_quantity),
                            'e': strategy_trader.instrument.format_quantity(trade.exec_entry_qty),
                            'x': strategy_trader.instrument.format_quantity(trade.exec_exit_qty),
                            'tp': strategy_trader.instrument.format_price(trade.take_profit),
                            'sl': strategy_trader.instrument.format_price(trade.stop_loss),
                            'tf': timeframe_to_str(trade.timeframe),
                            's': trade.state_to_str(),
                            'b': strategy_trader.instrument.format_price(trade.best_price()),
                            'w': strategy_trader.instrument.format_price(trade.worst_price()),
                            'bt': trade.best_price_timestamp(),
                            'wt': trade.worst_price_timestamp(),
                            'label': trade.label,
                            'pl': profit_loss,
                            'upnl': strategy_trader.instrument.format_price(trade.unrealized_profit_loss),
                            'pnlcur': trade.profit_loss_currency,
                            'fees': trade.entry_fees_rate() + trade.estimate_exit_fees_rate(strategy_trader.instrument),
                            'leop': strategy_trader.instrument.format_price(strategy_trader.instrument.open_exec_price(trade.direction)),
                        })
        except Exception as e:
            error_logger.error(repr(e))

    return results
