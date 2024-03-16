import configparser
import datetime
import json
import os.path
import re
import spotipy
import string
from twitchio.ext import commands
from datetime import datetime


CONFIG_FILE = 'config.ini'
COMMANDS_FILE = 'commands.json'
config = configparser.ConfigParser()
KEYWORD_PATTERN = r'\[([^\]]+)\]'
debug = True


def is_user_allowed(author):
    return author.is_subscriber or author.is_vip or author.is_mod or author.is_broadcaster


def print_to_logs(message):
    # Get current timestamp in the specified format
    timestamp = datetime.now().strftime('%d/%m/%y - %H:%M')
    # Format the log entry
    log_entry = f"{timestamp}: {message}\n"
    if debug:
        print(log_entry.strip("\n"))
    # Open the log file and append the log entry
    with open("log.txt", 'a', 'utf-8') as file:
        file.write(log_entry)


def replace_keywords(message: string, ctx: commands.Context):
    matches = re.findall(KEYWORD_PATTERN, message)
    for m in matches:
        match m:
            case "sender":
                return re.sub(KEYWORD_PATTERN, ctx.author.mention, message)


class TwitchBot(commands.Bot):
    def __init__(self):
        config.read(CONFIG_FILE)
        print_to_logs(f"Connecting to {config.get('twitch', 'channel')}")
        self.channel = config.get('twitch', 'channel')
        super().__init__(token=config.get('twitch-token', 'access_token'), prefix="!", initial_channels=["#" + self.channel])
        self.load_commands()

    def load_commands(self):
        if os.path.exists(COMMANDS_FILE):
            with open(COMMANDS_FILE, "r") as f:
                commands_json = json.load(f)
            for command, message in commands_json.items():
                # Use a closure to correctly capture 'message' for each command
                async def command_handler(ctx: commands.Context, msg=message):
                    msg = replace_keywords(msg, ctx)
                    await ctx.send(msg)

                # Dynamically set the name of the handler to match the command
                command_handler.__name__ = command
                # Use the command decorator to register the command
                self.command(name=command)(command_handler)

    async def event_ready(self):
        # Notify us when everything is ready!
        # We are logged in and ready to chat and use commands...
        print_to_logs(f'Logged in as | {self.nick} to {self.channel}')
        # print(f'User id is | {self.user_id}')

    async def event_message(self, message):
        # Messages with echo set to True are messages sent by the bot...
        # For now, we just want to ignore them...
        if message.echo:
            return
        # print_to_logs(json.dumps(message.tags))
        # Print the contents of our message to console...
        print_to_logs(f"{message.author.name}, {message.content}")
        # Since we have commands and are overriding the default `event_message`
        # We must let the bot know we want to handle and invoke our commands...
        await self.handle_commands(message)

    # @commands.command()
    # async def generic_command(self, ctx: commands.Context, message: string):
    #     if ctx.author.is_subscriber or ctx.author.is_vip or ctx.author.is_mod:
    #         await ctx.send(message)
    #     else:
    #         print(f"Ignored {ctx.message}")

    @commands.command()
    async def play(self, ctx: commands.Context):
        if is_user_allowed(ctx.author):
            sp = spotipy.Spotify(auth=config.get("spotify-token", "access_token"))
            for a in sp.devices()["devices"]:
                if a["is_active"]:
                    sp.start_playback(a["id"])
                    await ctx.send('Played!')

    @commands.command()
    async def pause(self, ctx: commands.Context):
        if is_user_allowed(ctx.author):
            sp = spotipy.Spotify(auth=config.get("spotify-token", "access_token"))
            for a in sp.devices()["devices"]:
                if a["is_active"]:
                    sp.pause_playback(a["id"])
                    await ctx.send('Paused!')

    @commands.command()
    async def sr(self, ctx: commands.Context):
        if is_user_allowed(ctx.author):
            sp = spotipy.Spotify(auth=config.get("spotify-token", "access_token"))

            song = ctx.message.content.strip("!sr")
            song = song.split("/")[-1]
            if "?" in song:
                song = song.split("?")[0]
            sp.add_to_queue(f"spotify:track:{song}")
            await ctx.send('Added!')

