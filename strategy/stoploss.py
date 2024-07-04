# @date 2019-09-12
# @author Frederic Scherma, All rights reserved without prejudices.
# @license Copyright (c) 2019 Dream Overflow
# Base strategy stop loss methods

import numpy as np

from .strategytradercontext import StrategyTraderContext


def search_std_atrsr(direction, sub, orientation, depth, price, epsilon=0.0):
    if not sub.atrsr:
        return 0.0

    if orientation > 0:
        return sub.atrsr.search_up(direction, price, depth, epsilon)
    elif orientation < 0:
        return sub.atrsr.search_down(direction, price, depth, epsilon)
    else:
        return sub.atrsr.search_both(direction, price, depth, epsilon)


def search_sorted_atrsr(direction, sub, orientation, depth, price, epsilon=0.0):
    if not sub.atrsr:
        return 0.0

    if orientation > 0:
        return sub.atrsr.search_sorted_up(direction, price, depth, epsilon)
    elif orientation < 0:
        return sub.atrsr.search_sorted_down(direction, price, depth, epsilon)
    else:
        return sub.atrsr.search_sorted_both(direction, price, depth, epsilon)


search_atrsr = search_std_atrsr
# search_atrsr = search_sorted_atrsr


def compute_stop_loss(direction, data, sub, entry_price, confidence=1.0, price_epsilon=0.0):
    """
    Branching to the predefined stop-loss method.
    """
    def compute_distance():
        if direction > 0:
            # never larger than distance in percent if defined
            if data.stop_loss.distance_type == StrategyTraderContext.DIST_PERCENTILE:
                return entry_price * (1.0 - data.stop_loss.distance)
            elif data.stop_loss.distance_type == StrategyTraderContext.DIST_PRICE:
                return entry_price - data.stop_loss.distance

        elif direction < 0:
            # never larger than distance in percent if defined
            if data.stop_loss.distance_type == StrategyTraderContext.DIST_PERCENTILE:
                return entry_price * (1.0 + data.stop_loss.distance)
            elif data.stop_loss.distance_type == StrategyTraderContext.DIST_PRICE:
                return entry_price + data.stop_loss.distance

            return 0.0

    if direction > 0:
        min_dist = 1.0 - data.min_profit

        if data.stop_loss.type == data.PRICE_NONE:
            return 0.0

        elif data.stop_loss.type == data.PRICE_ATR_SR:
            atr_stop_loss = search_atrsr(-direction, sub, data.stop_loss.orientation,
                                         data.stop_loss.depth, entry_price, price_epsilon)

            if data.stop_loss.distance > 0.0:
                # never larger than distance in percent if defined
                distance_stop_loss = compute_distance()

                # if no ATR found return the fixed one, else return the higher
                if atr_stop_loss <= 0.0:
                    return distance_stop_loss

                return max(atr_stop_loss, distance_stop_loss)

            return atr_stop_loss

        elif data.stop_loss.type == data.PRICE_CUR_ATR_SR:
            curatr_stop_loss = sub.atrsr.cur_down

            if data.stop_loss.distance > 0.0:
                # never larger than distance in percent if defined
                distance_stop_loss = compute_distance()

                # if no current ATR return the fixed one, else return the higher
                if curatr_stop_loss <= 0.0:
                    return distance_stop_loss

                return max(curatr_stop_loss, distance_stop_loss)

            return curatr_stop_loss

        elif data.stop_loss.type == data.PRICE_BOLLINGER:
            lmin = entry_price
            lmax = 0.0

            n = int(20 * confidence)

            for p in sub.bollinger.bottoms[-n:]:
                if not np.isnan(p) and p > 0.0 and p < entry_price:
                    lmax = max(lmax, p)
                    lmin = min(lmin, p)

            #return min((lmax + lmin) * 0.5, entry_price * (1.0 - data.stop_loss.distance))
            return min((entry_price + lmin) * 0.5, entry_price * min_dist)

        elif data.stop_loss.type == data.PRICE_FIXED and data.stop_loss.distance > 0.0:
            if data.stop_loss.distance_type == data.DIST_PERCENTILE:
                return entry_price * (1.0 - data.stop_loss.distance)
            elif data.stop_loss.distance_type == data.DIST_PRICE:
                return entry_price - data.stop_loss.distance

    elif direction < 0:
        min_dist = 1.0 + data.min_profit

        if data.stop_loss.type == data.PRICE_NONE:
            return 0.0

        elif data.stop_loss.type == data.PRICE_ATR_SR:
            atr_stop_loss = search_atrsr(-direction, sub, -data.stop_loss.orientation,
                                         data.stop_loss.depth, entry_price, price_epsilon)

            if data.stop_loss.distance > 0.0:
                # never larger than distance in percent if defined
                distance_stop_loss = compute_distance()

                if atr_stop_loss <= 0.0:
                    # if no ATR found return the fixed one
                    return distance_stop_loss

                return min(atr_stop_loss, distance_stop_loss)

            return atr_stop_loss

        elif data.stop_loss.type == data.PRICE_CUR_ATR_SR:
            curatr_stop_loss = sub.atrsr.cur_up

            if data.stop_loss.distance > 0.0:
                # never larger than distance in percent if defined
                distance_stop_loss = compute_distance()

                if curatr_stop_loss <= 0.0:
                    # if no current ATR return the fixed one
                    return distance_stop_loss

                return min(curatr_stop_loss, distance_stop_loss)

            return curatr_stop_loss

        elif data.stop_loss.type == data.PRICE_BOLLINGER:
            lmin = entry_price
            lmax = 0.0

            n = int(20 * confidence)

            for p in sub.bollinger.tops[-n:]:
                if not np.isnan(p) and p > 0.0 and p > entry_price:
                    lmax = max(lmax, p)
                    lmin = min(lmin, p)

            return max((lmax - entry_price) * 0.5, entry_price * min_dist)

        elif data.stop_loss.type == data.PRICE_FIXED and data.stop_loss.distance > 0.0:
            if data.stop_loss.distance_type == data.DIST_PERCENTILE:
                return entry_price * (1.0 + data.stop_loss.distance)
            elif data.stop_loss.distance_type == data.DIST_PRICE:
                return entry_price + data.stop_loss.distance

    return 0.0


