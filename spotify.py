import re
import string
from urllib.parse import quote

import base64
import hashlib
import requests
import secrets


SPOTIFY_AUTHORIZATION_URL = "https://accounts.spotify.com/authorize"
OAUTH_SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPE_SPOTIFY = "user-read-playback-state user-modify-playback-state"


# Getting the player
def get_player(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('https://api.spotify.com/v1/me/player', headers=headers)
    return response.json()


# Add a song through query
def add_song_query(token, query):
    headers = {'Authorization': f'Bearer {token}'}
    query = quote(query)
    search_response = requests.get(f'https://api.spotify.com/v1/search?q={query}&type=track', headers=headers)
    track_id = search_response.json()['tracks']['items'][0]['id']
    add_song_id(token, track_id)


# Look up song from query
def query_for_song(token, query):
    headers = {'Authorization': f'Bearer {token}'}
    query = quote(query)
    search_response = requests.get(f'https://api.spotify.com/v1/search?q={query}&type=track', headers=headers)
    return search_response.json()['tracks']['items'][0]


# Get song data from ID
def get_track_by_id(token, track_id):
    headers = {'Authorization': f'Bearer {token}'}
    track_url = f'https://api.spotify.com/v1/tracks/{track_id}'
    response = requests.get(track_url, headers=headers)
    return response.json()


# Add a song directly through ID
def add_song_id(token, track_id):
    headers = {'Authorization': f'Bearer {token}'}
    uri = quote(f'spotify:track:{track_id}')
    response = requests.post(f'https://api.spotify.com/v1/me/player/queue?uri={uri}', headers=headers)
    return response.status_code


# Get the queue
def get_queue(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get('https://api.spotify.com/v1/me/player/queue', headers=headers)
    return response.json()


# Play/Resume
def play(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.put('https://api.spotify.com/v1/me/player/play', headers=headers)
    return response.status_code


# Pause
def pause(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.put('https://api.spotify.com/v1/me/player/pause', headers=headers)
    return response.status_code


# Skip the current song
def skip(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.post('https://api.spotify.com/v1/me/player/next', headers=headers)
    return response.status_code


# Get currently playing track
def get_current_track(token):
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.post('https://api.spotify.com/v1/me/player/currently-playing', headers=headers)
    return response.status_code


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
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier
    }
    response = requests.post(OAUTH_SPOTIFY_TOKEN_URL, data=payload)
    return response.json()


# Refresh the Token
def refresh_access_token(client_id, refresh_token):
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    response = requests.post(OAUTH_SPOTIFY_TOKEN_URL, data=payload)
    return response.json()
