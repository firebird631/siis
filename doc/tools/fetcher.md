# Fetcher #

This tools allow to fetch market data (ticks/trades/quotes or OHLC candles).

Each configured fetcher can be used through the fetcher command tool.

Either you can fetch only a specific timeframe or only ticks/trades/quotes, or you can generate the higher timeframe,
in cascaded mode until the wanted higher timeframe.

The rebuilder command tools can be used after a fetch to rebuild a specific timeframe of OHLC, or many in casaced mode too.

There is special case, some broker are only virtual, like HistData or TickStory, fetcher can assist to create virtual market info data
into the database to be able to process backtest on them, please read below for more explanations.


## Fetchers ##

Different fetchers are implemented, please read below before fetch.


### Binance (Spot/Margin) ###

Codename : binance.com

...

Limitations: 
* slow fetching

Advantages:
* lot of history OHLCs
* aggreged trades data history


### Bitmex ###

Codename : bitmex.com

...

Limitations: 
* very slow fetching

Advantages:
* lot of history OHLCs
* aggreged trades data history


### HistData ###

Codename : histdata.com

HistData is a good place where to download some forex and indices markets data.
I don't know what is the sources.

If the data are imported using the fetcher, all data are related to the histdata.com broker codename,
and then not usable from another broker/market.

It is possible to uses these dataset for backtesting but it is necessary to setup the related market info data.

#### Installing markets ####

...


### IG (CFD) ###

Codename : ig.com

...

Limitations: 
* 10000 OHLCs limit per week, per account
* history limited different for each timeframe, look the official doc
* strange datetime (maybe DST datetime or timezone issue even using their UTC timestamp)
* no tick data history
* only forex and indices

Advantages:
* Very fast fecthing.

This will limit most of the strategies.

Then this will be using only by the watcher, to get the last up-to-date OHLC per timeframe, but really no more.


### Kraken (Pro) ###

Codename : kraken.com

...

Limitations: 
* history of the last 720 OHLCs per timeframe
* weekly starts on thursday

Advantages:
* Unlimited trade data history

This could limit some strategies.

Then you could fetch the trades data, and generated OHLCs from them (--cascaded options or --rebuild tool)


...


### TickStory ###

Codename : tickstory.com

Tickstory is a great tool that allow you to get history of data from different brokers.
At this time there is only Dukascopy.

If the data are imported using the fetcher, all data are related to the tickstory.com broker codename,
and then not usable from another broker/market.

It is possible to uses these dataset for backtesting but it is necessary to setup the related market info data.


#### Installing markets ####

...