def dynamic_stop_loss_fixed_bollinger_long(sub, last_price, curr_stop_loss_price, price_epsilon=0.0):
    stop_loss = 0.0

    #if sub.bollinger and sub.bollinger.bottoms is not None and len(sub.bollinger.bottoms) > 0:
    if sub.bollinger and sub.bollinger.tops is not None and len(sub.bollinger.tops) > 0:
        if 1:  # sub.last_closed:
            #p = sub.bollinger.bottoms[-1]
            p = sub.bollinger.tops[-1]

            if p > curr_stop_loss_price and p < last_price - price_epsilon:
                stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_bollinger_short(sub, last_price, curr_stop_loss_price, price_epsilon=0.0):
    stop_loss = 0.0

    #if sub.bollinger and sub.bollinger.tops is not None and len(sub.bollinger.tops) > 0:
    if sub.bollinger and sub.bollinger.bottoms is not None and len(sub.bollinger.bottoms) > 0:
        if 1:  # sub.last_closed:
            # p = sub.bollinger.tops[-1]
            p = sub.bollinger.bottoms[-1]

            if p < curr_stop_loss_price and p > last_price + price_epsilon:
                stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_pct_long(sub, last_price, curr_stop_loss_price, distance):
    stop_loss = 0.0

    p = last_price * (1.0 - distance)

    if p > curr_stop_loss_price and p < last_price:
        stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_pct_short(sub, last_price, curr_stop_loss_price, distance):
    stop_loss = 0.0

    p = last_price * (1.0 + distance)

    if p < curr_stop_loss_price and p > last_price:
        stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_dist_long(sub, last_price, curr_stop_loss_price, distance):
    stop_loss = 0.0

    p = last_price - distance

    if p > curr_stop_loss_price and p < last_price:
        stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_dist_short(sub, last_price, curr_stop_loss_price, distance):
    stop_loss = 0.0

    p = last_price + distance

    if p < curr_stop_loss_price and p > last_price:
        stop_loss = p

    return stop_loss


def dynamic_stop_loss_atrsr_long(sub, last_price, curr_stop_loss_price, depth, orientation, price_epsilon=0.0):
    # search in long direction because be want a price greater than actual stop loss but we keep it only
    # if lesser than current close price
    # stop_loss = search_atrsr(1, sub, orientation, depth, curr_stop_loss_price, price_epsilon)

    # if stop_loss < last_price - price_epsilon:
    #     return stop_loss

    # return 0.0

    # or simply
    stop_loss = search_atrsr(-1, sub, orientation, depth, last_price, 0)  # price_epsilon)

    if stop_loss < last_price - price_epsilon and stop_loss > curr_stop_loss_price:
        return stop_loss

    return 0.0


def dynamic_stop_loss_atrsr_short(sub, last_price, curr_stop_loss_price, depth, orientation, price_epsilon=0.0):
    # reverse explanation of the long version
    # stop_loss = search_atrsr(-1, sub, -orientation, depth, curr_stop_loss_price, price_epsilon)

    # if stop_loss > last_price + price_epsilon:
    #     return stop_loss

    # return 0.0

    # or simply (revert orientation)
    stop_loss = search_atrsr(1, sub, -orientation, depth, last_price, 0)  # price_epsilon)

    if stop_loss > last_price + price_epsilon and stop_loss < curr_stop_loss_price:
        return stop_loss

    return 0.0


