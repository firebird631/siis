# Commands #

Here are presented the differents commands managed by the command mode into the terminal instance,
and also available from the monitoring Websocket through a client (Web client...).

Support of monitoring client is not realized at this time.

Each of the availables commande are detailed with theirs arguments.
Some command are general, having a global effects, some are more specific, some others are
related to a trade, a trade operation or a strategy region.

You should use the TAB key for auto-complete the arguments, it list/complete most of the arguments.


## Help ##

```:help (command)``` or ```:h```

This command is only available from the SiiS terminal.

Without extra argument it display the help instructions and the list of commands.

If an argument is provided it must be one of the listed command. It will display a detailled help for
the specific command.


## User ##

```:user``` or ```:u```

Display the contextual user help.


## Alias ##

```:alias F(X) (command)``` or ```:@ F(X) (command)```

Allow to create a command alias mapped to one of the F1-F24 keys.

(X) must be replaced by a number from 1 to 24, and (command) by the text that will be copied when
pression the F(X) key.

Example :

```:alias F5 close my-strategy-name BTCUSD```

Each time you press F5 a new command will be inserted with close my-strategy-name BTCUSD, then you can validate
pressing the enter key.

Note that you can create incomplete alias like :

```:alias F5 long my-strategy-name ```

Then you could complete with the name of the pair of others arguments.


## Unalias ##

```:alias F(X)``` or ```:^ F(X)```

Delete a previously created alias, see Alias command.


## Play ##

```:play (apps|notifiers) (identifier) (market)```

Allow to enable/play either a strategy/appliance or a notifier.

The first argument is mandatory and must be apps for strategy/appliance or notifiers for a notifier.
If no others arguments are provided then all the strategy/appliance or notifiers will be enabled (if previously disabled).

If a strategy/appliance identifier arguments is defined then it will activate all the markets of it.
If a market is specified it will only activate this specific market.

If a notifier identifier argument is defined then only this notifier is activate.


## Pause ##

```:pause (apps|notifiers) (identifier) (market)```

Allow to disable/pause either a strategy/appliance or a notifier.

The first argument is mandatory and must be apps for strategy/appliance or notifiers for a notifier.
If no others arguments are provided then all the strategy/appliance or notifiers will be disbled (if previously enabled).

If a strategy/appliance identifier arguments is defined then it will pause all the markets of it.
If a market is specified it will only pause this specific market.

If a notifier identifier argument is defined then only this notifier is paused.


## Info ##

```:info (apps|notifiers) (identifier) (market)```

Returns the state either of strategies/appliances or of notifiers.

As with Play and Pause command it take the same arguments.

For notifiers it display the activity status.
For strategies/appliances it display the activity per market status, and the default trade amount/quantity/lot-size.


## Long ##

This command refers to a market of a strategy/appliance.

```:long (appliance) (market) (L@X) (T@X) (SL@X) (TP@X) (\*quantity-rate%) (\'timeframe) (/entry-timeout) (xleverage)```

or

```:L ...```

Manually create a new trade in LONG/BUY direction for a specific strategy/appliance and market.

Mandatory parameters are strategy/appliance and market. Others are optionnals and are :

- L@X means limit at value X (example L@1.14)
- T@X either L@X or T@X, means entry trigger stop in place of a limit order (example T@1.15)
- SL@X means stop-loss taker at value X (example SL@1.12)
- TP@X means take-profit maker at value X (example TP@1.18)
- \'timeframe defined the timeframe of the trade, manually will have no effect but it could be usefull for you,
	it must be one of the predefined timeframe values
- /entry-timeout Expiration timeout of the entry if the trade entry is not fully executed after this delay,
	it must be one of the predefined timeframe values
- \*quantity-rate Defined a size/amount factor from the predefined value (example x2.0 will double the default size, x0.5 will reduce by half)
- quantity-rate% Defined a size/amount factor from the predefined value in percent (example 200% will double the default size, 50% will reduce by half)
- xleverage Defined the Leverage of the trade in case of individual position leverage (rare case) (example x5 will define the leverage to 5)

If neither of L@X and T@X are defined then the order is executed on market as taker, according to the order-book.
If no timeframe is defined the default is 4h.

If no stop-loss or take-profit are defined there will be none of them, but the strategy/appaliance could auto-compute them for you.
Some strategy managed partially or totally the manual user trade, some others will no interfere with user trade.

