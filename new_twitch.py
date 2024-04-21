import asyncio
import ssl
import sys
from os import path

import websockets

from manager_utils import load_configuration_from_json, PrintColors
from twitch_commands import TwitchCommands
from twitch_utils import handle_irc_message, authenticate, join_channel

EVENTSUB_URL = "wss://eventsub.wss.twitch.tv/ws"
CHAT_URL = "wss://irc-ws.chat.twitch.tv:443"


class TwitchWebSocketManager:
    def __init__(self, manager):
        self.manager = manager
        self.channel = self.manager.configuration['twitch']['channel']
        self.manager.print.print_to_logs(f"Connecting to {self.channel}", self.manager.print.GREEN)
        self.queue = []
        self.complex_commands = {}
        self.simple_commands = {}
        self.websocket = None
        self.twitch_commands = TwitchCommands(self)

    async def eventsub_connection(self):
        async with websockets.connect(EVENTSUB_URL) as websocket:
            while True:
                message = await websocket.recv()
                print(f"EventSub Message: {message}")
                # Process the message as needed

    async def chat_connection(self):
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_context.load_cert_chain(certfile=self.manager.resource_path("localhost.ecc.crt"),
                                    keyfile=self.manager.resource_path("localhost.ecc.key"))

        async with websockets.connect(CHAT_URL, ssl=ssl_context) as websocket:
            self.websocket = websocket
            await authenticate(self, self.websocket)
            await join_channel(self, self.websocket)

            while True:
                message = await self.websocket.recv()
                # print(f"Chat Message: {message}")
                await handle_irc_message(self, message)

    async def run(self):
        # Run both connections in parallel
        # await asyncio.gather(
        #     self.eventsub_connection(),
        #     self.chat_connection()
        # )
        await asyncio.gather(self.chat_connection())


class miniManager:
    def __init__(self):
        self.configuration = {}
        self.print = PrintColors()
        load_configuration_from_json(self, "config/config.json")

    @staticmethod
    def resource_path(relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = path.abspath(".")

        return str(path.join(base_path, relative_path))


# Example usage
if __name__ == "__main__":
    minimgr = miniManager()
    twmanager = TwitchWebSocketManager(minimgr)
    asyncio.run(twmanager.run())
