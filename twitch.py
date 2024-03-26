import configparser
import json
import os.path
import re
import spotipy
import string
from requests import post
from time import time

from twitchio.ext import commands
from twitchio.ext.commands import Context

from logger import print_to_logs, PrintColors
from urllib.parse import urlencode
from webbrowser import open as wbopen

CONFIG_FILE = 'config.ini'
COMMANDS_FILE = 'commands.json'
config = configparser.ConfigParser()
KEYWORD_PATTERN = r'\[([^\]]+)\]'
url_pattern = r'\b(?:https?|ftp):\/\/[\w\-]+(\.[\w\-]+)+[/\w\-?=&#%]*\b'
TWITCH_AUTHORIZATION_URL = 'https://id.twitch.tv/oauth2/authorize'
TWITCH_TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
scope_twitch = 'chat:read chat:edit'


def is_user_allowed(author):
    return author.is_subscriber or author.is_vip or author.is_mod or author.is_broadcaster


def replace_keywords(message: string, ctx: commands.Context):
    matches = re.findall(KEYWORD_PATTERN, message)
    for m in matches:
        match m:
            case "sender":
                return re.sub(KEYWORD_PATTERN, ctx.author.mention, message)


def get_player():
    config.read(CONFIG_FILE)
    sp = spotipy.Spotify(auth=config.get("spotify-token", "access_token"))
    for a in sp.devices()["devices"]:
        if a["is_active"]:
            return sp, a['id']
        else:
            return None, None


def print_queue_to_file(queue):
    with open("queue.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(queue))


def start_twitch_oauth_flow():
    params = {
        'client_id': config.get('twitch', 'client_id'),
        'redirect_uri': 'https://localhost:5000/callback_twitch',
        'response_type': 'code',
        'scope': scope_twitch
    }
    url = f"{TWITCH_AUTHORIZATION_URL}?{urlencode(params)}"
    wbopen(url)


def retrieve_token_info(code):
    payload = {
        'client_id': config.get('twitch', 'client_id'),
        'client_secret': config.get('twitch', 'client_secret'),
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': 'https://localhost:5000/callback_twitch'
    }
    response = post(TWITCH_TOKEN_URL, data=payload)
    response_json = response.json()
    access_token = response_json.get('access_token')
    refresh_token = response_json.get('refresh_token')
    expires_in = response_json.get('expires_in')
    # Calculate the expiration timestamp and save it
    expires_at = int(time()) + expires_in
    return access_token, refresh_token, expires_at


class TwitchBot(commands.Bot):
    def __init__(self):
        config.read(CONFIG_FILE)
        print_to_logs(f"Connecting to {config.get('twitch', 'channel')}", PrintColors.GREEN)
        self.channel = config.get('twitch', 'channel')
        self.queue = []
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
                print_to_logs(f"Registered command {command}", PrintColors.BRIGHT_PURPLE)
                self.command(name=command)(command_handler)

    async def event_ready(self):
        # Notify us when everything is ready!
        # We are logged in and ready to chat and use commands...
        print_to_logs(f'Logged in as | {self.nick} to {self.channel}', PrintColors.GREEN)
        # print(f'User id is | {self.user_id}')

    async def event_message(self, message):
        # Messages with echo set to True are messages sent by the bot...
        # For now, we just want to ignore them...
        if message.echo:
            return
        # print_to_logs(json.dumps(message.tags))
        # Print the contents of our message to console...
        print_to_logs(f"{message.author.name}, {message.content}", PrintColors.BRIGHT_PURPLE)
        # Since we have commands and are overriding the default `event_message`
        # We must let the bot know we want to handle and invoke our commands...
        await self.handle_commands(message)

    async def event_command_error(self, context: Context, error: Exception) -> None:
        print_to_logs(f"ERROR: Missing command. {error }", PrintColors.RED)

    @commands.command()
    async def play(self, ctx: commands.Context):
        if is_user_allowed(ctx.author):
            sp, sp_id = get_player()
            if sp is not None and sp_id is not None:
                sp.start_playback(sp_id)
                print_to_logs("Resumed!", PrintColors.YELLOW)
                await ctx.send('Resumed!')
            else:
                await ctx.send('No player found - Please start playing a song before requesting!')

    @commands.command()
    async def pause(self, ctx: commands.Context):
        if is_user_allowed(ctx.author):
            sp, sp_id = get_player()
            if sp is not None and sp_id is not None:
                sp.pause_playback(sp_id)
                print_to_logs("Paused!", PrintColors.YELLOW)
                await ctx.send('Paused!')
            else:
                await ctx.send('No player found - Please start playing a song before requesting!')

    @commands.command()
    async def skip(self, ctx: commands.Context):
        if is_user_allowed(ctx.author):
            sp, sp_id = get_player()
            if sp is not None and sp_id is not None:
                sp.next(sp_id)
                self.queue.pop(0)
                print_to_logs("Skipped!", PrintColors.YELLOW)
                await ctx.send('Skipped!')
            else:
                await ctx.send('No player found - Please start playing a song before requesting!')

    @commands.command()
    async def sr(self, ctx: commands.Context):
        if is_user_allowed(ctx.author):
            sp, _ = get_player()
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
                    "author": f"{query["artists"][0]["name"]}",
                    "requested_by": f"{ctx.author.display_name}",
                    "duration": query["duration_ms"]
                })
                print_queue_to_file(self.queue)
                print_to_logs(f'Aggiunto {query["name"]} - {query["artists"][0]["name"]} alla coda!', PrintColors.BRIGHT_PURPLE)
                await ctx.send(f'Aggiunto {query["name"]} - {query["artists"][0]["name"]}!')
            else:
                await ctx.send('No player found - Please start playing a song before requesting!')
