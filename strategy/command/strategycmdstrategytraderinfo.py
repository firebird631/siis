# @date 2018-08-24
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2018 Dream Overflow
# Strategy command trader info

def cmd_strategy_trader_info(strategy, strategy_trader, data):
    """
    Get strategy-trader info or specific element if detail defined.
    """        
    results = {
        'messages': [],
        'error': False
    }

    detail = data.get('detail', "")
    region_id = -1

    if detail == "region":
        try:
            region_id = int(data.get('region-id'))
        except ValueError:
            results['error'] = True
            results['messages'].append("Invalid region identifier")

    if results['error']:
        return results

    with strategy_trader._mutex:
        if detail == "region":
            if region_id >= 0:
                region = None

                for r in strategy_trader.regions:
                    if r.id == region_id:
                        region = r
                        break

                if region:
                    results['messages'].append("Strategy trader %s region details:" %
                                               strategy_trader.instrument.market_id)
                    results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))
                else:
                    results['error'] = True
                    results['messages'].append("Invalid region identifier %i" % region_id)

            else:
                results['messages'].append("Strategy trader %s, list %i regions:" % (
                    strategy_trader.instrument.market_id, len(strategy_trader.regions)))

                for region in strategy_trader.regions:
                    results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))

        elif detail == "alert":
            # @todo
            pass

        elif detail == "status":
            # status
            results['messages'].append("Activity : %s" % ("enabled" if strategy_trader.activity else "disabled"))

        elif not detail or detail == "details":
            # no specific detail
            results['messages'].append("Strategy trader %s details:" % strategy_trader.instrument.market_id)

            # status
            results['messages'].append("Activity : %s" % ("enabled" if strategy_trader.activity else "disabled"))

            # quantity
            results['messages'].append("Instrument trade quantity : %s, mode is %s" % (
                strategy_trader.instrument.trade_quantity,
                strategy_trader.instrument.trade_quantity_mode_to_str()
            ))

            total_qty = 0.0
            total_margin = 0.0
            total_contract = 0.0

            # for asset, count total for active trades
            with strategy_trader._trade_mutex:
                for trade in strategy_trader._trades:
                    if trade.is_active():
                        if trade.trade_type == trade.TRADE_ASSET:
                            total_qty += trade.e - trade.x
                        elif trade.trade_type == trade.TRADE_MARGIN or trade.trade_type == trade.TRADE_IND_MARGIN:
                            total_margin += trade.invested_quantity
                        elif trade.trade_type == trade.TRADE_POSITION:
                            total_contract += trade.e - trade.x

            if total_qty:
                total_qty = strategy_trader.instrument.adjust_quantity(total_qty)

            if total_margin:
                total_margin = strategy_trader.instrument.adjust_quote(total_margin)

            if total_qty > 0.0:
                free_qty = -1.0

                trader = strategy.trader()
                if trader:
                    asset = trader.asset(strategy_trader.instrument.base)
                    if asset:
                        free_qty = asset.quantity - total_qty

                results['messages'].append("In trades asset quantity : %s" % total_qty)

                if free_qty >= 0.0:
                    results['messages'].append("Expected free asset quantity : %s" % free_qty)
                else:
                    results['messages'].append("Unable to compute the expected free asset quantity")

            if total_margin > 0.0:
                results['messages'].append("In trades involved margin : %s" % total_margin)

            if total_contract > 0.0:
                results['messages'].append("In trades involved contracts : %s" % total_contract)

            # regions
            if len(strategy_trader.regions):
                results['messages'].append("-----")
                results['messages'].append("List %i regions:" % len(strategy_trader.regions))

                for region in strategy_trader.regions:
                    results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))
        else:
            results['error'] = True
            results['messages'].append("Invalid detail type name %s" % detail)

    return results
