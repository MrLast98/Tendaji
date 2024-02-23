import configparser
import os
import webbrowser
from flask import Flask, request, redirect, session
import requests
from threading import Thread
from urllib.parse import urlencode
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import secrets
from twitchio.ext import commands

# Configuration and Flask App
CONFIG_FILE = 'config.ini'
AUTHORIZATION_URL = 'https://id.twitch.tv/oauth2/authorize'
TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
scope_spotify = "user-read-playback-stat,user-modify-playback-state"
scope_twitch = 'chat:read chat:edit'

config = configparser.ConfigParser()
config.read(CONFIG_FILE)
app = Flask(__name__)
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

auth_manager = None
server = 'irc.chat.twitch.tv'
port = 6697
twitch_thread = None
sp = None


@app.route('/')
def index():
    if not auth_manager:
        return "Spotify OAuth is not initialized. Check your config.ini file."
    auth_url = auth_manager.get_authorize_url()
    return redirect(auth_url)


@app.route('/callback')
def callback():
    session['token_info'] = auth_manager.get_access_token(request.args['code'])
    config.set("spotify", "token", auth_manager.get_access_token(request.args['code'])['access_token'])
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    print("Token retrieved!")
    return redirect('/currently_playing')


@app.route('/currently_playing')
def currently_playing():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    sp = spotipy.Spotify(auth=token_info['access_token'])
    track = sp.current_playback()
    if track is not None:
        track_name = track['item']['name']
        artist_name = track['item']['artists'][0]['name']
        print(f"Currently playing: {track_name} by {artist_name}")
        return f"Currently playing: {track_name} by {artist_name}"
    else:
        print("No track is currently playing.")
        return "No track is currently playing."


@app.route('/callback_twitch')
def callback_twitch():
    code = request.args.get('code')
    payload = {
        'client_id': config.get('twitch', 'client_id'),
        'client_secret': config.get('twitch', 'client_secret'),
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': 'https://localhost:5000/callback_twitch'
    }
    response = requests.post(TOKEN_URL, data=payload)
    response_json = response.json()
    access_token = response_json.get('access_token')

    # Save the access token and other details to config.ini
    if access_token:
        config.set('twitch', 'token', access_token)
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
    else:
        print("Error")


def ensure_config_section_exists(section):
    if not config.has_section(section):
        config.add_section(section)


def validate_config():
    required_keys = ['token', 'channel', 'client_id', 'client_secret']
    return all(config.get('twitch', key) for key in required_keys)


def start_oauth_flow():
    params = {
        'client_id': config.get('twitch', 'client_id'),
        'redirect_uri': 'https://localhost:5000/callback_twitch',
        'response_type': 'code',
        'scope': scope_twitch
    }
    url = f"{AUTHORIZATION_URL}?{urlencode(params)}"
    webbrowser.open(url)


def setup():
    # Prompt for missing details
    if not config['twitch'].get('channel'):
        config.set("twitch", "channel", input("Enter the channel you want to join: "))
    if not config['twitch'].get('client_id'):
        config.set("twitch", "client_id", input("Enter your Twitch client ID: "))
    if not config['twitch'].get('client_secret'):
        config.set("twitch", "client_secret", input("Enter your Twitch client secret: "))

    # Check if the token exists and is valid; if not, start the OAuth flow
    if not config['twitch'].get('token'):
        print("Initiating OAuth flow to obtain token...")
        start_oauth_flow()
        print("Please complete the OAuth flow in the browser.")


class TwitchBot(commands.Bot):
    def __init__(self):
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        print(f"Connecting to {config.get('twitch', 'channel')}")
        self.sp = spotipy.Spotify(auth=config.get("spotify", "token"))
        self.device_id = self.sp.me()
        super().__init__(token=config.get('twitch', 'token'), prefix="!", initial_channels=["#" + config.get('twitch', 'channel')])

    async def event_ready(self):
        # Notify us when everything is ready!
        # We are logged in and ready to chat and use commands...
        print(f'Logged in as | {self.nick}')
        print(f'User id is | {self.user_id}')

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

        await ctx.send('Played!')

    @commands.command()
    async def pause(self, ctx: commands.Context):

        self.sp.pause_playback(self.device_id)

        await ctx.send('Paused!')

    @commands.command()
    async def sr(self, ctx: commands.Context):
        song = ctx.message.content.strip("!sr")
        song = song.split("/")[-1]
        self.sp.add_to_queue(f"spotify:track:{song}")

        await ctx.send('Added!')


# Start Twitch Bot on a separate thread
def start_twitch_bot():
    global twitch_thread
    global auth_manager
    if twitch_thread is None:
        twitch_thread = Thread(target=TwitchBot().run)
        twitch_thread.daemon = True
        twitch_thread.start()
    print("Started Twitch Bot!")


# Main Function
if __name__ == "__main__":
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        client = config.get('spotify', 'client_id', fallback=None)
        uri = config.get('spotify', 'redirect_uri', fallback=None)
        secret = config.get('spotify', 'client_secret', fallback=None)
        key = config.get('app', 'secret_key', fallback=None)
        ensure_config_section_exists('twitch')
        if not validate_config():
            setup()

        if client and secret and uri:
            auth_manager = SpotifyOAuth(client_id=client,
                                        client_secret=secret,
                                        redirect_uri=uri,
                                        scope=scope_spotify)
        else:
            print("Spotify credentials are missing in config.ini")

        if key:
            app.secret_key = key
        else:
            print("App secret_key is missing in config.ini. Generating a new one.")
            app.secret_key = secrets.token_hex(16)
            config.set('app', 'secret_key', app.secret_key)
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
        start_twitch_bot()
    else:
        print("config.ini file not found")
        print("Generating a new Flask secret_key.")
        app.secret_key = secrets.token_hex(16)
        config.set('app', 'secret_key', app.secret_key)
        config.set('spotify', 'client_id', "")
        config.set('spotify', 'redirect_uri', "")
        config.set('spotify', 'client_secret', "")
        config.set('twitch', 'token', "")
        config.set('twitch', 'channel', "")
        config.set('twitch', 'client_id', "")
        config.set('twitch', 'client_secret', "")
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
    app.run(port=5000, debug=True, ssl_context=("localhost.ecc.crt", "localhost.ecc.key"))
