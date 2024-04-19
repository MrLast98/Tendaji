import configparser
import json
import os.path
import re
import string
from asyncio import Event

from twitchio.ext import commands
from twitchio.ext.commands import Context

from defaults import DEFAULT_COMMANDS
from manager_utils import PrintColors

from spotify import pause, add_song_id, play, query_for_song, get_track_by_id, skip, get_queue

COMMANDS_FILE = 'config/commands.json'
config = configparser.ConfigParser()
KEYWORD_PATTERN = r'\[([^\]]+)\]'
url_pattern = r'\b(?:https?|ftp):\/\/[\w\-]+(\.[\w\-]+)+[/\w\-?=&#%]*\b'


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


def parse_song(song):
    artists = [a["name"] for a in song["artists"]]
    return {
        "name": song["name"],
        "artists": ", ".join(artists),
        "id": song["id"]
    }


class TwitchBot(commands.Bot):
    def __init__(self, manager):
        self.manager = manager
        self.manager.print.print_to_logs(f"Connecting to {self.manager.configuration['twitch']['channel']}",
                                         self.manager.print.GREEN)
        self.channel = self.manager.configuration['twitch']['channel']
        self.queue = []
        self.token_flag = Event()
        self.complex_commands = {}
        super().__init__(token=self.manager.configuration['twitch-token']['access_token'], prefix="!",
                         initial_channels=["#" + self.channel])

    async def event_ready(self):
        self.load_commands()
        self.manager.print.print_to_logs(f'Logged in as {self.nick} to {self.channel}', self.manager.print.GREEN)

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

    async def event_command_error(self, context: Context, error: Exception) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        self.manager.print.print_to_logs(f"{error}", PrintColors.RED)

    def load_commands(self):
        if os.path.exists(COMMANDS_FILE):
            with open(COMMANDS_FILE, "r") as f:
                commands_json = json.load(f)
            self.load_simple_commands(commands_json=commands_json["simple"])
            self.set_complex_commands(commands_json=commands_json["complex"])
        else:
            self.manager.print.print_to_logs("Commands file not found", self.manager.print.RED)
            self.manager.print.print_to_logs("Creating new one with default commands", self.manager.print.WHITE)
            defaults = DEFAULT_COMMANDS
            for command, _ in self.commands.items():
                defaults["complex"][command] = {}
                defaults["complex"][command]["enabled"] = True
                defaults["complex"][command]["level"] = "ANY"
            with open("config/commands.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(defaults, indent=4))
            self.load_commands()

    def load_simple_commands(self, commands_json):
        for command, context in commands_json.items():
            if context["enabled"]:
                async def command_handler(ctx: commands.Context, msg=context["message"], level=context["level"]):
                    if self.is_user_allowed(ctx, level):
                        msg = replace_keywords(msg, ctx)
                        await ctx.send(msg)

                # Dynamically set the name of the handler to match the command
                command_handler.__name__ = command
                # Use the command decorator to register the command
                self.manager.print.print_to_logs(f"Registered command {command}", self.manager.print.BRIGHT_PURPLE)
                self.command(name=command)(command_handler)

    def set_complex_commands(self, commands_json):
        for command, context in commands_json.items():
            if context["enabled"]:
                self.complex_commands[command] = context["level"]

    def is_user_allowed(self, ctx, level):
        author = ctx.author
        match level:
            case "BROADCASTER":
                if not author.is_broadcaster:
                    self.manager.print.print_to_logs(f"User {author.display_name} not allowed to run this command",
                                                     self.manager.print.YELLOW)
                    return False
                return True
            case "MOD":
                if not author.is_mod and not author.is_broadcaster:
                    self.manager.print.print_to_logs(f"User {author.display_name} not allowed to run this command",
                                                     self.manager.print.YELLOW)
                    return False
                return True
            case "VIP":
                if not author.is_vip and not author.is_mod and not author.is_broadcaster:
                    self.manager.print.print_to_logs(f"User {author.display_name} not allowed to run this command",
                                                     self.manager.print.YELLOW)
                    return False
                return True
            case "SUB":
                if not author.is_subscriber and not author.is_vip and not author.is_mod and not author.is_broadcaster:
                    self.manager.print.print_to_logs(f"User {author.display_name} not allowed to run this command",
                                                     self.manager.print.YELLOW)
                    return False
                return True
            case _:
                return True

    def is_command_enabled(self, command):
        return command in set(self.complex_commands.keys())

    @commands.command()
    async def song(self, ctx: commands.Context):
        if self.is_command_enabled(ctx.command.name) and self.is_user_allowed(ctx, self.complex_commands[ctx.command.name]):
            response = get_queue(self.manager.configuration["spotify-token"]["access_token"])
            currently_playing = parse_song(response["currently_playing"])
            await ctx.send(currently_playing["name"])

    @commands.command()
    async def play(self, ctx: commands.Context):
        if self.is_command_enabled(ctx.command.name) and self.is_user_allowed(ctx, self.complex_commands[ctx.command.name]):
            play(self.manager.configuration["spotify-token"]["access_token"])
            self.manager.print.print_to_logs("Resumed!", PrintColors.YELLOW)
            await ctx.send('Resumed!')

    @commands.command()
    async def pause(self, ctx: commands.Context):
        if self.is_command_enabled(ctx.command.name) and self.is_user_allowed(ctx, self.complex_commands[ctx.command.name]):
            pause(self.manager.configuration["spotify-token"]["access_token"])
            self.manager.print.print_to_logs("Paused!", self.manager.print.YELLOW)
            await ctx.send('Paused!')

    @commands.command()
    async def skip(self, ctx: commands.Context):
        if self.is_command_enabled(ctx.command.name) and self.is_user_allowed(ctx, self.complex_commands[ctx.command.name]):
            skip(self.manager.configuration["spotify-token"]["access_token"])
            self.manager.print.print_to_logs("Skipped!", self.manager.print.YELLOW)
            await ctx.send('Skipped!')

    @commands.command()
    async def sbagliato(self, ctx: commands.Context):
        if self.is_command_enabled(ctx.command.name) and self.is_user_allowed(ctx, self.complex_commands[ctx.command.name]):
            await ctx.send("Oh No")

    @commands.command()
    async def sr(self, ctx: commands.Context):
        if self.is_command_enabled(ctx.command.name) and self.is_user_allowed(ctx, self.complex_commands[ctx.command.name]):
            song = ctx.message.content.strip("!sr ")
            if re.search(url_pattern, song):
                song = song.split("/")[-1]
                if "?" in song:
                    song = song.split("?")[0]
                query = get_track_by_id(self.manager.configuration["spotify-token"]["access_token"], song)
                add_song_id(self.manager.configuration["spotify-token"]["access_token"], song)
            else:
                query = query_for_song(self.manager.configuration["spotify-token"]["access_token"], song)
                add_song_id(self.manager.configuration["spotify-token"]["access_token"], query["id"])
            # self.queue.append({
            #     "title": f'{query["name"]}',
            #     "author": f"{query['artists'][0]['name']}",
            #     "requested_by": f"{ctx.author.display_name}",
            #     "duration": query["duration_ms"]
            # })
            # print_queue_to_file(self.queue)
            self.manager.print.print_to_logs(f'Aggiunto {query["name"]} - {query["artists"][0]["name"]} alla coda!',
                                             self.manager.print.BRIGHT_PURPLE)
            await ctx.send(f'Aggiunto {query["name"]} - {query["artists"][0]["name"]}!')
