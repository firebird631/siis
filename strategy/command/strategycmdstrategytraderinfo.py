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
        except Exception:
            results['error'] = True
            results['messages'].append("Invalid region identifier")

    if results['error']:
        return results

    trade = None

    with strategy_trader._mutex:
        if detail == "region":
            if region_id >= 0:
                region = None

                for r in strategy_trader.regions:
                    if r.id == region_id:
                        region = r
                        break

                if region:
                    results['messages'].append("Stragegy trader %s region details:" % strategy_trader.instrument.market_id)
                    results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))
                else:
                    results['error'] = True
                    results['messages'].append("Invalid region identifier %i" % region_id)

            else:
                results['messages'].append("Stragegy trader %s, list %i regions:" % (strategy_trader.instrument.market_id, len(strategy_trader.regions)))

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
            results['messages'].append("Stragegy trader %s details:" % strategy_trader.instrument.market_id)

            # status
            results['messages'].append("Activity : %s" % ("enabled" if strategy_trader.activity else "disabled"))

            # quantity
            results['messages'].append("Trade quantity : %s, max factor is x%s, mode is %s" % (
                strategy_trader.instrument.trade_quantity,
                strategy_trader.instrument.trade_max_factor,
                strategy_trader.instrument.trade_quantity_mode_to_str()
            ))

            # regions
            results['messages'].append("List %i regions:" % len(strategy_trader.regions))

            for region in strategy_trader.regions:
                results['messages'].append(" - #%i: %s" % (region.id, region.str_info()))
        else:
            results['error'] = True
            results['messages'].append("Invalid detail type name %s" % detail)

    return results
