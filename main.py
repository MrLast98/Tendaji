import asyncio
import configparser
import json
import os
import secrets
import spotipy
import sys
import time
import uvicorn
from datetime import datetime
from logger import print_to_logs, PrintColors, check_log_file
from manager import Manager
from quart import Quart, request, redirect, session
from twitch import retrieve_token_info, start_twitch_oauth_flow, print_queue_to_file

# pyinstaller --onefile --add-data "localhost.ecc.crt;." --add-data "localhost.ecc.key;." main.py


# Configuration and Flask App
CONFIG_FILE = 'config.ini'
COMMANDS_FILE = 'commands.json'
QUEUE_FILE = 'queue.json'
LOGS_FILE = f"logs-{datetime.now().strftime("%d-%m-%Y")}.txt"
app = Quart(__name__)
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'
config = configparser.ConfigParser()
manager = ""


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


def setup():
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
    save_config()


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


async def shutdown():
    """Gracefully shut down all tasks and save configurations."""
    print_to_logs("Initiating shutdown...", PrintColors.BRIGHT_PURPLE)
    save_config()
    manager.twitch_bot.get("task").cancel()
    manager.updater.cancel()
    manager.quart.cancel()
    await asyncio.gather(manager.twitch_bot.get("task"), manager.updater, manager.quart, return_exceptions=True)
    print_to_logs("Cleanup complete. Exiting...", PrintColors.BRIGHT_PURPLE)


def update_queue(track_name, artist_name):
    with open("queue.json", "r", encoding="utf-8") as f:
        queue = json.loads(f.read())
    while queue and queue[0]["title"] != track_name and queue[0]["author"] != artist_name and len(queue) > 0:
        queue.pop(0)
    print_queue_to_file(queue)
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
    global manager
    token = manager.auth_manager.get_access_token(request.args['code'])
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


@app.route('/callback_twitch')
async def callback_twitch():
    global manager
    access_token, refresh_token, expires_at = retrieve_token_info(request.args.get('code'))

    # Save the access token, refresh token, and expiration timestamp
    if access_token and refresh_token and expires_at:
        config.set('twitch-token', 'access_token', access_token)
        config.set('twitch-token', 'refresh_token', refresh_token)
        config.set('twitch-token', 'expires_at', str(expires_at))
        save_config()
        manager.create_new_bot()
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
        return '''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Error Occurred</title>
            </head>
            <body>
                <p>Error: "Error retrieving tokens"</p>
            </body>
            </html>
        '''


@app.route('/currently_playing')
async def currently_playing():
    global manager
    sp = spotipy.Spotify(auth=config.get("spotify-token", "access_token"),)
    track = sp.current_playback()
    if track is not None:
        track_name = track['item']['name']
        artist_name = track['item']['artists'][0]['name']

        album_name = track['item']['album']['name']
        album_image_url = track['item']['album']['images'][0]['url'] if track['item']['album'][
            'images'] else "No image available"
        track_duration = int(track['item']["duration_ms"])
        progress = int(track["progress_ms"])
        if track_duration - progress >= 30000:
            refresh_rate = 30
        else:
            refresh_rate = (track_duration - progress) / 1000 + 1  # Convert to seconds and add 1
            update_queue(track_name, artist_name)
        next_refresh = int(time.time()) + refresh_rate
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
                <p><strong>Next Refresh:</strong> {datetime.fromtimestamp(next_refresh).strftime('%H:%M:%S')}</p>
                <img src="{album_image_url}" alt="Album art" class="album-art" />
            </div>
        </body>
        </html>
        '''
        return html_content
    else:
        return "No track is currently playing."


async def check_twitch():
    global manager
    if manager.twitch_bot.get("instance") is None or manager.twitch_bot.get("task") is None:
        print_to_logs("No bot istance", PrintColors.RED)
        manager.create_new_bot()
    access_token = config.get("twitch-token","access_token")
    refresh_token = config.get("twitch-token", "refresh_token")
    expires_at = config.get('twitch-token', 'expires_at')
    if expires_at and expires_at != "" and expires_at != "None" and int(expires_at) < int(time.time()):
        print_to_logs("Expired Twitch Token", PrintColors.YELLOW)
        await manager.update_twitch_token()
        save_config()
        manager.create_new_bot()
    elif ((not access_token or access_token == "" or access_token == "None") or
        (not refresh_token or refresh_token == "" or refresh_token == "None") or
        (not expires_at or expires_at == "" or expires_at == "None")):
        print_to_logs("Twitch token configuration missing. Retrieving...", PrintColors.RED)
        start_twitch_oauth_flow()
        print_to_logs("Re-Authorizing Twitch Bot...", PrintColors.YELLOW)
    else:
        print_to_logs("Twitch is OK!", PrintColors.GREEN)


async def check_spotify():
    global manager
    if manager.auth_manager is None:
        print_to_logs("No auth manager", PrintColors.RED)
        manager.create_new_auth_manager()
    elif (not config.get("spotify-token", "expires_at") or
            not config.get("spotify-token", "refresh_token") or
            not config.get("spotify-token", 'access_token')):
        print_to_logs("No Token", PrintColors.RED)
        manager.start_spotify_oauth_flow()
    elif config.get("spotify-token", 'expires_at') and manager.auth_manager.is_token_expired({"expires_at": int(config.get("spotify-token", 'expires_at'))}):
        print_to_logs("Expired Spotify Token", PrintColors.YELLOW)
        await manager.refresh_spotify_token()
        save_config()
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
    global manager
    try:
        manager = Manager(config)
        uvicorn_config = uvicorn.Config(app, host="localhost", port=5000,
                                        ssl_certfile=resource_path('localhost.ecc.crt'),
                                        ssl_keyfile=resource_path('localhost.ecc.key'),
                                        loop="asyncio", log_level="info")
        server = uvicorn.Server(config=uvicorn_config)
        # await check_twitch()
        # await check_spotify()
        # Start the Uvicorn server asynchronously
        quart_task = asyncio.create_task(server.serve())
        manager.quart = quart_task
        print_to_logs("Quart Task Created", PrintColors.BRIGHT_PURPLE)

        updater_task = asyncio.create_task(recurring_task(300))
        manager.updater = updater_task
        print_to_logs("Updater Task Created", PrintColors.BRIGHT_PURPLE)
        time.sleep(1)
        await asyncio.gather(manager.quart, manager.updater)
    except KeyboardInterrupt:
        print_to_logs("KeyboardInterrupt received. Shutting down...", PrintColors.YELLOW)
        await shutdown()


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

    if os.path.exists(QUEUE_FILE):
        os.remove(QUEUE_FILE)
        print_to_logs("Cleared queue", PrintColors.BRIGHT_PURPLE)

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
