# Troubles #

Please understand than I develop this project during my free time, and for free, only your donations could help me.

## Issues during installation ##

**TA-lib is not found** : look you have installed it, and maybe you have to export your LD_LIBRARY_PATH.

## Runtime issues ##

**Backtesting is slow** : I know that, you can increase the timestep, but then the results will be less accurate, mostly depending on
if the strategy works at close or at each tick/trade, and if the timestep is or not an integer divider of the strategy base timeframe.
When I've more time or a lot of feedbacks I will spend more time to develop the C++ version.

**Fetching historical data is slow** : It depends on the exchange and the timeframe. Fetching history trades from BitMex takes a lot of time,
be more patient, this is due to theirs API limitations.

**In paper-mode (live or backtesting) margin or asset quantity is missing** : A recent problem reappears with BitMex markets, I have to investigate,
it's annoying for live paper-mode and for backtesting. Similar issues could appear with assets quantities. It's in the priority list.
Maybe I will plan to have only percent P/L, where the paper-trader will accept any trades.

### BitMex related ###

**BitMex WS connection error** : Their WS are very annoying, if you restart the bot you have to wait 2 or 3 minutes before, because it
will reject you until you don't wait.

**BitMex overloads** : The bot did retry of order, like 5 or 10 or 15 time, I could make a configurable option for this, but sometimes
it could not suffice, consider you missed the train.

**BitMex reject your API call, a story of expired timestamp** : Then your server time is not synced with a global NTP server. BitMex says
there is a timestamp to far in the past or that is in the future. If your server does not have a NTP service consider installing one,
and update the datetime of your system, and then restart the bot.

**Exception during fetch of BitMex trade** : It appears, and I have no idea at this time there is an unexpected API response that generate a program
exception, that need to restart the fetch at the time of failure. I will investigate later on that issue. 

### Binance related ###

**Binance starting is slow** : Yes, prefetching a lot of USDT and BTC markets take a while, many minutes, be patient, your bot
will do not have to be restarted every day, once your configured correctly. For testing considers limiting the configured symbols lists.

**Binance Spot and Binance Futures with more than 100 markets at time loss data bid/ask price data stream** : Theirs documentation 
allow to have until 200 stream per web-socket connection, but there is some stream connection loss below this limit. 
it works with less than 100 markets, trying to go above could be a problem.

**Error during placement of a sell order** : It is better to always have a sufficient amount of BNB tokens to pay commissions with. 
Binance use free (not in order) BNB tokens to pay commissions with a lower rate and the management is simpler for the bot.
It you do not have enough BNB buy order will take on asset balance and sell order on quote balance. SiiS try to translate 
as possible the amount, but it is strongly recommended to use BNB tokens to avoid issues.

### IG related ###

**IG candle limit 10k reached** : Using the demo account it is possible to double the limit to 20k.
Do the maths : how many markets to initiate, to fetch, how many candles history is needed ? 
Try to contact IG support to increase limitations. A solution is to use another fetcher and map data to IG. 
Then only fetch from IG the most recent history at startup using --initial-fetch and never store them (
don't use --store-ohlc neither --store-trade else it will create history inconsistencies).
Take care to check that starting many times the instance per week that it will not reach limits.

**IG provides live and history data for limited markets types** : commodities, indices, forex and crypto. 
You will not be able to get data for stocks. In that case you can fetch history using another source and map them to IG. 
For live data you will need a specific watcher. Take care of a possible price spread between your different source 
of price and IG market price.

**siis.error.watcher.ig AttributeError("module 'time' has no attribute 'clock'")** : Since Python 3.9 the Crypto package is not maintained. 
Two solutions : replace by its alternative (remove the current, install its replacement) or manually fix the file lib/python3.<9|10>/site-packages/Crypto/Random/_UserFriendlyRNG.py
at line 77 with t = time.process_time(). clock() function is deprecated and definitively removed since Python 3.9.

### ByBit related ###

**No orders are created** : Yes the trading part (ordering, user WS) is not implemented for now.

**It does not work at all** : Yes the watching of market data is not fully completed for now. Please consider donation to help the developer.

### Backtesting and Training related ###

During a backtest, the conversion rate (base_exchange_rate) of instruments are unknowns.
And it will occur to invalid account balance calculation.

This could be a problem for the following cases :
  * Backtesting multiple instruments on the same profile that have different settlement or quote currency.
  * Backtesting an instrument having a different settlement or quote currency than the account currency.

Solutions :
  * Do distinct profiles and backtest per instrument or at least group them by settlements or quote currency.
  * Always define the account currency as the same as the settlement or quote currency of the instrument.
