import ssl
from asyncio import Event

import websockets

from manager_utils import PrintColors
from twitch_commands import TwitchCommands
from twitch_utils import handle_irc_message, authenticate, join_channel

EVENTSUB_URL = 'wss://eventsub.wss.twitch.tv/ws'
CHAT_URL = 'wss://irc-ws.chat.twitch.tv:443'


class TwitchWebSocketManager:
    def __init__(self, manager):
        self.manager = manager
        self.channel = self.manager.configuration['twitch']['channel']
        self.manager.print.print_to_logs(f"Connecting to {self.channel}", self.manager.print.GREEN)
        self.complex_commands = {}
        self.simple_commands = {}
        self.websocket = None
        self.shutdown = Event()
        self.twitch_commands = TwitchCommands(self)

    async def eventsub_connection(self):
        async with websockets.connect(EVENTSUB_URL) as websocket:
            while True:
                message = await websocket.recv()
                print(f"EventSub Message: {message}")
                # Process the message as needed

    async def chat_connection(self):
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_context.load_cert_chain(certfile=self.manager.resource_path('localhost.ecc.crt'),
                                    keyfile=self.manager.resource_path('localhost.ecc.key'))

        async with websockets.connect(CHAT_URL, ssl=ssl_context) as websocket:
            self.websocket = websocket
            await authenticate(self, self.websocket)
            await join_channel(self, self.websocket)

            while not self.shutdown.is_set():
                message = await self.websocket.recv()
                # print(f"Chat Message: {message}")
                await handle_irc_message(self, message)

    async def run(self):
        # Run both connections in parallel
        # await asyncio.gather(
        #     self.eventsub_connection(),
        #     self.chat_connection()
        # )
        await self.chat_connection()

    async def close(self):
        if self.websocket:
            await self.websocket.close()
        self.manager.print.print_to_logs('Twitch Bot Shut Down!', PrintColors.YELLOW)
