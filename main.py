import asyncio
import configparser
import os
import webbrowser
import requests
from urllib.parse import urlencode
import spotipy
from quart import Quart, request, redirect, session
from spotipy.oauth2 import SpotifyOAuth
import secrets
import multiprocessing
import queue
from twitch import TwitchBot
from quart import Quart
from ssl import SSLContext, PROTOCOL_TLS_SERVER

# Configuration and Flask App
CONFIG_FILE = 'config.ini'
AUTHORIZATION_URL = 'https://id.twitch.tv/oauth2/authorize'
TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
OAUTH_AUTHORIZE_URL = 'https://accounts.spotify.com/authorize'
OAUTH_TOKEN_URL = 'https://accounts.spotify.com/api/token'
scope_spotify = "user-read-playback-state user-modify-playback-state"
scope_twitch = 'chat:read chat:edit'


config = configparser.ConfigParser()
app = Quart(__name__)
app.config['SESSION_COOKIE_NAME'] = 'spotify-login-session'

SERVER = 'irc.chat.twitch.tv'
PORT = 6697
NICKNAME = ""
TOKEN = ""
CHANNEL = ""
auth_manager = None
sp = None
command_queue = queue.Queue()  # Initialize a command queue for inter-process communication
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
        print(f"Currently playing: {track_name} by {artist_name}")
        return f"Currently playing: {track_name} by {artist_name}"
    else:
        print("No track is currently playing.")
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
    redirect("/currently_playing")


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


def twitch_irc_socket(token, nickname, channel, cmd_queue):
    global done
    if not done:
        TwitchBot().run()
        done = True


def process_commands(cmd_queue):
    sp = spotipy.Spotify(auth=config.get("spotify", "token"))
    while True:
        try:
            command = cmd_queue.get(timeout=1)  # Adjust timeout as needed
            if command == "play":
                # Assuming `sp` is your Spotipy instance with appropriate scope
                sp.start_playback()
            elif command == "pause":
                sp.pause_playback()
            # Implement other commands like "list queue", "add to queue", etc.
        except queue.Empty:
            continue


async def main():
    bot = TwitchBot()
    bot_task = asyncio.create_task(bot.start())  # Replace bot.run() with bot.start() if necessary

    # Create SSL context
    ssl_context = SSLContext(PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain('local.ecc.crt', 'local.ecc.key')

    # Adjust the quart_task to include SSL context
    quart_task = asyncio.create_task(app.run_task(port=5000, debug=True, ssl=ssl_context))

    await asyncio.gather(bot_task, quart_task)


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

    # Start the command processor in a separate process
    command_processor = multiprocessing.Process(target=process_commands, args=(command_queue,))
    command_processor.start()
    NICKNAME = config.get('twitch', 'channel')
    TOKEN = config.get('twitch', 'token')
    CHANNEL = config.get('twitch', 'channel')
    asyncio.run(main())