Example :

```:long my-btc-strat BTCUSD L@8600 SL@8000 TP@9400 200% '4h /1d```

will create a long order with 200% of the configured quantity, enter at limit price of 8600$, place a stop-loss taker order
at 8000$ and a take profit maker order at 9400$. The trade will be auto-canceled if the limit price is not reached after 1 day,
and the timeframe of the trade is 4 hour.


## Short ##

This command refers to a market of a strategy/appliance.

```:short (appliance) (market) (L@X) (T@X) (SL@X) (TP@X) (\*quantity-rate%) (\'timeframe) (/entry-timeout) (xleverage)```

or

```:S ...```

Manually create a new trade in SHORT/SELL direction for a specific strategy/appliance and market.

Mandatory parameters are strategy/appliance and market. Others are optionnals and are described into the long command.

If neither of L@X and T@X are defined then the order is executed on market as taker, according to the order-book.

Example :

```:short my-forex-strat EURUSD L@1.15 SL@1.16 TP@1.14```

will create a short order, enter at limit price of 1.15$, place a stop-loss taker order at 1.16$
and a take profit maker order at 1.14$. The trade will be neved auto-canceled, and the timeframe of the trade is default to 4 hour.


## Close ##

This command refers to a market of a strategy/appliance and an existing trade.

```:close (appliance) (market) (trade)``` or ```:C (appliance) (market) (trade)```

Manually close at market a valid trade for a specific strategy/appliance and market.

Mandatory parameters are strategy/appliance, market and trade identifier.

The identifier of a trade is a number, listed from the trade view.

If the trade is not active (meaning no entered partially or fully) it will cancel the related entering order(s).
If the trade is active it send a close market order to the broker.


## Clean ##

This command refers to a market of a strategy/appliance and an existing trade.

```:clean (appliance) (market) (trade)``` or ```:CT (appliance) (market) (trade)```

Manually force the clean an trade entry for a specific strategy/appliance and market.

Mandatory parameters are strategy/appliance, market and trade identifier.

The identifier of a trade is a number, listed from the trade view.

This command will not close the position, neither sell the previously bought assets quantity.
There is two usages of this command :

- Remove a trade because we want the bot let go, and get manual control from the broker tool. Then all related exit order are canceled,
and the remaining entering order (if not fully filled) is canceled too.
- Remove a trade that is no longer existing, if there is a synchronization issue, or internal failure management, and then this
will force the remove the undesirable trade entry.

In some case the issue could be related to a persistant trade that is reloaded after restarting the bot but the tests let it pass,
or if the retrieved asset quantity does not correspond (slightly) to the realized quantity.


## Set quantity ##

This command refers to a market of a strategy/appliance.

```:setquantity (appliance) (market) (quantity)``` or ```:SETQTY (appliance) (market) (quantity)```

With info command it is possible to look how much amount/quantity/lot-size are ordered at each trade creation.
This value is not dynamically modified at this time, and you would increase/decrease it sometimes, depending of the risk 
you want and of the previous profits.

All arguments are mandatories.

The quantity parameters is either an amount of the asset or a contract size, or a lot size, it depend of the type of the instrument.


## Modify Stop Loss ##

This command refers to a market of a strategy/appliance and an existing trade.

```:stop-loss (appliance) (market) (trade) (price) (force)``` or ```:SL (appliance) (market) (trade) (price) (force)```

Changes or defines a stop-loss target for a specific trade.

All parameters are mandatory excepted (force).

The behavior will depend of the strategy/appliance, but without using the force argument the trigger will be executed
locally by SiiS, no reduce-order will be placed/modified, no position will be amended.

Using force argument it will create the stop-market reduce-order for the trade, or modifiy the stop-loss price if its a position.

Some strategies could modify dynamically the stop-loss target, locally or on broker side, then some strategies
could overrided used defined value, some others will detect the user intention and will not interfers with user manual changes.

Example :

```:SL my-strat BTCUSD 2 86000 force```

will motify the stop-loss price of the trade 2 to 8600$ and force to do it on broker side.


## Modify Take Profit ##

This command refers to a market of a strategy/appliance and an existing trade.

```:take-profit (appliance) (market) (trade) (price) (force)``` or ```:TP (appliance) (market) (trade) (price) (force)```

Changes or defines a take-profit target for a specific trade.

