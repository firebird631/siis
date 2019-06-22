// ==UserScript==
// @name         New Userscript
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  try to take over the world!
// @author       You
// @match        https://fr.tradingview.com/chart/15IaXPgV/
// @grant        GM_log
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// ==/UserScript==

// curl -i -H "Accept: application/json" -H "Content-T/json" -X GET "http://127.0.0.1:7373?strategy=blueskyday&action=order&direction=long&timestamp=124658654654&symbol=BTCUSD&price=6200.0&apikey=u9J4ZBxH0dq1Di7zFVu22C3VHSsbCrQ6iFf0z3t8p8k"

// @todo restart on parameters changes !!
// @todo more finest data spy
// @todo add a shortcut to force to send the latest signal

(function() {
    'use strict';

    let SymbolsMap = {
        // crypto
        "Bitcoin / Dollar": "BTCUSD",
        "BTC/USD": "BTCUSD",
        "BTC / USD": "BTCUSD",
        "Ethereum / Dollar": "ETHUSD",
        "ETH/USD": "ETHUSD",
        "ETH / USD": "ETHUSD",
        // forex
        "AUD/NZD": "AUDNZD",
        "AUD/USD": "AUDUSD",
        "EUR/USD": "EURUSD",
        "EUR/JPY": "EURJPY",
        "EUR/CAD": "EURCAD",
        "EUR/TRY": "EURTRY",
        "EUR/CHN": "EURCHN",
        "USD/JPY": "USDJPY",
        "USD/CAD": "USDCAD",
        "USD/TRY": "USDTRY",
        "USD/CHN": "USDCHN",
        "GBP/USD": "GBPUSD",
        "EUR/GBP": "EURGBP",
        // indicies
        // metals
        // stocks
        // @todo
    };

    console.log("TradingView strategy spy starting...");
    console.log("Press CTRL+l to lock unlock the screen");
    console.log("Press CTRL+y to toggle play/pause signals sending");
    console.log("Press CTRL+i to force restart");
    console.log("Press CTRL+m to force send/resent the latest signal");

    let apiKey = "u9J4ZBxH0dq1Di7zFVu22C3VHSsbCrQ6iFf0z3t8p8k";
    let strategyName = "undefined";

    let trackerInit = false;
    let strategyTrackerLastTradeNum = 0;
    let locked = false;
    let playpause = true;
    
    let symbol = "";
    let timeframe = 0;
    
    let options = {};

    let protocol = 'http://';
    let host = '127.0.0.1';
    let port = 7373;

    let lastSignal = null;

    let restart = function() {
        trackerInit = false;
        initializeStrategyWatcher();
    };

    let sendLast = function() {
        if (!trackerInit || !lastSignal) {
            return;
        }

        let url = lastSignal;

        // force the timestamp to now... but does we really want that, the strategy would
        // want to know when it was produced
        let updatedDate = new Date().getTime() / 1000;
        url.searchParams.set('timestamp', updatedDate);
        url.searchParams.set('originalTimestamp', url.searchParams.get('timestamp'));

        let tradeId = url.searchParams.get('id');
        let direction = url.searchParams.get('direction');
        let price = url.searchParams.get('price');
        let symbol = url.searchParams.get('symbol');

        GM_xmlhttpRequest({
            method: "GET",
            url: url.href,
            onload: function(response) {
                console.log("Order #" + tradeId + " transmission result: " + response.responseText);
            },
            onerror: function() {
                console.log("Cannot send order #" + tradeId);
            }
        });

        let msg = "Stragegy " + strategyName + " order (#" + tradeId + ") " + direction + ' ' + updatedDate + ' ' + price + ' ' + symbol;
        console.log(msg);
        let notification = new Notification(msg, {});
    };

    // it is a big fix, because only the n last pos are displayed, and no idea where there are into the model
    // so force scroll to bottom and get the last trades
    let strategyUpdate = function() {
        let report = $("div.reports-content").parent();
        let trades = report.find('td.trade-num');

        // always force scroll to bottom
        $("#bottom-area > div.bottom-widgetbar-content.backtesting > div.backtesting-content-wrapper > div > div").scrollTop(
                $("#bottom-area > div.bottom-widgetbar-content.backtesting > div.backtesting-content-wrapper > div > div")[0].scrollHeight)

        // let tables = $("div.reports-content").children("div.report-content").children("div.report-data").children("div.table-wrap").children('table').children('tbody');

        for (let i = 0; i < trades.length; ++i) {
            let trade = trades.eq(i);

            let entry = trade.parent();
            let exit = entry.next();

            let tradeId = parseInt(trade.text());

            let now = new Date().getTime() / 1000;

            if (tradeId > strategyTrackerLastTradeNum) {
                let process = true;

                if (!playpause) {
                    process = false;
                }

                // let direction = entry.children('td.trade-e-comment').text() === 'Long' ? 'long' : 'short';
                let direction = "long";

                if (entry.children('td.trade-e-type').text().endsWith('achat') || entry.children('td.trade-e-type').text().endsWith('buy')) {
                    direction = 'long';
                } else if (entry.children('td.trade-e-type').text().endsWith('vente') || entry.children('td.trade-e-type').text().endsWith('sell')) {
                    direction = 'short';
                }

                let date = Date.parse(entry.children('td.trade-e-date').text().replace(/\s/, "T")) / 1000;  // ms to s
                let price = parseFloat(entry.children('td.trade-e-price').text());
                let exitPrice = parseFloat(entry.children('td.trade-x-price').text());

                if (now - date > 60) {
                    // does not automatically send older signals
                    process = false;
                }

                // parameters
                var url = new URL(protocol + host + ':' + port);
                url.searchParams.set('apikey', apiKey);

                url.searchParams.set('id', tradeId);
                url.searchParams.set('strategy', strategyName);
                url.searchParams.set('action', 'order');

                // symbol and timeframe
                url.searchParams.set('symbol', symbol);
                url.searchParams.set('timeframe', timeframe);

                // strategy settings settings
                for (let o in options) {
                    url.searchParams.set('o_' + o, options[o]);
                }

                if (!isNaN(exitPrice)) {
                    let exitDate = Date.parse(entry.children('td.trade-x-date').text().replace(/\s/, "T")) / 1000;  // ms to s
                    let exitDir = entry.children('td.trade-x-comment').text() === 'Long' ? 'long' : 'short';

                    url.searchParams.set('type', 'exit');
                    url.searchParams.set('direction', exitDir);
                    url.searchParams.set('timestamp', exitDate);
                    url.searchParams.set('price', exitPrice);

                    console.log("Position exit signal: ", tradeId, exitDir, entry.children('td.trade-x-date').text(), exitPrice);
                } else {
                    url.searchParams.set('type', 'entry');
                    url.searchParams.set('direction', direction);
                    url.searchParams.set('timestamp', date);
                    url.searchParams.set('price', price);

                    console.log("Position enter signal: ", tradeId, direction, entry.children('td.trade-e-date').text(), price);
                }

                lastSignal = url;
                strategyTrackerLastTradeNum = tradeId;

                // <tbody>
                // <tr>
                //    <td rowspan="2" class="trade-num">4</td>
                //    <td class="trade-e-type">Entrée transaction de vente</td>
                //    <td class="trade-e-comment comment">Short</td>
                //    <td class="trade-e-date">2018-07-30&nbsp;03:03</td>
                //    <td class="trade-e-price">8145.6</td>
                //    <td rowspan="2" class="trade-contracts">1</td>
                //    <td rowspan="2" class="trade-profit">
                //       <span class="neg">$ 6.30</span>
                //       <div class="additional_percent_value"><span class="neg">0.01&nbsp;%</span></div>
                //    </td>
                // </tr>
                // <tr>
                //    <td class="trade-x-type">Fermeture de la transaction de vente</td>
                //    <td class="trade-x-comment comment">Long</td>
                //    <td class="trade-x-date">2018-07-30&nbsp;03:18</td>
                //    <td class="trade-x-price">8151.9</td>
                // </tr>
                // </tbody>

                if (process) {
                    // automatically send the signal if valid and is not too old
                    GM_xmlhttpRequest({
                        method: "GET",
                        url: url.href,
                        onload: function(response) {
                            console.log("Order #" + tradeId + " transmission result: " + response.responseText);
                        },
                        onerror: function() {
                            console.log("Cannot send order #" + tradeId);
                        }
                    });

                    let msg = "Stragegy " + strategyName + " order (#" + tradeId + ") " + direction + ' ' + entry.children('td.trade-e-date').text() + ' ' + price + ' ' + symbol;
                    console.log(msg)
                    let notification = new Notification(msg, {});
                }
            }
        }
    };

    // init when possible, so timeout, retry... until its ok
    let initializeStrategyWatcher = function() {
        if (trackerInit) {
            return;
        }

        let report = $("div.reports-content");
        if (report.length == 0) {
            setTimeout(initializeStrategyWatcher, 1000);
            return;
        }

        let legend = $("body > div.js-rootresizer__contents > div.layout__area--center > div > div.chart-container-border > div.chart-widget > table > tbody > tr:nth-child(1) > td.chart-markup-table.pane > div > div.pane-legend > div.pane-legend-line.pane-legend-wrap.main > span.pane-legend-line.apply-overflow-tooltip.main > div");
        let label = legend.text().split(', ');

        let numCharts = TradingViewApi.chartsCount();
        for (let i = 0; i < numCharts; ++i) {
            let chart = TradingViewApi.chart(i);

        }

        // reset
        strategyTrackerLastTradeNum = 0;
        report.unbind();

        // get settings
        if (label[0].trim() in SymbolsMap) {
            symbol = SymbolsMap[label[0].trim()];
        } else {
            // default try to remove the middle slash and trim spaces
            symbol = label[0].replace('/', '').trim();
        }

        timeframe = label[1] * 60;  // in seconds

        // settings, but how need to use the active one if many...
        let legends = $("body > div.js-rootresizer__contents > div.layout__area--center > div > div.chart-container-border > div.chart-widget > table > tbody > tr:nth-child(1) > td.chart-markup-table.pane > div > div.pane-legend > div");
        for (let i = 0; i < legends.length; ++i) {
            let elt = legends.eq(i).children("span.pane-legend-line.apply-overflow-tooltip");
            if (elt.text().startsWith("Blue Sky Day")) {
                strategyName = "blueskyday";

                let parts = elt.text().split('(')[1].slice(0,-1).split(', ');
                options = {};
                options.deep = parts[0];
                options.resolution = parts[1];

            } else if (elt.text().startsWith("MA Crossover Strategy")) {
                strategyName = "macrossover";

                let parts = elt.text().split('(')[1].slice(0,-1).split(', ');
                options = {};
                // ...
            } else if (elt.text().startsWith("ChannelBreakOutStrategy")) {
                strategyName = "channelbreakout";
                // ...
                let parts = elt.text().split('(')[1].slice(0,-1).split(', ');
                options = {};
                options.length = parts[0];
            }
        }

        if (symbol == "" || symbol == undefined || symbol == null) {
            alert("Symbol not found, no strategy !");
        } else {
            console.log("TradingView strategy spy started on strategy=" + strategyName + " symbol=" + symbol + ' timeframe=' + timeframe + ' options=' + JSON.stringify(options));

            trackerInit = true;

            report.bind('DOMSubtreeModified', function(e) {
                if (e.target.innerHTML.length > 0) {
                    strategyUpdate(e.target.innerHTML);
                }
            });
        }
    };

    $(document).bind('keydown', function(e) {
        if (e.key == 'l' && event.ctrlKey) {
            locked = !locked;

            if (locked) {
                $("body").append('<div id="siis-locker" style="display: block; width: 100%; height: 100%; position: fixed; margin: 0; padding: 0; top: 0; left: 0; z-index: 1000; background-color: #55111188;"></div>');
            } else {
                $("#siis-locker").remove();
            }

            let msg = "";

            if (locked) {
                msg = "TradingView strategy spy - screen is now locked";
            } else {
                msg = "TradingView strategy spy - screen is now released";
            }

            console.log(msg);
            return false;
        } else if (e.key == 'y' && event.ctrlKey) {
            // @todo play pause + notification
            playpause = !playpause;

            let msg = "";

            if (playpause) {
                msg = "TradingView strategy spy - RE copying signals";
            } else {
                msg = "TradingView strategy spy - PAUSE copying signals";
            }

            console.log(msg);
            let notification = new Notification(msg, {});

            return false;
        } else if (e.key == 'i' && event.ctrlKey) {
            let msg = "TradingView strategy spy - Restarting...";

            console.log(msg);
            let notification = new Notification(msg, {});

            // force restart
            restart();

            return false;
        } else if (e.key == 'm' && event.ctrlKey) {
            let msg = "TradingView strategy spy - Force send last signal...";

            console.log(msg);
            let notification = new Notification(msg, {});

            // force restart
            sendLast();

            return false;
        } 
    });

    restart();
})();
