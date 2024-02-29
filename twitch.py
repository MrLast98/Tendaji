import spotipy
from twitchio.ext import commands
import configparser


CONFIG_FILE = 'config.ini'
config = configparser.ConfigParser()
config.read(CONFIG_FILE)


class TwitchBot(commands.Bot):
    def __init__(self):
        config.read(CONFIG_FILE)
        print(f"Connecting to {config.get('twitch', 'channel')}")
        super().__init__(token=config.get('twitch', 'token'), prefix="!", initial_channels=["#" + config.get('twitch', 'channel')])

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
        # Print the contents of our message to console...
        print(message.content)

        # Since we have commands and are overriding the default `event_message`
        # We must let the bot know we want to handle and invoke our commands...
        await self.handle_commands(message)

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
        sp = spotipy.Spotify(auth=config.get("spotify", "token"))

        song = ctx.message.content.strip("!sr")
        song = song.split("/")[-1]
        if "?" in song:
            song = song.split("?")[0]
        sp.add_to_queue(f"spotify:track:{song}")

        await ctx.send('Added!')

