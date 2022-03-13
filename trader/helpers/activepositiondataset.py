# @date 2022-03-13
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2022 Dream Overflow
# Trader dataset to display table for views and formatters

import logging
import traceback

logger = logging.getLogger('siis.trader')
error_logger = logging.getLogger('siis.error.trader')
traceback_logger = logging.getLogger('siis.traceback.trader')


def get_active_positions(trader):
    """
    Generate and return an array of all active positions :
        symbol: str market identifier
        id: int position identifier
        et: float entry UTC timestamp
        xt: float exit UTC timestamp
        d: str 'long' or 'short'
        l: str leverage
        tp: str formatted take-profit price
        sl: str formatted stop-loss price
        tr: str trailing stop distance or None
        rate: float profit/loss rate
        q: float size qty
        aep: average entry price
        axp: average exit price
        pl: position unrealized profit loss rate
        pnl: position unrealized profit loss
        mpl: position unrealized profit loss rate at market
        mpnl: position unrealized profit loss at market
        pnlcur: trade profit loss currency
        key: user key
    """
    results = []

    with trader.mutex:
        try:
            for k, position in trader._positions.items():
                market = trader._markets.get(position.symbol)
                if market:
                    results.append({
                        'mid': market.market_id,
                        'sym': market.symbol,
                        'id': position.position_id,
                        'et': position.created_time,
                        'xt': position.closed_time,
                        'd': position.direction_to_str(),
                        'l': position.leverage,
                        'aep': market.format_price(position.entry_price) if position.entry_price else "",
                        'axp': market.format_price(position.exit_price) if position.exit_price else "",
                        'q': market.format_quantity(position.quantity),
                        'tp': market.format_price(position.take_profit) if position.take_profit else "",
                        'sl': market.format_price(position.stop_loss) if position.stop_loss else "",
                        'tr': "Yes" if position.trailing_stop else "No",
                        # 'tr-dist': market.format_price(position.trailing_stop_distance) if position.trailing_stop_distance else None,
                        'pl': position.profit_loss_rate,
                        'pnl': market.format_price(position.profit_loss),
                        'mpl': position.profit_loss_market_rate,
                        'mpnl': market.format_price(position.profit_loss_market),
                        'pnlcur': position.profit_loss_currency,
                        'cost': market.format_quantity(position.position_cost(market)),
                        'margin': market.format_quantity(position.margin_cost(market)),
                        'key': position.key
                    })
        except Exception as e:
            error_logger.error(repr(e))
            traceback_logger.error(traceback.format_exc())

    return results