All parameters are mandatory excepted (force).

The behavior will depend of the strategy/appliance, but without using the force argument the trigger will be executed
locally by SiiS, no reduce-order will be placed/modified, no position will be amended.

Using force argument it will create the limit-postonly reduce-order for the trade, or modifiy the take-profit price if its a position.

Some strategies could modify dynamically the stop-loss target, locally or on broker side, then some strategies
could overrided used defined value, some others will detect the user intention and will not interfers with user manual changes.

Example :

```:TP my-strat BTCUSD 2 10000```

will motify the take-profit price of the trade 2 to 10000$. The order will be locally manage, it will not modify directly
the order on the broker, but depending of the strategy, it could detect the user change and decide to apply it on the broker side,
or the strategy could overrided later this value, or other strategy could then disable its automated management, and no longer
modify take-profit and stop-loss targets.


## Assign ##

This command refers to a market of a strategy/appliance and an existing quantity/position.

```:assign (appliance) (market) (EP@X) (SL@X) (TP@X) (\'timeframe) (quantity) (position)```

or

```:AS ...```

Imagine you have an existing position or a quantity of an asset, and you want to manage it from SiiS,
then with assign command you can refers this position/asset-quantity and create a trade on it,
then the strategy/appliance will be able to manage, or you could add some trade operation on it, and visualize the P/L.

Note, for now only asset quantity could be assigned (developpement need for position assign).

All parameters are mandatory excepted (\'timeframe) and depending of the case (quantity) or (position).

Example :

```:assign my-btc-strat BTCUSDT EP@8600 SL@8000 TP@9400 0.1 '4h```

will assign 0.1 BTC to a trade, assuming the entry-price was 8600$.
It will defined the stop-loss and take-profits orders too.

You should make attention about exit orders, you could have to delete your previous order before, else
it will not able to look for free asset quantity.

This is an advanced feature, you have to know what you do before using it, and knowing how the strategy/appliance will intefers with the trade.


## Chart ##

This command refers to a market of a strategy/appliance and a valid timeframe.

```:chart (appliance) (market) (timeframe)``` or ```:V (appliance) (market) (timeframe)```

It open a new window with a matplotlib chart, as dynamic as possible, for the selected timeframe.
Note this feature is only for dev/testing only, the charting client is very primitive and could have
some bugs. The future monitoring WebClient will offers more user friendly and powerfull charting feature.


## User Save ##

```:save``` or ```:s```

Force to save now all strategies/appliances states and existing trades. This operation is done automatically at program exit.


## Add Dynamic Stop Loss ##

This command refers to a trading operation of an existing trade.

```:dynamic-stop-loss (appliance) (market) (trade) (trigger-price) (stop-price)``` or ```:DSL ...```

[More information about trade operations.](doc/strategies/tradeops.md)

Add an operation on an existing trade, to modify the stop-loss order/price once it reach a specified trigger price.
In others words, each time the price move and reach a fixed better price it will modify the stop-loss price to a specified value.

Example :

```:DSL my-btc-strat BTCUSDT 1 9000 8600```

The price of BTCUSDT reach 9000$, then the operation modify the stop-loss price to 8600$.
Once executed the operation is deleted.

You can add many dynamic-stop-loss operation, at diffents level, then you could progressively secure your trade during the pump.


## Remove Operation ##

This command refers to a trading operation of an existing trade.

```:del (appliance) (market) (trade) (operation)``` or ```:D ...```

[More information about trade operations.](doc/strategies/tradeops.md)

Delete an existing operation on an existing trade.

Trade and operation arguments are integer values.
Once deleted an operation can be recreated.


## Trade Info ##

```:trade (appliance) (market) (trade)``` or ```:T (appliance) (market) (trade)```

This command refers to a market of a strategy/appliance and an existing trade.

Returns the list of the defined operation on a specific trade.
You can remove them using the Remove Operation.


## Add Range Region ##

This command refers to a strateygy/appliance.

[More information about strategy/appliance regions.](doc/strategies/regions.md)

...


## Add Trend Region ##

This command refers to a strateygy/appliance.

[More information about strategy/appliance regions.](doc/strategies/regions.md)

...


## Remove Region ##

This command refers to an existing region of a strateygy/appliance.

[More information about strategy/appliance regions.](doc/strategies/regions.md)

...
