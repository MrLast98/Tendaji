import aiohttp
import asyncio
import configparser
import json
import os
import requests
import secrets
import spotipy
import sys
import time
import uvicorn
import webbrowser
from datetime import datetime
from logger import print_to_logs, PrintColors, check_log_file
from quart import Quart, request, redirect, session
from spotipy.oauth2 import SpotifyOAuth
from twitch import TwitchBot
from urllib.parse import urlencode

# pyinstaller --onefile --add-data "localhost.ecc.crt;." --add-data "localhost.ecc.key;." main.py


# Configuration and Flask App
CONFIG_FILE = 'config.ini'
COMMANDS_FILE = 'commands.json'
LOGS_FILE = f"logs-{datetime.now().strftime("%d-%m-%Y")}.txt"
AUTHORIZATION_URL = 'https://id.twitch.tv/oauth2/authorize'
TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
OAUTH_AUTHORIZE_URL = 'https://accounts.spotify.com/authorize'
OAUTH_TOKEN_URL = 'https://accounts.spotify.com/api/token'
scope_spotify = "user-read-playback-state user-modify-playback-state"
scope_twitch = 'chat:read chat:edit'
app = Quart(__name__)
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'
config = configparser.ConfigParser()


class Manager:
    def __init__(self):
        self.twitch_bot = {
            "task": "",
            "instance": ""
        }
        self.auth_manager = None
        self.quart = None
        self.updater = None

    def create_new_bot(self):
        bot = TwitchBot()
        self.twitch_bot["instance"] = bot
        bot_task = asyncio.create_task(bot.start())
        self.twitch_bot["task"] = bot_task

    async def update_bot_token(self):
        params = {
            'grant_type': 'refresh_token',
            'refresh_token': config.get("twitch-token", "refresh_token"),
            'client_id': config.get("twitch", "client_id"),
            'client_secret': config.get("twitch", "client_secret"),
        }
        async with aiohttp.ClientSession() as session:
            response = await fetch(session, TOKEN_URL, data=params)
            if 'access_token' in response:
                access_token = response['access_token']
                refresh_token = response.get('refresh_token')
                expires_in = response.get('expires_in')
                expires_at = int(time.time()) + expires_in

                config.set("twitch-token", 'access_token', access_token)
                config.set("twitch-token", "refresh_token", refresh_token)
                config.set("twitch-token", "expires_at", str(expires_at))
                save_config()
            else:
                raise Exception(f"Failed to refresh Twitch token: {response}")
        self.create_new_bot()

    def start_spotify_oauth_flow(self):
        auth_url = self.auth_manager.get_authorize_url()
        webbrowser.open(auth_url)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return str(os.path.join(base_path, relative_path))


def save_config():
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    print_to_logs("Configuration saved.", PrintColors.BRIGHT_PURPLE)


def ensure_config_section_exists(section):
    if not config.has_section(section):
        config.add_section(section)


def validate_config():
    twitch_keys = ['channel', 'client_id', 'client_secret']
    token_keys = ['access_token', 'refresh_token', 'expires_at']
    return all(config.get('twitch', key) for key in twitch_keys) and all(
        config.get('twitch-token', key) for key in token_keys)


def start_twitch_oauth_flow():
    params = {
        'client_id': config.get('twitch', 'client_id'),
        'redirect_uri': 'https://localhost:5000/callback_twitch',
        'response_type': 'code',
        'scope': scope_twitch
    }
    url = f"{AUTHORIZATION_URL}?{urlencode(params)}"
    webbrowser.open(url)


def setup():
    global TASKS
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
    auth_manager.refresh_access_token()


async def fetch(session, url, data=None):
    async with session.request('POST', url, data=data) as response:
        return await response.json()


