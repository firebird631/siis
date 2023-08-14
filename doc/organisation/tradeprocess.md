# Orders and trades Processing #

Trades are managed per strategy trader (StrategyTrader) and strategy traders are managed by strategy (Strategy).

Strategy receive events from watchers (Watcher) and traders (Trader).
Trader subscribe to order's (new, update, cancel, delete, close) and trades executions.

Watcher is responsible to retrieve events from the exchange.

Each event is pushed to the dequeue of the strategy instance and the thread
of the strategy at each pass it dispatches the messages to the related strategy trader.

It also receives update signals for positions in margin and CFDs exchanges and the prices tickers and 
executed public trades and potentially order book and some other information.

## Dispatch of orders and positions signals ##

During the update pass of the strategy into its dedicated thread messages are executed :
* Firstly it looks up for the strategy trader according to the market identifier
* Then it searches if one or more trades are looking for the message :
  * Using either the unique user reference
  * Or using the order unique exchange identifier
  * And for the position according either 
    * To the unique exchange position identifier
    * Or to the market identifier (plus direction eventually) for futures exchanges

During the execution of the message onto the trade, the trade mutex of the strategy trader is acquired.

It is important that any action onto a trade is processed into a trade mutex block.

Another important thing to considers is when an order is created through the trader, if the trade as some changes, 
it must also be protected by the strategy trader trade mutex.

* It is important to acquire mutex because the method doing something on a trade must be completed before a receiving a message to be process from the watcher.
  * Else it could cause border side effects like not having knowledge of all necessary state before processing correctly the message
  * Or receive a message before to know its target
    * This case is special and should never occur because the user reference order identifier is defined before calling the exchange API endpoint.

## Trade entry, limit and stop management ##

The trade entry is unique and eventually can be replaced before the original entry order is executed.
If the original entry order is partially executed it is not possible to modify (reopen) the trade.

It is possible to cancel an entry, manually or strategy based, or using an expiry timeout.

About exits orders, there is always a stop price and a limit price. The stop can be in loss or profit.
The limit also but it could be a problem with some case on crypto spot trading if the min notional is not reached after 
an important loose.

Spot market allow only one limit or stop order at time but the counter-part is then locally managed using a market order 
once the price of stop or limit is reached.

_OCO orders are actually not fully implemented neither tested._

It cannot be possible to have multiple limit orders par trade, but it is allowed for CFD positions to be reduced.

A manual close market order is managed using the stop order of a trade.
The limit order is then deleted and a market order is created with remaining quantity.

**Putting many target need to add many orders.**

If the user manually close a trade that is partially executed in exit through the limit order then there is some considerations to take in account.

* Most watchers returns the cumulative filled field and sometimes the filled field.
  * Meaning it is more complex to get the exact realised exit quantity
    * This way there is separate ordered quantity and executed quantity per order
      * Only one for the entry because it is fully or not or if partially it is not possible to increase entry for this trade
      * A table for each exit order (for each one not closed/canceled/deleted)
        * It is kept until the order is fully filled
        * In that way the trade is certain to don't miss an order partial or complete execution
        * The cost is to manage the previous stop and limit orders data

_Actually there is only one cumulative computed quantity for exit._
This is a potential issue in some cases that have to be handled.
