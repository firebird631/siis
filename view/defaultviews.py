# @date 2019-06-28
# @author Frederic SCHERMA
# @license Copyright (c) 2019 Dream Overflow
# View manager service.

from view.service import ViewService
# from view.textview import TextView


def setup_default_views(view_service, watcher_service, trader_service, strategy_service):
    # 'default'
    # from view.defaultview import DefaultView
    # default = DefaultView()
    # view_service.add_view(default)

    # 'debug'
    # from view.debugview import DebugView
    # debug = DebugView()
    # view_service.add_view(debug)

    # 'signal'
    # from view.signalview import SignalView
    # signal = SignalView(strategy_service)
    # view_service.add_view(signal)

    # 'account'
    from view.accountview import AccountView
    account = AccountView(trader_service)
    view_service.add_view(account)

    # 'strategy'
    from view.tradeview import TradeView
    trade = TradeView(strategy_service)
    view_service.add_view(trade)

    # 'stats'
    from view.tradehistoryview import TradeHistoryView
    trade_history = TradeHistoryView(strategy_service)
    view_service.add_view(trade_history)

    # 'perf'
    from view.aggtradeview import AggTradeView
    agg_trade = AggTradeView(strategy_service)
    view_service.add_view(agg_trade)

    # 'market'
    from view.marketview import MarketView
    market = MarketView(trader_service)
    view_service.add_view(market)

    # 'ticker'
    from view.tickerview import TickerView
    ticker = TickerView(trader_service)
    view_service.add_view(ticker)

    # 'position'
    from view.positionview import PositionView
    position = PositionView(trader_service)
    view_service.add_view(position)

    # 'order'
    from view.orderview import OrderView
    order = OrderView(trader_service)
    view_service.add_view(order)

    # 'asset'
    from view.assetview import AssetView
    asset = AssetView(trader_service)
    view_service.add_view(asset)
