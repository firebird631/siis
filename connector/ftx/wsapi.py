import asyncio
import hmac
import json
import time
import traceback
from json import JSONDecodeError
from typing import Optional

import websockets
from websockets.legacy.client import WebSocketClientProtocol

from .fifo import AsyncFifoQueue

import logging
logger = logging.getLogger('siis.connector.ftx')
error_logger = logging.getLogger('siis.error.connector.ftx')
traceback_logger = logging.getLogger('siis.traceback.connector.ftx')


class FtxWebSocketClient:
    """
    Basic FTX WebSocket client

    See: https://docs.ftx.com/#websocket-api
    """
    _ws: Optional[WebSocketClientProtocol]

    def __init__(self,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 subaccount_name: Optional[str] = None,
                 queue_size: int = 1024,
                 socket_url='wss://ftx.com/ws',
                 verbose=False):
        """
        Create a websocket client

        :param api_key: api key
        :param api_secret: api secret
        :param subaccount_name: subaccount
        :param queue_size: size for message queue
        :param socket_url: ftx websocket url
        :param verbose: set to True to log messages and connection status
        """
        self._api_key = api_key
        self._api_secret = api_secret
        self._subaccount_name = subaccount_name
        self._ws = None
        self._last_ping = None
        self.verbose = verbose
        self.socket_url = socket_url
        self._queue = AsyncFifoQueue(maxsize=queue_size)

    async def connect(self):
        """
        Connect to the websocket
        :return:
        """
        self._ws = await websockets.connect(self.socket_url)
        self._log('websocket connected')
        asyncio.create_task(self._loop_fn())
        asyncio.create_task(self._ping_loop_fn())

    async def disconnect(self):
        """
        Disconnects the websocket if it's open
        :return:
        """
        if self._ws and self._ws.open:
            await self._ws.close()
            self._ws = None

    @property
    def connected(self):
        """
        True if the websocket is connected and open
        """
        return self._ws and self._ws.open

    @property
    def messages_dropped(self):
        """
        The amount of messages dropped due to the queue being full.
        Increase max_queue_size or try to process messages faster if messages get dropped.
        :return:
        """
        return self._queue.items_dropped

    def _log(self, *args, **kwargs):
        if self.verbose:
            logger.debug(*args, **kwargs)
            # print(*args, **kwargs)

    def _on_message(self, msg):
        if msg and 'type' in msg:
            if msg['type'] != 'pong':
                self._queue.put_nowait(msg)
            else:
                dt = time.time() - self._last_ping
                self._log(f'pong ({round(dt, 2)}s)')

    async def send_message(self, msg):
        """
        Send a message on the websocket

        Example:
            ``client.send_message({'op': 'ping'})``

        :param msg: the message
        """
        self._log('->', msg)
        await self._ws.send(json.dumps(msg))

    async def _ping_loop_fn(self):
        """
        Ping keep-alive loop, sends a ping message every 15 seconds
        """
        await asyncio.sleep(1)
        while self.connected:
            if not self._last_ping:
                self._log('ping')
            self._last_ping = time.time()
            await self.send_message({'op': 'ping'})
            await asyncio.sleep(15)

    async def _loop_fn(self):
        """
        Main message loop
        """
        while self.connected:
            try:
                msg = await self._ws.recv()
                try:
                    self._on_message(json.loads(msg))
                except JSONDecodeError:
                    error_logger.error('could not parse JSON : %s' % msg)
            except:
                self._ws = None
                self._queue.put_nowait(None)
                error_logger.error('websocket closed with error')
                traceback_logger.error(traceback.format_exc())

    async def login(self):
        assert self._api_key and self._api_secret, 'api_key and api_secret must be set to use login()'
        ts = int(time.time() * 1000)
        sign = hmac.new(self._api_secret.encode(), f'{ts}websocket_login', 'sha256').hexdigest()
        msg = {'op': 'login', 'args': {'key': self._api_key, 'sign': sign, 'time': ts}}
        await self.send_message(msg)

    async def subscribe(self, channel: str, market: str):
        """
        Subscribe to a channel and market

        :param channel: the channel
        :param market: the market
        """
        await self.send_message({
            'op': 'subscribe',
            'channel': channel,
            'market': market
        })

    async def unsubscribe(self, channel: str, market: str):
        """
        Unsubscribe from a channel and market

        :param channel: the channel
        :param market: the market
        """
        await self.send_message({
            'op': 'unsubscribe',
            'channel': channel,
            'market': market
        })

    async def recv(self):
        """
        Receives a single message from the websocket or waits until one is available.
        `None` is returned when the websocket is closed or closing.

        :return: a message dict
        """
        if not self.connected:
            return None
        return await self._queue.get()
