import string
import time

import spotipy
from twitchio.ext import commands
import configparser
import json
from enum import Enum


CONFIG_FILE = 'config.ini'
config = configparser.ConfigParser()
config.read(CONFIG_FILE)


class CommandLevel(Enum):
    SUB = "subscriber"
    VIP = "vip"
    MOD = "moderator"


def is_user_allowed(message, level: CommandLevel):
    return message.tags[level.value] == "1"


class TwitchBot(commands.Bot):
    def __init__(self):
        config.read(CONFIG_FILE)
        print(f"Connecting to {config.get('twitch', 'channel')}")
        super().__init__(token=config.get('twitch', 'token'), prefix="!", initial_channels=["#" + config.get('twitch', 'channel')])
        self.load_commands()

    def load_commands(self):
        with open("commands.json", "r") as f:
            commands_json = json.load(f)
        for command, message in commands_json.items():
            # Use a closure to correctly capture 'message' for each command
            async def command_handler(ctx, command=command, message=message):
                await ctx.send(message)

            # Dynamically set the name of the handler to match the command
            command_handler.__name__ = command
            # Use the command decorator to register the command
            self.command(name=command)(command_handler)

    async def event_ready(self):
        # Notify us when everything is ready!
        # We are logged in and ready to chat and use commands...
        print(f'Logged in as | {self.nick}')
        # print(f'User id is | {self.user_id}')

    async def event_message(self, message):
        # Messages with echo set to True are messages sent by the bot...
        # For now, we just want to ignore them...
        if message.echo:
            return
        print(json.dumps(message.tags))
        # Print the contents of our message to console...
        print(message.content)
        # Since we have commands and are overriding the default `event_message`
        # We must let the bot know we want to handle and invoke our commands...
        await self.handle_commands(message)

    @commands.command()
    async def generic_command(self, ctx: commands.Context, message: string):
        await ctx.send(message)


    @commands.command()
    async def hello(self, ctx: commands.Context):

        await ctx.send(f'Hello {ctx.author.name}!')

    @commands.command()
    async def play(self, ctx: commands.Context):
        sp = spotipy.Spotify(auth=config.get("spotify", "token"))
        for a in sp.devices()["devices"]:
            if a["is_active"]:
                sp.start_playback(a["id"])
                await ctx.send('Played!')

    @commands.command()
    async def pause(self, ctx: commands.Context):
        sp = spotipy.Spotify(auth=config.get("spotify", "token"))
        for a in sp.devices()["devices"]:
            if a["is_active"]:
                sp.pause_playback(a["id"])
                await ctx.send('Paused!')

    @commands.command()
    async def sr(self, ctx: commands.Context):
        # if ctx.message.tags['subscriber'] == "1":
        if is_user_allowed(ctx.message, CommandLevel.SUB):
            sp = spotipy.Spotify(auth=config.get("spotify", "token"))

            song = ctx.message.content.strip("!sr")
            song = song.split("/")[-1]
            if "?" in song:
                song = song.split("?")[0]
            sp.add_to_queue(f"spotify:track:{song}")

            await ctx.send('Added!')
        else:
            print(f"Ignored {ctx.message}")

