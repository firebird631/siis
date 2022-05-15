# Organisation and Structure #

SiiS is a trading bot, and can monitor your account (positions, orders, balance, assets...).
The watcher is dedicated to connect to public and private data in real-time using HTTP REST and HTTP WebSockets.

There are 3 fundamentals services into the application :
* Watchers service : Connect to a virtual or one or multiple data sources,
* Trader service : Connect to a demo ou real account or emulate for paper-trading,
* Strategy service : Use of the watchers signals data and trading features.

There are 3 others services :
* Database service : To manage the asynchronous data loading and saving from SQL database or from filesystem,
* Monitor service : Create an HTTP server and WebSocket Server and provides service for an external Web Application,
* WatchDog service : To check that any others services and worker are still alive and not frozen or saturated,
* Notifiers service : To publish trading and status signals to externals services (Telegram, Discord...).

## Watchers Service ##

The watcher service instantiate the watchers configured into the profile. In backtesting there is no connected watcher, 
but there is a dummy watcher.

Generally only one watcher is configured and connected. At least the watcher of the exchange must be configured.
It will fetch any initial data, OHLCs (candles/klines), previous realized or aggregated trades if the strategy need them, 
connect to live trade and price tickers, to user data stream to receive messages of trading (orders, trade, positions), 
and some others exchanges messages.

This watcher will be used by the trader. Many others watchers could be configured and connected to get some others sources 
of data for the strategy.

* Source : _watcher/service.py_
* Base model : _watcher/watcher.py_
* Connectors adapter's : _watcher/connector/*_
* Dummy watcher model for backtesting : _watcher/dummywatcher/watcher.py_

### In real or paper mode ###

In real trading and in paper trading, live data are received using the different watchers.

* [More about trading](../trading.md).
* [More about paper trading](../papermode/index.md).

### In backtest mode ###

In backtest mode, live data are not necessary, only a dummy-watcher is instanced. This dummy watch 
generate the OHLC using the trade or tick data streamed from the data stored on the filesystem.

It also sends events to others services.

* [More about backtesting](../backtesting/index.md).
* [More about paper trading](../papermode/index.md).

## Trader Service ##

The trader service instantiate the trader (broker/exchange) configured into the profile.
There is only one trader connected per instance.

* Service : _trader/service.py_
* Base model : _trader/trader.py_
* Connectors adapter's : _trader/connector/*_
* Paper-trader model : _trader/papertrader/trader.py_

It is connected to the related watcher (of the same name) in way to receive the trading updates,
and markets data.

It sends only one message to others service after loading of the different markets data information. 

### In real mode ###

In real mode the account data are updated from HTTP REST and from HTTP WebSocket.

[More about trading](../trading.md).

### In backtest mode or paper mode ###

In backtest or paper mode the trade is simulated. The trader instanced is the paper-trader. It simulates the behavior of 
an exchange, realize the pending orders (limits, stop...), and the market orders. It also manages the different 
positions on margin and position trading. It updates at every trade or tick and trade are executed on the first level of 
the order book (first bid/ask price).

The volume is not taken into account, and there is no slippage factor. 

* [More about backtesting](../backtesting/index.md).
* [More about paper trading](../papermode/index.md).

### Replicators ###

It is a feature that will be developed later in order to replicate a strategy to multiple account at time,
in that way you will be able to replicate your strategy to any of your clients accounts.

## Strategy Service ##

* Service : _strategy/service.py_
* Base model : _strategy/strategy.py_
* Strategy-trader Base model : _strategy/strategytrader.py_

The strategy service run a dedicated thread, plus a pool of worker. Each worker have its dedicated thread.
By default, there is a worker per CPU, this can be configured.

The strategy service read the profile and instantiate the strategy with one strategy-trader per instrument.
A strategy-trader is a subunit of the strategy.

The strategy service receive events from the trader service and from the watchers service.
Messages are then dispatched to their related strategy-trader.

The strategy-trader update query is then pushed into the pool of workers to be executed as soon as possible.
Depending on the message the strategy-trader can execute a computing to evaluate the trading signals or updates some 
internal data.

The strategy does not care if there is a real watcher connection or a simulated trader.

[More about strategies](../strategies/index.md).

## Database Service ##

* Service : _database/database.py_
* PostgreSQL specialization : _database/pgsql.py_
* MySQL specialization : _database/mysql.py_
* OHLCs (candles/klines) storage, management, reading, streaming : _database/ohlcstorage.py_
* Tick or trades storage, management, reading, streaming : _database/tickstorage.py_

The database service is responsible for the synchronous, asynchronous data loading, and of asynchronous data writing.

Most of the data are loaded and written asynchronously.

## Monitor Service ##

* Service : _monitor/service.py_

The command line terminal allow you to process any of the operation during runtime.
But this is not very user-friendly, and it can be not very safe to always use directly this interface.

The monitor service if started allow you to connect the Web Trader or any other Web Client to
control the bot instance.

The monitoring service run a dedicated thread, plus the HTTP REST and the HTTP WebSocket pools of connections.

[More about the monitoring](../monitor/index.md).

## WatchDog Service ##

* Service : _common/watchdog.py_

This service is useful to detect when the application stay too long in a loop.
Some pings message are sent to the different thread, if the thread does not answer in a 
fast delay a message appear in the console view.

The watch-dog service run a dedicated thread.

During start-up it is possible to get some warnings, but after except when called a mass-command,
it is not a good sign to have such ping timeout warnings messages.

The percent **%** key can be used to manually ping each services.

Some cause of latency : 
* During startup there is a lot of data to fetch or to compute, you have to wait the startup complete.
* One or many services can be temporarily waiting for an answer of the exchange. This can be a network or external service latency.
* There is too many trades events per second, the strategy or the workers are saturated.
* An unknown bug occurred.

## Notifiers Service ##

* Service : _notifier/service.py_
* Base model : _notifier/notifier.py_

It is not mandatory to configure some notifiers, but as default there is a desktop notifier.
The desktop notifier can post popup notification through the DBus system using lib notify2.

It can also play audio sound using alsa-player **aplay**. If the lib notify2 is not found it will
don't try to emit desktop popups.

[More about notification](../notifiers/index.md).
