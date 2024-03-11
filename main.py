import asyncio
import configparser
import datetime
import os
import time
import webbrowser
import requests
from urllib.parse import urlencode
import spotipy
from quart import Quart, request, redirect, session
from spotipy.oauth2 import SpotifyOAuth
import secrets
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


def print_to_logs(message):
    # Get current timestamp in the specified format
    timestamp = datetime.datetime.now().strftime('%d/%m/%y - %H:%M')
    # Format the log entry
    log_entry = f"{timestamp}: {message}\n"
    # Open the log file and append the log entry
    with open("log.txt", 'a') as file:
        file.write(log_entry)


if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE)
else:
    print_to_logs("config.ini file not found")
    print_to_logs("Generating a new Flask secret_key.")
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
    config.set('spotify-token', 'expires_at', '')  # Use Unix timestamp
    config.set('twitch', 'channel', "")
    config.set('twitch', 'client_id', "")
    config.set('twitch', 'client_secret', "")
    config.set('twitch-token', 'access_token', '')
    config.set('twitch-token', 'refresh_token', '')
    config.set('twitch-token', 'expires_at', '')  # Use Unix timestamp


TASKS = {
    "bot": {
        "task": None,
        "instance": None
    },
    "auth_manager": None,
    "quart": None,
    "updater": None
}


def save_config():
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    print_to_logs("Configuration saved.")


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
    global TASKS
    token = TASKS["auth_manager"].get_access_token(request.args['code'])
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
    elif (not config.get("spotify-token", "expires_at") or
          not config.get("spotify-token", "refresh_token") or
          not config.get("spotify-token", 'access_token') or
          TASKS["auth_manager"] is None):
        return redirect(TASKS["auth_manager"].get_authorize_url())
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
    refresh_token = response_json.get('refresh_token')
    expires_in = response_json.get('expires_in')

    # Calculate the expiration timestamp and save it
    expires_at = int(time.time()) + expires_in

    # Save the access token, refresh token, and expiration timestamp
    if access_token and refresh_token:
        config.set('twitch-token', 'access_token', access_token)
        config.set('twitch-token', 'refresh_token', refresh_token)
        config.set('twitch-token', 'expires_at', str(expires_at))
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


def start_spotify_oauth_flow():
    auth_url = TASKS["auth_manager"].get_authorize_url()
    webbrowser.open(auth_url)


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
    TASKS["auth_manager"] = SpotifyOAuth(client_id=config.get('spotify', 'client_id', fallback=None),
                                         client_secret=config.get('spotify', 'client_secret', fallback=None),
                                         redirect_uri=config.get('spotify', 'redirect_uri', fallback=None),
                                         scope=scope_spotify)


def update_bot_token():
    params = {
        'grant_type': 'refresh_token',
        'refresh_token': config.get("twitch-token", "refresh_token"),
        'client_id': config.get("twitch-token", "client_id"),
        'client_secret': config.get("twitch-token", "client_secret"),
    }
    response = requests.post(TOKEN_URL, data=params)
    if response.status_code == 200:
        response_json = response.json()
        access_token = response_json.get('access_token')
        refresh_token = response_json.get('refresh_token')
        expires_at = response_json.get("expires_at")
        # Use the new refresh token if provided, otherwise keep the old one
        config.set("twitch-token", 'access_token', access_token)
        config.set("twitch-token", "refresh_token", refresh_token)
        config.set("twitch-token", "expires_at", str(expires_at))
    else:
        raise Exception(f"Failed to refresh Twitch token: {response.status_code}")
    save_config()
    create_new_bot()


def check_twitch():
    if TASKS["bot"]["instance"] is None:
        bot = TwitchBot()
        TASKS["bot"]["instance"] = bot
        TASKS["bot"]["task"] = asyncio.create_task(bot.start())
    if (not config.get("twitch-token", "expires_at") or
            not config.get("twitch-token","refresh_token") or
            not config.get("twitch-token", 'access_token')):
        print_to_logs("error config not found")
        start_twitch_oauth_flow()
    elif not config.get('twitch-token', 'expires_at'):
        if int(config.get('twitch-token', 'expires_at')) < int(time.time()):
            update_bot_token()
    else:
        print_to_logs("Twitch is OK!")


def check_spotify():
    if TASKS["auth_manager"] is None:
        print_to_logs("No auth manager")
        TASKS["auth_manager"] = SpotifyOAuth(client_id=config.get("spotify", "client_id"),
                                             client_secret=config.get("spotify", "client_secret"),
                                             redirect_uri=config.get("spotify", "redirect_uri"),
                                             scope=scope_spotify)
        return redirect(TASKS["auth_manager"].get_authorize_url())
    if (not config.get("spotify-token", "expires_at") or
            not config.get("spotify-token", "refresh_token") or
            not config.get("spotify-token", 'access_token')):
        print_to_logs("No Token")
        start_spotify_oauth_flow()
    if TASKS["auth_manager"].is_token_expired({"expires_at": int(config.get("spotify-token", 'expires_at'))}):
        print_to_logs("Expired Token")
        start_spotify_oauth_flow()
    else:
        print_to_logs("Spotify is OK!")


async def recurring_task(interval):
    while True:
        # Twitch check
        print_to_logs("Twitch sanity check!")
        check_twitch()

        # Spotify check
        print_to_logs("Spotify sanity check!")
        check_spotify()
        # Wait for 'interval' seconds before running the task again
        await asyncio.sleep(interval)


def create_new_bot():
    bot = TwitchBot()
    TASKS["bot"]["instance"] = bot
    bot_task = asyncio.create_task(bot.start())
    TASKS["bot"]["task"] = bot_task


async def main():
    global TASKS
    uvicorn_config = uvicorn.Config(app, host="localhost", port=5000,
                                    ssl_certfile='localhost.ecc.crt',
                                    ssl_keyfile='localhost.ecc.key',
                                    loop="asyncio", log_level="info")
    server = uvicorn.Server(config=uvicorn_config)
    # Start the Uvicorn server asynchronously
    quart_task = asyncio.create_task(server.serve())
    TASKS["quart"] = quart_task
    print_to_logs("Quart Task Created")

    # Check if the token exists and is valid; if not, start the OAuth flow
    if (not config['twitch-token'].get('access_token') or
            not config['twitch-token'].get('refresh_token') or
            not config['twitch-token'].get('expires_at')):
        print_to_logs("Initiating OAuth flow to obtain token...")
        start_twitch_oauth_flow()

    updater_task = asyncio.create_task(recurring_task(300))
    TASKS["updater"] = updater_task
    print_to_logs("Updater Task Created")
    # try:
    await asyncio.gather(updater_task, quart_task)  # Corrected to gather all tasks directly
    # except Exception as e:
    #     print_to_logs(f"An error occurred: {e}")


# Main Function
if __name__ == "__main__":
    if not validate_config():
        setup()
    key = config.get('app', 'secret_key', fallback=None)
    if key:
        app.secret_key = key
    else:
        print_to_logs("App secret_key is missing in config.ini. Generating a new one.")
        app.secret_key = secrets.token_hex(16)
        config.set('app', 'secret_key', app.secret_key)
        save_config()
    i = input("> ")
    if i != "":
        config.set("twitch", "channel", f"{i}")
    asyncio.run(main())
