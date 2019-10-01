# @date 2018-08-07
# @author Frederic SCHERMA
# @license Copyright (c) 2018 Dream Overflow
# 1broker.com watcher implementation

import http.client
import urllib
import json
import time

from datetime import datetime

from watcher.watcher import Watcher
from watcher.author import Author
from watcher.position import Position
from notifier.signal import Signal

from terminal.terminal import Terminal


class OneBrokerWatcher(Watcher):
    """
    1broker is now closed.

    @deprecated no longer authorized broker.

    # @todo use the 1broker connector to watch social positions and live data (using ws)
    # @todo fetch_market and store
    # @todo fetch tick and candles and store
    # @todo store social buy/sell signals
    """

    def __init__(self, service, name="1broker.com"):
        super().__init__(name, service, Watcher.WATCHER_ALL)

        self._host = "1broker.com"
        self._base_url = "/api/v2/"
        self._connected = False
        self._checkout = False

        # identity
        identity = service.identity(self._name)
        if identity:
            self.__apitoken = identity.get('api-key')
            self._host = identity.get('host')

    def connect(self):
        super().connect()

        self._conn = http.client.HTTPSConnection(self._host, timeout=10)

        var = {
            'pretty': 'false',
            'token': self.__apitoken
        }

        url = self._base_url + '?' + urllib.parse.urlencode(var)
        self._conn.request("GET", url)

        response = self._conn.getresponse() 
        data = response.read()

        if response.status == 200:
            self._connected = True
            self._ready = True

            self.service.notify(Signal.SIGNAL_WATCHER_CONNECTED, self.name, time.time())
        else:
            self._connected = False

    @property
    def connected(self):
        return self._connected

    @Watcher.mutexed
    def checkout(self):
        var = {
            'pretty': 'false',
            'token': self.__apitoken,
            'limit': 20,
            'offset': 0
        }

        # checkout social traders details and instantiates authors models
        watcher_config = self.service.watcher_config(self._name)

        for trader in watcher_config.get('authors'):
            trader_id = trader['id']
            var['user_id'] = trader_id

            url = self._base_url + 'social/profile_trades.php?' + urllib.parse.urlencode(var)

            self._conn.request("GET", url)

            response = self._conn.getresponse()
            data = response.read()

            if response.status != 200:
                Terminal.inst().error("Http error getting %s user %s trades !" % (self.name, trader_id))
                continue

            data = json.loads(data)

            if data['error'] or data['warning']:
                Terminal.inst().error("API error getting %s user %s trades !" % (self.name, trader_id))
                continue

            server_date = datetime.strptime(data['server_time'], "%Y-%m-%dT%H:%M:%S.%fZ")

            user_id = data['response']['user_id']
            user_name = data['response']['username']
            risk_score = int(data['response']['risk_score'])

            # author id stored as string but used as integer into queries
            author = Author(self, str(user_id), user_name)
            self._authors[str(user_id)] = author

            author.risk_score = risk_score
            author.success_rate = risk_score

            Terminal.inst().info("Found user %s id %s (risk:%i)" % (user_name, user_id, risk_score))
            # @todo logger

            self.service.notify(Signal.SIGNAL_AUTHOR_ADDED, self.name, author)

        self._checkout = True       

    def pre_run(self):
        super().pre_run()

        if self._connected:
            self.checkout()

    def post_run(self):
        super().post_run()

    def disconnect(self):
        super().disconnect()
        self._conn = None
        self._connected = False
        self._authors = {}
        self._checkout = False
        self._ready = False

    def update(self):
        if not super().update():
            return

        if not self._connected:
            # try reconnect
            time.sleep(10)
            self.connect()
            return

        if not self._checkout:
            # need checkout performed before update
            self.checkout()
            if not self._checkout:              
                return

        self.lock()

        # update position of followed authors/traders
        for author_id, author in self._authors.items():
            var = {
                'pretty': 'false',
                'token': self.__apitoken,
                'limit': 20,
                'offset': 0,
                'user_id': int(author_id)
            }

            # https://1broker.com/api/v2/social/profile_trades.php?token=Aa508b7a7a5ffba14908bded38a88ee8&pretty=true&user_id=71368&limit=10&offset=0
            url = self._base_url + 'social/profile_trades.php?' + urllib.parse.urlencode(var)

            self._conn.request("GET", url)

            response = self._conn.getresponse()
            data = response.read()

            if response.status != 200:
                Terminal.inst().error("Http error getting %s user %s trades !" % (self.name, author_id))
                continue

            data = json.loads(data)

            if data['error'] or data['warning']:
                Terminal.inst().error("API Error getting %s user %s trades !" % (self.name, author_id))
                continue

            try:
                server_date = datetime.strptime(data['server_time'], "%Y-%m-%dT%H:%M:%S.%fZ")
            except:
                server_date = datetime.strptime(data['server_time'], "%Y-%m-%dT%H:%M:%SZ")

            open_trades = data['response']['trading_ideas_open']
            closed_trades = data['response']['trading_ideas_closed']

            for t in open_trades:
                position_id = t['position_id']
                position = Position(self, position_id, author)

                direction = Position.LONG if t['direction'] == 'long' else Position.SHORT
                date_created = datetime.strptime(t['date_created'], "%Y-%m-%dT%H:%M:%SZ") # .%fZ")
                is_open = t['is_open']

                if not is_open:
                    # should be open...
                    continue

                symbol = t['symbol']
                profit_loss_percent = float(t['profit_loss_percent'])
                comment_count = t['comment_count']   # @todo use as indicateur
                leverage = float(t['leverage'])

                if self._positions.get(position_id):
                    # already exists, just update the profit_loss_percent value
                    
                    # retrieve the position
                    position = self._positions.get(position_id)
                    position.profit_loss_rate = profit_loss_percent * 0.01

                    continue

                #
                # get position details
                #

                var = {
                    'pretty': 'false',
                    'token': self.__apitoken,
                    'position_id': position_id
                }

                # https://1broker.com/api/v2/position/shared/get.php?token=Aa508b7a7a5ffba14908bded38a88ee8&pretty=true&position_id=4459904
                url = self._base_url + 'position/shared/get.php?' + urllib.parse.urlencode(var)

                self._conn.request("GET", url)

                response = self._conn.getresponse()
                data = response.read()

                if response.status != 200:
                    Terminal.inst().error("Http error getting %s open position %s !" % (self.name, position_id))
                    continue

                data = json.loads(data)

                if data['error'] or data['warning']:
                    Terminal.inst().error("API Error getting %s open position %s !" % (self.name, position_id))
                    continue

                p = data['response']

                entry_price = float(p['entry_price'])
                stop_loss = float(p['stop_loss']) if p['stop_loss'] is not None else None
                take_profit = float(p['take_profit']) if p['take_profit'] is not None else None
                trailing_stop_loss = p['trailing_stop_loss']
                comments = p['comments']

                # @todo comments +/- 'upvotes' 'downvotes' 'deleted' 'content' 'comment_id' 'username' 'user_id' 'date_created'
                # => make a confidence score + alert at threshold

                # quantity is not known from the copier, let it to 0
                position.symbol = symbol
                position.entry(direction, 0.0, entry_price, stop_loss, take_profit, date_created, leverage=leverage, trailing_stop_loss=trailing_stop_loss)

                # add position
                self._positions[position_id] = position

                self.service.notify(Signal.SIGNAL_SOCIAL_ENTER, self.name, position)

            for t in closed_trades:
                position_id = t['position_id']

                # retrieve the position
                position = self._positions.get(position_id)

                if position is None:
                    # Terminal.inst().error("Closed position %s cannot be found !" % (position_id,))
                    continue

                if position.status == Position.POSITION_CLOSED:
                    # already closed
                    continue

                #
                # get position details
                #

                var = {
                    'pretty': 'false',
                    'token': self.__apitoken,
                    'position_id': position_id
                }

                # https://1broker.com/api/v2/position/shared/get.php?token=Aa508b7a7a5ffba14908bded38a88ee8&pretty=true&position_id=4459904
                url = self._base_url + 'position/shared/get.php?' + urllib.parse.urlencode(var)

                self._conn.request("GET", url)

                response = self._conn.getresponse()
                data = response.read()

                if response.status != 200:
                    Terminal.inst().error("Http error getting %s closed position %s !" % (self.name, position_id))
                    continue

                data = json.loads(data)

                if data['error'] or data['warning']:
                    Terminal.inst().error("API Error getting %s closed position %s !" % (self.name, position_id))
                    continue

                p = data['response']

                profit_loss_percent = float(t['profit_loss_percent'])
                exit_price = float(p['exit_price']) if p['exit_price'] is not None else None
                date_closed = datetime.strptime(t['date_closed'], "%Y-%m-%dT%H:%M:%SZ") # .%fZ")

                position.exit(exit_price, date_closed)
                position.profit_loss_rate = profit_loss_percent * 0.01

                # Terminal.inst().info("Exited position %s found !" % (position_id,), view='status')

                self.service.notify(Signal.SIGNAL_SOCIAL_EXIT, self.name, position)

        self.unlock()

    def post_update(self):
        super().post_update()

        # ok for social but not if websocket
        time.sleep(0.5)
