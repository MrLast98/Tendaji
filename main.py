import configparser
import os
import webbrowser
from flask import Flask, request, redirect, session
import requests
from threading import Thread
from urllib.parse import urlencode
from  irc.bot import SingleServerIRCBot
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import secrets

# Configuration and Flask App
CONFIG_FILE = 'config.ini'
AUTHORIZATION_URL = 'https://id.twitch.tv/oauth2/authorize'
TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
scope_spotify = "user-read-playback-state user-modify-playback-state"
scope_twitch = 'chat:read chat:edit'

config = configparser.ConfigParser()
config.read(CONFIG_FILE)
app = Flask(__name__)
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'


# Shared Data System
class SharedData:
    def __init__(self):
        self.data = {}

    def set(self, key, value):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)


shared_data = SharedData()


# Spotify Bot Class
class SpotifyBot:
    def __init__(self):
        self.auth_manager = None
        self.get_app_secret()
        self.add_routes()

    def get_app_secret(self):
        if os.path.exists("config.ini"):
            config.read('config.ini')
            client = config.get('spotify', 'client_id', fallback=None)
            uri = config.get('spotify', 'redirect_uri', fallback=None)
            secret = config.get('spotify', 'client_secret', fallback=None)
            key = config.get('app', 'secret_key', fallback=None)

            if client and secret and uri:
                self.auth_manager = SpotifyOAuth(client_id=client,
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
                with open('config.ini', 'w') as configfile:
                    config.write(configfile)
        else:
            print("config.ini file not found")
            print("Generating a new Flask secret_key.")
            app.secret_key = secrets.token_hex(16)
            config.set('app', 'secret_key', app.secret_key)
            config.set('spotify', 'client_id',     "")
            config.set('spotify', 'redirect_uri',  "")
            config.set('spotify', 'client_secret', "")
            with open('config.ini', 'w') as configfile:
                config.write(configfile)

    def add_routes(self):
        @app.route('/')
        def index():
            if not self.auth_manager:
                return "Spotify OAuth is not initialized. Check your config.ini file."
            auth_url = self.auth_manager.get_authorize_url()
            return redirect(auth_url)

        @app.route('/callback')
        def callback():
            session['token_info'] = self.auth_manager.get_access_token(request.args['code'])
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


# Twitch Bot Class
class TwitchBot(SingleServerIRCBot):
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_FILE)
        self.ensure_config_section_exists('twitch')

        if not self.validate_config():
            self.setup()
            self.config.read(CONFIG_FILE)

        self.username = self.config.get('twitch', 'username')
        self.token = self.config.get('twitch', 'token')
        self.channel = '#' + self.config.get('twitch', 'channel')

        server = 'irc.chat.twitch.tv'
        port = 6667
        print(f"Connecting to {self.channel}")

        SingleServerIRCBot.__init__(self, [(server, port, f"oauth:{self.token}")], self.username, self.username)

    def ensure_config_section_exists(self, section):
        if not self.config.has_section(section):
            self.config.add_section(section)

    def validate_config(self):
        required_keys = ['username', 'token', 'channel', 'client_id', 'client_secret']
        return all(self.config.get('twitch', key) for key in required_keys)

    def setup(self):
        # Prompt for missing details
        if not self.config['twitch'].get('username'):
            self.config.set("twitch", "username", input("Enter your Twitch username: "))
        if not self.config['twitch'].get('channel'):
            self.config.set("twitch", "channel", input("Enter the channel you want to join: "))
        if not self.config['twitch'].get('client_id'):
            self.config.set("twitch", "client_id", input("Enter your Twitch client ID: "))
        if not self.config['twitch'].get('client_secret'):
            self.config.set("twitch", "client_secret", input("Enter your Twitch client secret: "))

        # Check if the token exists and is valid; if not, start the OAuth flow
        if not self.config['twitch'].get('token'):
            print("Initiating OAuth flow to obtain token...")
            Thread(target=lambda: app.run(port=5000, debug=False, ssl_context=("localhost.ecc.crt", "localhost.ecc.key"))).start()
            self.start_oauth_flow()
            print("Please complete the OAuth flow in the browser.")
        with open('config.ini', 'w') as configfile:
            self.config.write(configfile)

    def start_oauth_flow(self):
        params = {
            'client_id': self.config.get('twitch', 'client_id'),
            'redirect_uri': 'https://localhost:5000/callback',
            'response_type': 'code',
            'scope': scope_twitch
        }
        url = f"{AUTHORIZATION_URL}?{urlencode(params)}"
        webbrowser.open(url)

    @app.route('/callback')
    def callback(self):
        code = request.args.get('code')
        payload = {
            'client_id': self.config.get('twitch', 'client_id'),
            'client_secret': self.config.get('twitch', 'client_secret'),
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': 'https://localhost:5000/callback'
        }
        response = requests.post(TOKEN_URL, data=payload)
        response_json = response.json()
        access_token = response_json.get('access_token')

        # Save the access token and other details to config.ini
        self.config.set('twitch', 'token', access_token)
        with open(CONFIG_FILE, 'w') as configfile:
            self.config.write(configfile)

        os._exit(0)  # Terminate the Flask thread after writing the config

    def on_pubmsg(self, connection, event):
        if event.arguments[0].startswith("!sr"):
            print(f"Received !sr command from {event.source.nick}")


# Main Function
if __name__ == "__main__":
    spotify_bot = SpotifyBot()
    twitch_bot = TwitchBot()

    # Start Twitch Bot on a separate thread
    twitch_bot_thread = Thread(target=lambda: twitch_bot.start())
    twitch_bot_thread.start()

    # Run the Flask app
    app.run(port=5000, debug=True, ssl_context=("localhost.ecc.crt", "localhost.ecc.key"))
