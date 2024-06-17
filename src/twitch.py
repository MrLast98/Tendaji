import json
import sqlite3
import ssl
from asyncio import Event, gather

import websockets
from websockets import ConnectionClosedOK, ConnectionClosedError

from manager_utils import PrintColors
from src.twitch_eventsub_utils import get_user_info, subscribe_to_follow, handle_eventsub_messages
from twitch_commands import TwitchCommands
from twitch_ircchat_utils import handle_irc_message, authenticate, join_channel

EVENTSUB_URL = 'wss://eventsub.wss.twitch.tv/ws'
CHAT_URL = 'wss://irc-ws.chat.twitch.tv:443'


class TwitchWebSocketManager:
    def __init__(self, manager):
        self.manager = manager
        self.channel = self.manager.configuration['twitch']['channel']
        self.manager.print.print_to_logs(f"Connecting to {self.channel}", self.manager.print.GREEN)
        self.complex_commands = {}
        self.simple_commands = {}
        self.chat_websocket = None
        self.eventsub_websocket = None
        self.shutdown = Event()
        self.twitch_commands = TwitchCommands(self)
        self.ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self.ssl_context.load_cert_chain(certfile=self.manager.resource_path('localhost.ecc.crt'),
                                    keyfile=self.manager.resource_path('localhost.ecc.key'))
        self.user = get_user_info(self)
        self.last_message_id = None
        self.conn = sqlite3.connect('/home/tendaji/Work/chatAnalysis/database/database.sqlite')
        self.cursor = self.conn.cursor()

    @property
    def headers(self):
        return {
            'Authorization': f'Bearer {self.manager.configuration['twitch-token']['access_token']}',
            'Client-Id': self.manager.configuration['twitch']['client_id'],
            'Content-Type': 'application/json'
        }

    async def eventsub_connection(self):
        async with websockets.connect(EVENTSUB_URL, ssl=self.ssl_context) as websocket:
            self.eventsub_websocket = websocket
            message = await self.eventsub_websocket.recv()
            message = json.loads(message)
            self.last_message_id = message['metadata']['message_id']
            subscribe_to_follow(self, message['payload']['session']['id'])
            try:
                while not self.shutdown.is_set():
                    message = await self.eventsub_websocket.recv()
                    message = json.loads(message)
                    if self.last_message_id != message['metadata']['message_id']:
                        self.last_message_id = message['metadata']['message_id']
                        if message['metadata']['message_type'] != 'session_keepalive':
                            # print(f"Eventsub Message: {message}")
                            handle_eventsub_messages(self, message)
            except ConnectionClosedOK:
                pass
            except ConnectionClosedError as e:
                print(f"Error: {e}")

    async def chat_connection(self):
        async with websockets.connect(CHAT_URL, ssl=self.ssl_context) as websocket:
            self.chat_websocket = websocket
            await authenticate(self, self.chat_websocket)
            await join_channel(self, self.chat_websocket)
            try:
                while not self.shutdown.is_set():
                    message = await self.chat_websocket.recv()
                    # print(f"Chat Message: {message}")
                    await handle_irc_message(self, message)
            except ConnectionClosedOK:
                pass
            except ConnectionClosedError as e:
                print(f"Error: {e}")

    async def run(self):
        # Run both connections in parallel
        await gather(
            self.eventsub_connection(),
            self.chat_connection()
        )
        self.cursor.close()
        # await self.chat_connection()

    async def close(self):
        if self.chat_websocket:
            await self.chat_websocket.close()
        if self.eventsub_websocket:
            await self.eventsub_websocket.close()
        self.manager.print.print_to_logs('Twitch Bot Shut Down!', PrintColors.YELLOW)
