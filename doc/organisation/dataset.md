# Data structure #

Data are stored into the SQL database and into the filesystem.
Data stored on the filesystem are located into the configured (.siis by default) directory,
into your home ([see configuration for more details](../configuration/index.md)).

## Market dataset ##

The tick or trade data (price, volume, spread) are fetched during the running or when doing 
a manual fetch. By default, at runtime the tick or trade data are not stored on the filesystem.
Only the initial fetch of OHLC (candles/klines) are stored into the database.

The OHLC (candles/klines) data are stored into the SQL database. 

By default, any candles from 1m to 1w are stored and kept indefinitely.
The databases.json file defines an option **auto-cleanup**, set by default to false, if set to true it will process 
a clean-up each 4 hours of the last OHLCs :

* Weekly, daily, 4h and 3h OHLC are always kept
* 2h, 1h and 45m OHLC are kept for 90 days
* 30m, 15m, 10m are kept for 21 days
* 5m, 3m, 1m are kept for 8 days
* 1s, 10s, 15s, 30s are never kept

To force the storage of tick or trade data received during execution of the bot (watcher thread),
add the command line option **--store-trade**.

To force the storage of OHLC (candles/klines) data received during execution of the bot (watcher thread),
add the command line option **--store-ohlc**.

Further storage configuration of data will be added in file **databases.json**, in way to configure the max kept OHLC for each timeframe,
and create a special db-cleanup running mode that will only process the db-cleanup for the live servers.

There is no interest for live mode to kept too many past data for lowest timeframes, but it's necessary to keep them for
the backtesting.

You can use the **--rebuild** or **--tool=rebuilder** command to rebuild missing OHLCs from sub-multiple or from ticks/trades data.

It is possible to set up your own crontab with an SQL script the clean as your way.
It is also possible to set up your own crontab that call siis.py fetching every hour or day.

The strategy call the watchers to prefetch the last recent OHLC for the timeframes.
The fetched amount of OHLCs depends on the strategy, and can be configured into the profile json file.

When fetching data from IG it there is a limit of 10k candles per week. It can cause problem if you don't think about 
that before running the bot on many markets. For convenience, I've made some bash scripts to frequently fetch OHLC, 
and some others scripts (look at the scripts/ directory for examples) that I run just before starting a live instance 
to make a prefetch (only the last N candles), and to stay synced.

You can use the optimize command option to check your data, for trades/ticks and for any OHLC timeframes.

Trades/ticks are by default not stored from watcher running, but excepted for IG, because it's not possible to get back history from their API.
The problem is if you don't let an instance all the week, you will have some gap. You could manage to restart only once per week, during the
weekend the bot in that case, and to apply your strategies changes at this time.

Finally, you can disable writing of OHLCS generated during watcher using the option --read-only.

### Ticks/trade ###

The siis folder contains a subdirectory : markets. Into this directory the structure remains the same for any exchange (configured trader) :

<name_of_trader>/<market_name>/T/<year_month_market_name>

With :
  * <name_of_trader> : name of the related trader
    * For example binance.com, binancefutures.com, kraken.com, ig.com ...
  * <market_name> : name of the pair or the market codename related to the exchange
    * For example BTCUSDT, XRPUSD, ADAEUR, EURUSD, UDSJPY ...
  * T : means ticks or trades data or aggregated trade data
  * <year_month_market_name> : 4 digits year, 2 digits month, market name or codename
    * The file extension can be empty or .dat
      * .dat extension means an optimized binary file, this is the default configured file format

For Binance data are aggregate trades, for BitMex data are real trade, for IG CFD data are ticks,
for Kraken data are real trades.

There is one file per month, there is a binary and a tabular version of the file at this time. But maybe later
the tabular version will be removed.

About the files containing the trade/ticks data, there is bad effect of that design. The good effect is the highest performance, 
but because of Python performance this is not very impressive. A C/C++ version could read millions of tick per seconds, 
it is more performant than any timestamp based DB engine. The bad side of that design is that I've chosen 
to have 1 file per month (per market), and the problem is about temporal consistency of the data.
If you don't make a simple update, meaning to fetch from the last stored trade, and then you give a more recent date and time,
this will do a gap of data into the file. And the insert method is not currently supported. That's mean you will have 
to remove the files containing gaps and to fetch them again. There is a **--optimize** or **--tool=optimizer** command 
that help you to check where there is some errors into the market's data.

### OHLC/candles/klines ###

Explain ...

### Data consistency and error checking ###

The command **--optimize** or **--tool=optimizer** allow you to check trade/tick or OHLCs data time coherency and data error.

Explain ...

### Rebuild missing data ###

The command **--binarize** or **--tool=binarizer** allow you to convert a trade/tick data file from ASCII format to binary format.

Explain ...

### Data limits consideration ###

Take care to always have enough free disk space before to start a fetch or to execute the bot. 

## User strategy persistence ##

In live mode ony (real trading), when the bot is quit, status of the strategy traders are saved into the database 
using the name and identifier of the strategy, and the name of the trading account. 
When restarting the bot settings are reloaded from profile configure, and status variables that are stored previously 
into the database will override them.

To force to use the initial profile setting you have to clear database related record or to change the identifier of 
profile. **[WIP feature]** The **--tool=cleaner** using the **--object=profile-for-account:\<account-id\>** allow 
you to clean the previously saved status.

## Trades persistence ##

Explain ...

## Liquidation ##

Explain ...

## Performance and optimization ##

Explain ...

## Considerations about organisation ##

Explain ...
