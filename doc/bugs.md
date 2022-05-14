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

### IG related ###

**IG candle limit 10k reached** : Do the maths, how many markets do you want to initiate, to fetch, how many candles history you will need,
find your way, or try to ask if they can increase your limitations. I have no solution for this problem because it is out of my possibility.
