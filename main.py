import asyncio
import configparser
import os
import time
import webbrowser
import requests
from urllib.parse import urlencode
import spotipy
from quart import Quart, request, redirect, session
from spotipy.oauth2 import SpotifyOAuth
import secrets
import multiprocessing
from multiprocessing import Queue
from twitch import TwitchBot
import uvicorn

# Configuration and Flask App
CONFIG_FILE = 'config.ini'
AUTHORIZATION_URL = 'https://id.twitch.tv/oauth2/authorize'
TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
OAUTH_AUTHORIZE_URL = 'https://accounts.spotify.com/authorize'
OAUTH_TOKEN_URL = 'https://accounts.spotify.com/api/token'
scope_spotify = "user-read-playback-state user-modify-playback-state"
scope_twitch = 'chat:read chat:edit'

app = Quart(__name__)
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

config = configparser.ConfigParser()
if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE)
else:
    print("config.ini file not found")
    print("Generating a new Flask secret_key.")
    app.secret_key = secrets.token_hex(16)
    config.add_section('app')
    config.add_section('twitch')
    config.add_section('spotify')
    config.set('app', 'secret_key', app.secret_key)
    config.set('spotify', 'client_id', "")
    config.set('spotify', 'redirect_uri', "")
    config.set('spotify', 'client_secret', "")
    config.set('twitch', 'token', "")
    config.set('twitch', 'channel', "")
    config.set('twitch', 'client_id', "")
    config.set('twitch', 'client_secret', "")


auth_manager = None
sp = None
command_queue = Queue()  # Initialize a command queue for inter-process communication
done = False


@app.route('/')
async def index():
    if not auth_manager:
        return "Spotify OAuth is not initialized. Check your config.ini file."
    auth_url = auth_manager.get_authorize_url()
    return redirect(auth_url)


@app.route('/callback')
async def callback():
    session['token_info'] = auth_manager.get_access_token(request.args['code'])
    config.set("spotify", "token", auth_manager.get_access_token(request.args['code'])['access_token'])
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    print("Token retrieved!")
    return redirect('/currently_playing')


@app.route('/currently_playing')
async def currently_playing():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    sp = spotipy.Spotify(auth=token_info['access_token'])
    track = sp.current_playback()
    if track is not None:
        track_name = track['item']['name']
        artist_name = track['item']['artists'][0]['name']
        album_name = track['item']['album']['name']
        album_image_url = track['item']['album']['images'][0]['url'] if track['item']['album']['images'] else "No image available"
        refresh_rate = 30  # Refresh every 30 seconds

        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Currently Playing</title>
            <meta http-equiv="refresh" content="{refresh_rate}">
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .album-art {{ width: 300px; }}
            </style>
        </head>
        <body>
            <h1>Currently Playing</h1>
            <p><strong>Track:</strong> {track_name}</p>
            <p><strong>Artist:</strong> {artist_name}</p>
            <p><strong>Album:</strong> {album_name}</p>
            <img src="{album_image_url}" alt="Album art" class="album-art" />
        </body>
        </html>
        '''
        return html_content
    else:
        return "No track is currently playing."


@app.route('/callback_twitch')
async def callback_twitch():
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
    print(access_token)
    # Save the access token and other details to config.ini
    if access_token:
        config.set('twitch', 'token', access_token)
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
    else:
        print("Error")
    return redirect("/currently_playing")


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
    global auth_manager
    # Prompt for missing details
    if not config['twitch'].get('channel'):
        config.set("twitch", "channel", input("Enter the channel you want to join: "))
    if not config['twitch'].get('client_id'):
        config.set("twitch", "client_id", input("Enter your Twitch client ID: "))
    if not config['twitch'].get('client_secret'):
        config.set("twitch", "client_secret", input("Enter your Twitch client secret: "))
    if not config['spotify'].get('redirect_uri'):
        config.set("spotify", "redirect_uri", "https://localhost:5000/callback")
    if not config['spotify'].get('client_id'):
        config.set("spotify", "client_id", input("Enter your Spotify client ID: "))
    if not config['spotify'].get('client_secret'):
        config.set("spotify", "client_secret", input("Enter your Spotify client secret: "))
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    auth_manager = SpotifyOAuth(client_id=config.get('spotify', 'client_id', fallback=None),
                                client_secret=config.get('spotify', 'client_secret', fallback=None),
                                redirect_uri=config.get('spotify', 'redirect_uri', fallback=None),
                                scope=scope_spotify)
    # Check if the token exists and is valid; if not, start the OAuth flow
    if not config['twitch'].get('token'):
        print("Initiating OAuth flow to obtain token...")
        start_oauth_flow()
        auth_url = auth_manager.get_authorize_url()
        webbrowser.open(auth_url)
        print("Please complete the OAuth flow in the browser.")


async def main():
    bot = TwitchBot()
    bot_task = asyncio.create_task(bot.start())  # Start the Twitch bot asynchronously

    # Define Uvicorn config for your Quart app
    uvicorn_config = uvicorn.Config(app, host="localhost", port=5000,
                                    ssl_certfile='localhost.ecc.crt',
                                    ssl_keyfile='localhost.ecc.key',
                                    loop="asyncio", log_level="info")
    server = uvicorn.Server(config=uvicorn_config)

    # Start the Uvicorn server asynchronously
    quart_task = asyncio.create_task(server.serve())

    # Wait for both tasks to complete
    await asyncio.gather(bot_task, quart_task)


# Main Function
if __name__ == "__main__":
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
    asyncio.run(main())
