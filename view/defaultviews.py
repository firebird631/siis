# @date 2019-06-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# View manager service.

from view.service import ViewService


def setup_default_views(view_service, watcher_service, trader_service, strategy_service):
    # 'signal'
    from view.signalview import SignalView
    signal = SignalView(view_service, strategy_service)
    view_service.add_view(signal)

    # 'alert'
    from view.alertview import AlertView
    alert = AlertView(view_service, strategy_service)
    view_service.add_view(alert)

    # 'activealert'
    from view.activealertview import ActiveAlertView
    activealert = ActiveAlertView(view_service, strategy_service)
    view_service.add_view(activealert)

    # 'traderstate'
    from view.traderstateview import TraderStateView
    traderstate = TraderStateView(view_service, strategy_service)
    view_service.add_view(traderstate)

    # 'activeregion' @todo
    # from view.activeregionview import ActiveRegionView
    # activeregion = ActiveRegionView(view_service, strategy_service)
    # view_service.add_view(activeregion)

    # 'account'
    from view.accountview import AccountView
    account = AccountView(view_service, trader_service)
    view_service.add_view(account)

    # 'strategy'
    from view.tradeview import TradeView
    trade = TradeView(view_service, strategy_service)
    view_service.add_view(trade)

    # 'stats'
    from view.tradehistoryview import TradeHistoryView
    trade_history = TradeHistoryView(view_service, strategy_service)
    view_service.add_view(trade_history)

    # # 'perf'
    from view.aggtradeview import AggTradeView
    agg_trade = AggTradeView(view_service, strategy_service)
    view_service.add_view(agg_trade)

    # 'market'
    from view.marketview import MarketView
    market = MarketView(view_service, trader_service)
    view_service.add_view(market)

    # 'ticker'
    from view.tickerview import TickerView
    ticker = TickerView(view_service, trader_service)
    view_service.add_view(ticker)

    # 'position'
    from view.positionview import PositionView
    position = PositionView(view_service, trader_service)
    view_service.add_view(position)

    # 'order'
    from view.orderview import OrderView
    order = OrderView(view_service, trader_service)
    view_service.add_view(order)

    # 'asset'
    from view.assetview import AssetView
    asset = AssetView(view_service, trader_service)
    view_service.add_view(asset)

    # # 'orderbook' @todo
    # from view.orderbookview import OrderBookView
    # orderbook = AssetView(view_service, trader_service)
    # view_service.add_view(orderbook)
