import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import configparser
from flask import Flask, request, redirect, session
import secrets

scope = "user-read-playback-state user-modify-playback-state"
config = configparser.ConfigParser()


# Take the two scripts i provided and merge them, so they both use the same flask app (prioritise the app created by the "bot.py"script) , the two separate functions attached to the "/callback" route should be merged and check first for the configs related to the bot.py then for the configs related to the twitch.py.
# The irc server in twitch.py should be on a separate thread than the bot itself, with a central thread to manage the exchange of information if necessary (create a dummy system to share data between the two threads safely).
# Last, but not least, the two setups should be done BEFORE starting the threads so once the threads start they are both fully working.


class BotAPPedali:
    def __init__(self):
        self.app = Flask(__name__)
        self.auth_manager = None
        self.get_app_secret()
        self.app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'
        self.sp = None
        # Initialize the SpotifyOAuth object during class instantiation
        self.add_routes()
        # Run the Flask app
        self.app.run(debug=True)

    def add_routes(self):
        self.app.add_url_rule('/', 'index', self.login)
        self.app.add_url_rule('/callback', 'callback', self.callback)
        self.app.add_url_rule('/currently_playing', 'currently_playing', self.currently_playing)

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
                                                 scope=scope)
            else:
                print("Spotify credentials are missing in config.ini")

            if key:
                self.app.secret_key = key
            else:
                print("App secret_key is missing in config.ini. Generating a new one.")
                self.app.secret_key = secrets.token_hex(16)
                config.set('app', 'secret_key', self.app.secret_key)
                with open('config.ini', 'w') as configfile:
                    config.write(configfile)
        else:
            print("config.ini file not found")
            # Generate a new Flask secret key if config.ini is missing
            print("Generating a new Flask secret_key.")
            self.app.secret_key = secrets.token_hex(16)
            config.set('app', 'secret_key', self.app.secret_key)
            config.set('spotify', 'client_id',     "")
            config.set('spotify', 'redirect_uri',  "")
            config.set('spotify', 'client_secret', "")
            with open('config.ini', 'w') as configfile:
                config.write(configfile)

    def login(self):
        if not self.auth_manager:
            return "Spotify OAuth is not initialized. Check your config.ini file."
        auth_url = self.auth_manager.get_authorize_url()
        return redirect(auth_url)

    def callback(self):
        # Here we directly use Flask's session to store the token info
        session['token_info'] = self.auth_manager.get_access_token(request.args['code'])
        return redirect('/currently_playing')

    def currently_playing(self):
        token_info = session.get('token_info', None)
        if not token_info:
            return redirect('/')
        self.sp = spotipy.Spotify(auth=token_info['access_token'])
        track = self.sp.current_playback()
        if track is not None:
            track_name = track['item']['name']
            artist_name = track['item']['artists'][0]['name']
            print(f"Currently playing: {track_name} by {artist_name}")  # Print to console
            return f"Currently playing: {track_name} by {artist_name}"
        else:
            print("No track is currently playing.")  # Print to console
            return "No track is currently playing."


if __name__ == '__main__':
    bot = BotAPPedali()
