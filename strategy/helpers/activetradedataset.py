# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy helper to get dataset

# from typing import TYPE_CHECKING
#
# if TYPE_CHECKING:
#     from strategy.strategy import Strategy

import traceback

from common.utils import timeframe_to_str

import logging


logger = logging.getLogger('siis.strategy.helpers.activetradedataset')
error_logger = logging.getLogger('siis.error.strategy.helpers.activetradedataset')


def fmt_pips(value):
    return ("%.2f" % value).rstrip('0').rstrip('.')


def get_all_active_trades(strategy):
    """
    Generate and return an array of all the actives trades :
        symbol: str market identifier
        id: int trade identifier
        eot: float first entry open UTC timestamp
        xot: float first exit open UTC timestamp
        freot: float first realized trade in entry UTC timestamp
        frxot: float first realized trade in exit UTC timestamp
        lreot: float last realized trade in entry UTC timestamp
        lrxot: float last realized trade in exit UTC timestamp
        d: str 'long' or 'short'
        l: str formatted order price
        tp: str formatted take-profit price
        sl: str formatted stop-loss price
        rate: float profit/loss rate
        tfs: list of str timeframe generating the trade
        b: best hit price (MFE)
        w: worst hit price (MAE)
        bt: best hit price timestamp
        wt: worst hit price timestamp
        q: ordered quantity
        e: executed entry quantity
        x: executed exit quantity
        aep: average entry price
        axp: average exit price
        label: trade label
        upnl: trade unrealized profit loss
        pnlcur: trade profit loss currency
        fees: total fees rate (entry+exit+funding+commissions)
        loep : last exec open price
        lcep : last exec close price
        stop-loss-dist-pips: distance in pip from stop and entry price,
        take-profit-dist-pips: distance in pip from take-profit and entry price,
        entry-dist-pips: distance in pips from entry and last price
        order-dist-pips: distance in pips from order price and last price
        mae-dist-pips: distance in pips from entry price and worst price
        mfe-dist-pips: distance in pips from entry price and best price
        etd-dist-pips: distance in pips from MFE and last price
    """
    results = []

    with strategy.mutex:
        try:
            for k, strategy_trader in strategy.strategy_traders.items():
                with strategy_trader.mutex:
                    for trade in strategy_trader.trades:
                        pip_means = strategy_trader.instrument.one_pip_means

                        profit_loss_rate = trade.estimate_profit_loss_rate(strategy_trader.instrument)

                        if trade.entry_price or trade.order_price:
                            sl_dist_pips = (trade.direction * (trade.stop_loss - (
                                    trade.entry_price or trade.order_price))) / pip_means
                            tp_dist_pips = (trade.direction * (trade.take_profit - (
                                    trade.entry_price or trade.order_price))) / pip_means

                            entry_dist_pips = (trade.direction * (strategy_trader.instrument.open_exec_price(
                                trade.direction) - trade.entry_price)) / pip_means if trade.entry_price else 0.0
                            order_dist_pips = (trade.direction * (strategy_trader.instrument.open_exec_price(
                                trade.direction) - trade.order_price)) / pip_means if trade.order_price else 0.0
                        else:
                            sl_dist_pips = 0.0
                            tp_dist_pips = 0.0
                            entry_dist_pips = 0.0
                            order_dist_pips = 0.0

                        if trade.entry_price:
                            mfe_dist_pips = trade.direction * (trade.best_price() - trade.entry_price) / pip_means
                            mae_dist_pips = trade.direction * (trade.worst_price() - trade.entry_price) / pip_means
                        else:
                            mae_dist_pips = 0.0
                            mfe_dist_pips = 0.0

                        etd = trade.direction * (
                                strategy_trader.instrument.close_exec_price(trade.direction) - trade.best_price())
                        etd_dist_pips = min(0.0, etd) / pip_means

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
                            'etd': strategy_trader.instrument.format_price(etd),
                            'label': trade.label,
                            'pl': profit_loss_rate,
                            'upnl': strategy_trader.instrument.format_settlement(trade.unrealized_profit_loss),
                            'pnlcur': trade.profit_loss_currency,
                            'fees': trade.entry_fees_rate() + trade.margin_fees_rate() + trade.estimate_exit_fees_rate(strategy_trader.instrument),
                            'loep': strategy_trader.instrument.format_price(strategy_trader.instrument.open_exec_price(trade.direction)),
                            'lcep': strategy_trader.instrument.format_price(strategy_trader.instrument.close_exec_price(trade.direction)),
                            'qs': strategy_trader.instrument.format_quote(trade.invested_quantity),
                            'stop-loss-dist-pips': fmt_pips(sl_dist_pips),
                            'take-profit-dist-pips': fmt_pips(tp_dist_pips),
                            'entry-dist-pips': fmt_pips(entry_dist_pips),
                            'order-dist-pips': fmt_pips(order_dist_pips),
                            'mae-dist-pips': fmt_pips(mae_dist_pips),
                            'mfe-dist-pips': fmt_pips(mfe_dist_pips),
                            'etd-dist-pips': fmt_pips(etd_dist_pips)
                        })
        except Exception as e:
            error_logger.error(repr(e))
            error_logger.error(traceback.format_exc())

    return results