async def refresh_spotify_token():
    payload = {
       "client_id": config.get('spotify', 'client_id'),
       "grant_type": 'refresh_token',
       "refresh_token": config.get('spotify-token', 'refresh_token'),
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    async with aiohttp.ClientSession() as session:
        async with session.post(OAUTH_TOKEN_URL, data=payload, headers=headers) as response:
            if response.status == 200:
                response_json = await response.json()
                access_token = response_json.get('access_token')
                refresh_token = response_json.get('refresh_token')
                expires_in = response_json.get('expires_in')
                expires_at = int(time.time()) + expires_in
                config.set("spotify-token", 'access_token', access_token)
                config.set("spotify-token", "refresh_token", refresh_token)
                config.set("spotify-token", "expires_at", str(expires_at))
                print_to_logs(f"New Token Acquired! {access_token}, {refresh_token}, {expires_at}", PrintColors.BRIGHT_PURPLE)
                save_config()
            else:
                print_to_logs(f"Failed to refresh Spotify token: {response.status}", PrintColors.YELLOW)
                print_to_logs(f"Response: {response}", PrintColors.WHITE)
                start_spotify_oauth_flow()


def generate_config_file():
    app.secret_key = secrets.token_hex(16)
    config.add_section('app')
    config.add_section('twitch')
    config.add_section('spotify')
    config.add_section('twitch-token')
    config.add_section('spotify-token')
    config.set('app', 'secret_key', app.secret_key)
    config.set('spotify', 'client_id', "")
    config.set('spotify', 'redirect_uri', "")
    config.set('spotify', 'client_secret', "")
    config.set('spotify-token', 'access_token', '')
    config.set('spotify-token', 'refresh_token', '')
    config.set('spotify-token', 'expires_at', '')
    config.set('twitch', 'channel', "")
    config.set('twitch', 'client_id', "")
    config.set('twitch', 'client_secret', "")
    config.set('twitch-token', 'access_token', '')
    config.set('twitch-token', 'refresh_token', '')
    config.set('twitch-token', 'expires_at', '')
    save_config()


# async def shutdown():
#     """Gracefully shut down all tasks and save configurations."""
#     print_to_logs("Initiating shutdown...")
#     tasks = [t for t in TASKS.items() if t is not None]
#     for task in tasks:
#         task.cancel()
#     await asyncio.gather(*tasks, return_exceptions=True)
#     save_config()
#     print_to_logs("Cleanup complete. Exiting...")
#
#
# def signal_handler(loop):
#     """Initiates the shutdown process."""
#     print_to_logs("Signal received, shutting down.")
#     for task in asyncio.all_tasks(loop):
#         task.cancel()
#     asyncio.ensure_future(shutdown())


@app.route('/')
async def index():
    return redirect("/currently_playing")


@app.route('/callback')
async def callback():
    global auth_manager
    token = auth_manager.get_access_token(request.args['code'])
    if token:
        session['token_info'] = token
        config.set('spotify-token', 'access_token', token['access_token'])
        config.set('spotify-token', 'refresh_token', token.get('refresh_token'))
        config.set('spotify-token', 'expires_at', str(token['expires_at']))
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        return redirect("/currently_playing")
    else:
        error = "Error retrieving tokens"
        f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Error Occurred</title>
            </head>
            <body>
                <p>Error: {error}</p>
            </body>
            </html>
            '''


@app.route('/currently_playing')
async def currently_playing():
    global TASKS
    token_info = session.get('token_info', None)
    if token_info is None:
        token = {
            "access_token": config.get("spotify-token", "access_token"),
            "expires_at": config.get("spotify-token", "expires_at"),
            "refresh_token": config.get("spotify-token", "refresh_token"),
        }
        session["token_info"] = token
    sp = spotipy.Spotify(auth=token_info['access_token'])
    track = sp.current_playback()
    if track is not None:
        track_name = track['item']['name']
        artist_name = track['item']['artists'][0]['name']
        album_name = track['item']['album']['name']
        album_image_url = track['item']['album']['images'][0]['url'] if track['item']['album'][
            'images'] else "No image available"
        refresh_rate = 30

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
            <div>
            <div>
                <h1>Currently Playing</h1>
                <p><strong>Track:</strong> {track_name}</p>
                <p><strong>Artist:</strong> {artist_name}</p>
                <p><strong>Album:</strong> {album_name}</p>
                <img src="{album_image_url}" alt="Album art" class="album-art" />
            </div>
        </body>
        </html>
        '''
        return html_content
    elif (not config.get("spotify-token", "expires_at") or
          not config.get("spotify-token", "refresh_token") or
          not config.get("spotify-token", 'access_token') or
          TASKS["auth_manager"] is None):
        return redirect(TASKS["auth_manager"].get_authorize_url())
    else:
        return "No track is currently playing."


@app.route('/callback_twitch')
async def callback_twitch():
    global TASKS
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
    refresh_token = response_json.get('refresh_token')
    expires_in = response_json.get('expires_in')
    # Calculate the expiration timestamp and save it
    expires_at = int(time.time()) + expires_in

    # Save the access token, refresh token, and expiration timestamp
    if access_token and refresh_token and expires_at:
        config.set('twitch-token', 'access_token', access_token)
        config.set('twitch-token', 'refresh_token', refresh_token)
        config.set('twitch-token', 'expires_at', str(expires_at))
        TASKS["bot"]["task"] = asyncio.create_task(TASKS["bot"]["instance"].start())
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Process Complete</title>
        </head>
        <body>
            <p>You can close this window.</p>
        </body>
        </html>
    '''
    else:
        error = "Error retrieving tokens"
        f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Error Occurred</title>
            </head>
            <body>
                <p>Error: {error}</p>
            </body>
            </html>
            '''


async def check_twitch():
    global TASKS
    if TASKS["bot"]["instance"] is None:
        print_to_logs("No bot istance", PrintColors.RED)
        bot = TwitchBot()
        TASKS["bot"]["instance"] = bot
    if config.get('twitch-token', 'expires_at'):
        if config.get('twitch-token', 'expires_at') == "None":
            config.set('twitch-token', 'expires_at', "")
        elif int(config.get('twitch-token', 'expires_at')) < int(time.time()):
            if TASKS["bot"]["task"] is not None:
                TASKS["bot"]["task"].cancel()
            print_to_logs("Expired Twitch Token", PrintColors.YELLOW)
            await update_bot_token()
    elif (not config.get("twitch-token", "expires_at") or
            not config.get("twitch-token","refresh_token") or
            not config.get("twitch-token", 'access_token')):
        print_to_logs("Twitch token configuration missing. Retrieving...", PrintColors.RED)
        start_twitch_oauth_flow()
    if TASKS["bot"]["task"] is None:
        print_to_logs("Creating TwitchBot Task", PrintColors.YELLOW)
        TASKS["bot"]["task"] = asyncio.create_task(TASKS["bot"]["instance"].start())
    else:
        print_to_logs("Twitch is OK!", PrintColors.GREEN)


async def check_spotify():
    global TASKS
    print(config.get("spotify-token", 'expires_at') and TASKS["auth_manager"].is_token_expired({"expires_at": int(config.get("spotify-token", 'expires_at'))}))
    if TASKS["auth_manager"] is None:
        print_to_logs("No auth manager", PrintColors.RED)
        TASKS["auth_manager"] = SpotifyOAuth(client_id=config.get("spotify", "client_id"),
                                             client_secret=config.get("spotify", "client_secret"),
                                             redirect_uri=config.get("spotify", "redirect_uri"),
                                             scope=scope_spotify)
    elif (not config.get("spotify-token", "expires_at") or
            not config.get("spotify-token", "refresh_token") or
            not config.get("spotify-token", 'access_token')):
        print_to_logs("No Token", PrintColors.RED)
        start_spotify_oauth_flow()
    elif config.get("spotify-token", 'expires_at') and TASKS["auth_manager"].is_token_expired({"expires_at": int(config.get("spotify-token", 'expires_at'))}):
        print_to_logs("Expired Spotify Token", PrintColors.YELLOW)
        await refresh_spotify_token()
    else:
        print_to_logs("Spotify is OK!", PrintColors.GREEN)


async def recurring_task(interval):
    print_to_logs("Started reoccurring task", PrintColors.BRIGHT_PURPLE)
    while True:
        # Twitch check
        print_to_logs("Twitch sanity check!", PrintColors.BRIGHT_PURPLE)
        await check_twitch()

        # Spotify check
        print_to_logs("Spotify sanity check!", PrintColors.BRIGHT_PURPLE)
        await check_spotify()
        # Wait for 'interval' seconds before running the task again
        await asyncio.sleep(interval)


async def main():
    global TASKS
    uvicorn_config = uvicorn.Config(app, host="localhost", port=5000,
                                    ssl_certfile=resource_path('localhost.ecc.crt'),
                                    ssl_keyfile=resource_path('localhost.ecc.key'),
                                    loop="asyncio", log_level="info")
    server = uvicorn.Server(config=uvicorn_config)
    # await check_twitch()
    # await check_spotify()
    # Start the Uvicorn server asynchronously
    quart_task = asyncio.create_task(server.serve())
    TASKS["quart"] = quart_task
    print_to_logs("Quart Task Created", PrintColors.BRIGHT_PURPLE)

    updater_task = asyncio.create_task(recurring_task(300))
    TASKS["updater"] = updater_task
    print_to_logs("Updater Task Created", PrintColors.BRIGHT_PURPLE)
    time.sleep(1)
    await asyncio.gather(TASKS["quart"], TASKS["updater"])


def startup_checks():
    print_to_logs("Checking config file existence", PrintColors.BRIGHT_PURPLE)
    if os.path.exists(CONFIG_FILE):
        print_to_logs("Config found! Loading...", PrintColors.GREEN)
        config.read(CONFIG_FILE)
    else:
        print_to_logs("Config file not found", PrintColors.RED)
        print_to_logs("Creating new one and generatic necessary secrets", PrintColors.YELLOW)
        generate_config_file()

    if not os.path.exists(LOGS_FILE):
        check_log_file()
        print_to_logs("New Logs generated!", PrintColors.YELLOW)
        config.set('twitch-token', 'expires_at', "")
        config.set('twitch-token', 'access_token', "")
        config.set('twitch-token', 'refresh_token', "")
        config.set('spotify-token', 'access_token', "")
        config.set('spotify-token', 'refresh_token', "")
        config.set('spotify-token', 'expires_at', "")
        save_config()

    print_to_logs("Checking commands file existence", PrintColors.BRIGHT_PURPLE)
    if os.path.exists(COMMANDS_FILE):
        print_to_logs("Commands found! Loading...", PrintColors.GREEN)
        config.read(CONFIG_FILE)
    else:
        print_to_logs("Commands file not found", PrintColors.RED)
        print_to_logs("Creating new one with no commands", PrintColors.WHITE)
        with open("commands.json", "w", encoding="utf-8") as f:
            f.write(json.dumps({"example": "[sender] this is an example command"}))


# Main Function
if __name__ == "__main__":
    startup_checks()
    if not validate_config():
        setup()
    key = config.get('app', 'secret_key', fallback=None)
    if key:
        app.secret_key = key
    else:
        print_to_logs("App secret_key is missing in config.ini. Generating a new one.", PrintColors.RED)
        app.secret_key = secrets.token_hex(16)
        config.set('app', 'secret_key', app.secret_key)
        save_config()
    asyncio.run(main())