def dynamic_stop_loss_cur_atrsr_long(sub, entry_price, last_price, curr_stop_loss_price,
                                     depth, orientation, price_epsilon=0.0):
    stop_loss = 0.0

    if sub.atrsr and len(sub.atrsr._tdn):
        if sub.atrsr._tdn[-1] > curr_stop_loss_price and sub.atrsr._tdn[-1] < last_price:
            stop_loss = sub.atrsr._tdn[-1]

    # if sub.atrsr and len(sub.atrsr._tup):
    #     if sub.atrsr._tup[-1] > curr_stop_loss_price and sub.atrsr._tup[-1] < last_price:
    #         stop_loss = sub.atrsr._tup[-1]

    # if stop_loss < last_price:
    #     return stop_loss - price_epsilon

    if 0 < stop_loss < last_price - price_epsilon:
        return stop_loss - price_epsilon

    return 0.0


def dynamic_stop_loss_cur_atrsr_short(sub, entry_price, last_price, curr_stop_loss_price,
                                      depth, orientation, price_epsilon=0.0):
    stop_loss = 0.0

    if sub.atrsr and len(sub.atrsr._tup):
        if sub.atrsr._tup[-1] < curr_stop_loss_price and sub.atrsr._tup[-1] > last_price:
            stop_loss = sub.atrsr._tup[-1]

    # if sub.atrsr and len(sub.atrsr._tdn):
    #     if sub.atrsr._tdn[-1] < curr_stop_loss_price and sub.atrsr._tdn[-1] > last_price:
    #         stop_loss = sub.atrsr._tdn[-1]

    # if stop_loss > last_price:
    #     return stop_loss + price_epsilon

    if 0 < stop_loss > last_price + price_epsilon:
        return stop_loss + price_epsilon

    return 0.0


def dynamic_stop_loss_fixed_hma_long(sub, last_price, curr_stop_loss_price, price_epsilon=0.0):
    stop_loss = 0.0

    if sub.hma and sub.hma.hmas is not None and len(sub.hma.hmas) > 0:
        if 1:  # sub.last_closed:
            p = sub.hma.hmas[-1]

            if curr_stop_loss_price < p < last_price - price_epsilon:
                stop_loss = p

    return stop_loss


def dynamic_stop_loss_fixed_hma_short(sub, last_price, curr_stop_loss_price, price_epsilon=0.0):
    stop_loss = 0.0

    if sub.hma and sub.hma.hmas is not None and len(sub.hma.hmas) > 0:
        if 1:  # sub.last_closed:
            p = sub.hma.hmas[-1]

            if curr_stop_loss_price > p > last_price + price_epsilon:
                stop_loss = p

    return stop_loss


def dynamic_stop_loss(direction, data, sub, entry_price, last_price, curr_stop_loss_price, price_epsilon=0.0):

    if direction > 0:
        if data.type == StrategyTraderContext.PRICE_NONE:
            return 0.0

        elif data.type == StrategyTraderContext.PRICE_ATR_SR:
            return dynamic_stop_loss_atrsr_long(sub, last_price, curr_stop_loss_price, data.depth, data.orientation,
                                                price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_CUR_ATR_SR:
            return dynamic_stop_loss_cur_atrsr_long(sub, entry_price, last_price, curr_stop_loss_price, data.depth,
                                                    data.orientation, price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_BOLLINGER:
            return dynamic_stop_loss_fixed_bollinger_long(sub, last_price, curr_stop_loss_price, price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_FIXED and data.distance > 0.0:
            if data.distance_type == StrategyTraderContext.DIST_PERCENTILE:
                return dynamic_stop_loss_fixed_pct_long(sub, last_price, curr_stop_loss_price, data.distance)
            elif data.distance_type == StrategyTraderContext.DIST_PRICE:
                return dynamic_stop_loss_fixed_dist_long(sub, last_price, curr_stop_loss_price, data.distance)

        elif data.type == StrategyTraderContext.PRICE_HMA:
            return dynamic_stop_loss_fixed_hma_long(sub, last_price, curr_stop_loss_price, price_epsilon)

    elif direction < 0:
        if data.type == StrategyTraderContext.PRICE_NONE:
            return 0.0

        elif data.type == StrategyTraderContext.PRICE_ATR_SR:
            return dynamic_stop_loss_atrsr_short(sub, last_price, curr_stop_loss_price, data.depth, data.orientation,
                                                 price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_CUR_ATR_SR:
            return dynamic_stop_loss_cur_atrsr_short(sub, entry_price, last_price, curr_stop_loss_price, data.depth,
                                                     data.orientation, price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_BOLLINGER:
            return dynamic_stop_loss_fixed_bollinger_short(sub, last_price, curr_stop_loss_price, price_epsilon)

        elif data.type == StrategyTraderContext.PRICE_FIXED and data.distance > 0.0:
            if data.distance_type == StrategyTraderContext.DIST_PERCENTILE:
                return dynamic_stop_loss_fixed_pct_short(sub, last_price, curr_stop_loss_price, data.distance)
            elif data.distance_type == StrategyTraderContext.DIST_PRICE:
                return dynamic_stop_loss_fixed_dist_short(sub, last_price, curr_stop_loss_price, data.distance)

        elif data.type == StrategyTraderContext.PRICE_HMA:
            return dynamic_stop_loss_fixed_hma_short(sub, last_price, curr_stop_loss_price, price_epsilon)

    return 0.0
