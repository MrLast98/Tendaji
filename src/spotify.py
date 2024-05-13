import base64
import hashlib
import secrets
import string
from time import time
from urllib.parse import quote
from webbrowser import open as wbopen

import requests

SPOTIFY_AUTHORIZATION_URL = 'https://accounts.spotify.com/authorize'
OAUTH_SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'
SCOPE_SPOTIFY = 'user-read-playback-state user-modify-playback-state'


# Parse the song to retrieve the data for the songs
def parse_song(song):
    artists = [a['name'] for a in song['artists']]
    return {
        'name': song['name'],
        'artists': ', '.join(artists),
        'id': song['id']
    }


# Getting the player
def get_player(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('https://api.spotify.com/v1/me/player', headers=headers, timeout=5)
    return response.json()


# Add a song through query
def add_song_query(token, query):
    headers = {'Authorization': f'Bearer {token}'}
    query = quote(query)
    search_response = requests.get(f'https://api.spotify.com/v1/search?q={query}&type=track', headers=headers, timeout=5)
    track_id = search_response.json()['tracks']['items'][0]['id']
    add_song_id(token, track_id)


# Look up song from query
def query_for_song(token, query):
    headers = {'Authorization': f'Bearer {token}'}
    query = quote(query)
    search_response = requests.get(f'https://api.spotify.com/v1/search?q={query}&type=track', headers=headers, timeout=5)
    return search_response.json()['tracks']['items'][0]


# Get song data from ID
def get_track_by_id(token, track_id):
    headers = {'Authorization': f'Bearer {token}'}
    track_url = f'https://api.spotify.com/v1/tracks/{track_id}'
    response = requests.get(track_url, headers=headers, timeout=5)
    return response.json()


# Add a song directly through ID
def add_song_id(token, track_id):
    headers = {'Authorization': f'Bearer {token}'}
    uri = quote(f'spotify:track:{track_id}')
    response = requests.post(f'https://api.spotify.com/v1/me/player/queue?uri={uri}', headers=headers, timeout=5)
    return response.status_code


# Get the queue
def get_queue(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('https://api.spotify.com/v1/me/player/queue', headers=headers, timeout=5)
    return handle_responses(response)


# Play/Resume
def play(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.put('https://api.spotify.com/v1/me/player/play', headers=headers, timeout=5)
    return response.status_code


# Pause
def pause(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.put('https://api.spotify.com/v1/me/player/pause', headers=headers, timeout=5)
    return response.status_code


# Skip the current song
def skip(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.post('https://api.spotify.com/v1/me/player/next', headers=headers, timeout=5)
    return response.status_code


# Get currently playing track
def get_current_track(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('https://api.spotify.com/v1/me/player/currently-playing', headers=headers, timeout=5)
    return handle_responses(response)


def handle_responses(response):
    if response.status_code != 204 and response.status_code in range(200, 299):
        return response.json()
    return None


# Generate Code Verifier and Code Challenge
def generate_code_verifier_and_challenge():
    # Generate a code verifier with a random length between 43 and 128 characters
    length = secrets.choice(range(43, 129))
    code_verifier = ''.join(secrets.choice(string.ascii_letters + string.digits + '-._~') for _ in range(length))

    # Create the code challenge by hashing the code verifier with SHA-256 and encoding the hash with BASE64URL
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode('utf-8').rstrip('=')

    return code_verifier, code_challenge


# Get Authorization Code
def get_authorization_code(client_id, redirect_uri, code_challenge, state):
    state = base64.urlsafe_b64encode(hashlib.sha256(state.encode()).digest()).decode('utf-8')
    return f"{SPOTIFY_AUTHORIZATION_URL}?response_type=code&client_id={client_id}&scope={SCOPE_SPOTIFY}&redirect_uri={redirect_uri}&state={state}&code_challenge={code_challenge}&code_challenge_method=S256"


# Exchange Authorization Code for Tokens
def get_token(client_id, redirect_uri, code, code_verifier):
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'code_verifier': code_verifier
    }
    response = requests.post(OAUTH_SPOTIFY_TOKEN_URL, data=payload, timeout=5)
    return response.json()


# Refresh the Token
def refresh_access_token(client_id, refresh_token):
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
    }
    response = requests.post(OAUTH_SPOTIFY_TOKEN_URL, data=payload, timeout=5)
    return response.json()


async def start_spotify_oauth_flow(self):
    self.verify, challenge = generate_code_verifier_and_challenge()
    auth_url = get_authorization_code(self.configuration['spotify']['client_id'],
                                      self.configuration['spotify']['redirect_uri'], challenge,
                                      secrets.token_hex(64))
    wbopen(auth_url)
    self.authentication_flag.set()
    await self.await_authentication()


async def refresh_spotify_token(self):
    response = refresh_access_token(self.configuration['spotify']['client_id'],
                                    self.configuration['spotify-token']['refresh_token'])
    if 'access_token' in response:
        access_token = response.get('access_token')
        refresh_token = response.get('refresh_token')
        expires_in = response.get('expires_in')
        self.set_config('spotify-token', 'access_token', access_token)
        self.set_config('spotify-token', 'refresh_token', refresh_token)
        self.set_config('spotify-token', 'expires_in', str(expires_in))
        self.set_config('spotify-token', 'timestamp', str(int(time())))
        self.save_config()
    else:
        self.print.print_to_logs(f"Failed to refresh Spotify token: {response['error']}", self.print.YELLOW)
        self.print.print_to_logs(f"Response: {response}", self.print.WHITE)
        await start_spotify_oauth_flow(self)
