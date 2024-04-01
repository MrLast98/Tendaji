import configparser
import json
import os.path
import re
import string
from time import time

import spotipy
from spotipy import SpotifyException
from twitchio.ext import commands
from twitchio.ext.commands import Context

from manager_utils import PrintColors

COMMANDS_FILE = 'config/commands.json'
config = configparser.ConfigParser()
KEYWORD_PATTERN = r'\[([^\]]+)\]'
url_pattern = r'\b(?:https?|ftp):\/\/[\w\-]+(\.[\w\-]+)+[/\w\-?=&#%]*\b'


def is_user_allowed(author):
    return author.is_subscriber or author.is_vip or author.is_mod or author.is_broadcaster


def replace_keywords(message: string, ctx: commands.Context):
    matches = re.findall(KEYWORD_PATTERN, message)
    if len(matches) > 0:
        for m in matches:
            match m:
                case "sender":
                    return re.sub(KEYWORD_PATTERN, ctx.author.mention, message)
    else:
        return message


def print_queue_to_file(queue):
    with open("queue.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(queue))


class TwitchBot(commands.Bot):
    def __init__(self, manager):
        self.manager = manager
        self.manager.print.print_to_logs(f"Connecting to {self.manager.configuration['twitch']['channel']}", self.manager.print.GREEN)
        self.channel = self.manager.configuration['twitch']['channel']
        self.queue = []
        super().__init__(token=self.manager.configuration['twitch-token']['access_token'], prefix="!",
                         initial_channels=["#" + self.channel])

    async def event_ready(self):
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
                self.manager.print.print_to_logs(f"Registered command {command}", self.manager.print.BRIGHT_PURPLE)
                self.command(name=command)(command_handler)
        self.manager.print.print_to_logs(f'Logged in as | {self.nick} to {self.channel}', self.manager.print.GREEN)

    async def event_message(self, message):
        # Messages with echo set to True are messages sent by the bot...
        # For now, we just want to ignore them...
        if message.echo:
            return
        # PrintColors.print_to_logs(json.dumps(message.tags))
        # Print the contents of our message to console...
        self.manager.print.print_to_logs(f"{message.author.name}, {message.content}", self.manager.print.BLUE)

        # Since we have commands and are overriding the default `event_message`
        # We must let the bot know we want to handle and invoke our commands...
        await self.handle_commands(message)

    # def get_name(self, message):
    #     if message.

    async def event_command_error(self, context: Context, error: Exception) -> None:
        if isinstance(error, commands.CommandNotFound):
            return

        PrintColors.print_to_logs(f"ERROR: Missing command. {error}", PrintColors.RED)

    async def get_player(self):
        sp = spotipy.Spotify(auth=self.manager.configuration["spotify-token"]["access_token"])
        try:
            devices = sp.devices()
        except SpotifyException:
            self.manager.print.print_to_logs("Expired Spotify Token", PrintColors.YELLOW)
            await self.manager.refresh_spotify_token()
        for a in devices["devices"]:
            if a["is_active"]:
                return sp, a['id']
            else:
                return None, None

    @commands.command()
    async def play(self, ctx: commands.Context):
        if is_user_allowed(ctx.author):
            sp, sp_id = await self.get_player()
            if sp is not None and sp_id is not None:
                sp.start_playback(sp_id)
                self.manager.print.print_to_logs("Resumed!", PrintColors.YELLOW)
                await ctx.send('Resumed!')
            else:
                await ctx.send('No player found - Please start playing a song before requesting!')

    @commands.command()
    async def pause(self, ctx: commands.Context):
        if is_user_allowed(ctx.author):
            sp, sp_id = await self.get_player()
            if sp is not None and sp_id is not None:
                sp.pause_playback(sp_id)
                self.manager.print.print_to_logs("Paused!", self.manager.print.YELLOW)
                await ctx.send('Paused!')
            else:
                await ctx.send('No player found - Please start playing a song before requesting!')

    @commands.command()
    async def skip(self, ctx: commands.Context):
        if is_user_allowed(ctx.author):
            sp, sp_id = await self.get_player()
            if sp is not None and sp_id is not None:
                sp.next(sp_id)
                self.queue.pop(0)
                self.manager.print.print_to_logs("Skipped!", self.manager.print.YELLOW)
                await ctx.send('Skipped!')
            else:
                await ctx.send('No player found - Please start playing a song before requesting!')

    @commands.command()
    async def sr(self, ctx: commands.Context):
        if is_user_allowed(ctx.author):
            sp, _ = await self.get_player()
            if sp is not None:
                song = ctx.message.content.strip("!sr")

                if re.search(url_pattern, song):
                    song = song.split("/")[-1]
                    if "?" in song:
                        song = song.split("?")[0]
                    query = sp.track(song)
                    sp.add_to_queue(f"spotify:track:{song}")
                else:
                    query = sp.search(song, type="track")
                    query = query["tracks"]["items"][0]
                    sp.add_to_queue(query["uri"])
                self.queue.append({
                    "title": f'{query["name"]}',
                    "author": f"{query['artists'][0]['name']}",
                    "requested_by": f"{ctx.author.display_name}",
                    "duration": query["duration_ms"]
                })
                print_queue_to_file(self.queue)
                self.manager.print.print_to_logs(f'Aggiunto {query["name"]} - {query["artists"][0]["name"]} alla coda!',
                              self.manager.print.BRIGHT_PURPLE)
                await ctx.send(f'Aggiunto {query["name"]} - {query["artists"][0]["name"]}!')
            else:
                await ctx.send('No player found - Please start playing a song before requesting!')
