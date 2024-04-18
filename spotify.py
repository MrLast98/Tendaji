from urllib.parse import quote

from flask import Flask, request, jsonify
import requests
import base64
import json
import threading

# app = Flask(__name__)

# Replace these with your actual credentials
client_id = 'YOUR_CLIENT_ID'
client_secret = 'YOUR_CLIENT_SECRET'
redirect_uri = 'http://localhost:3000/callback'


# OAuth2 login
def get_token():
    auth_url = 'https://accounts.spotify.com/authorize'
    token_url = 'https://accounts.spotify.com/api/token'
    scope = 'user-modify-playback-state user-read-playback-state'
    auth_response = requests.get(auth_url, params={
        'response_type': 'code',
        'client_id': client_id,
        'scope': scope,
        'redirect_uri': redirect_uri
    })
    print(f"Please go to {auth_response.url} and authorize access.")

    # Start the Flask server in a separate thread
    server_thread = threading.Thread(target=app.run, kwargs={'port': 3000})
    server_thread.start()

    # Wait for the server to start
    # while not app.is_running:
    #     pass

    # The server will handle the callback and set the access token
    # This function will return once the token is obtained


# Callback endpoint
# @app.route('/callback')
# def callback():
#     auth_code = request.args.get('code')
#     token_url = 'https://accounts.spotify.com/api/token'
#     headers = {
#         'Authorization': 'Basic ' + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode('utf-8'),
#         'Content-Type': 'application/x-www-form-urlencoded'
#     }
#     data = {
#         'grant_type': 'authorization_code',
#         'code': auth_code,
#         'redirect_uri': redirect_uri,
#         'client_id': client_id,
#         'client_secret': client_secret
#     }
#     response = requests.post(token_url, headers=headers, data=data)
#     response_data = response.json()
#     access_token = response_data['access_token']
#     refresh_token = response_data['refresh_token']
#     # Here you can store the tokens as needed
#     print(f"Access Token: {access_token}")
#     print(f"Refresh Token: {refresh_token}")
#     return jsonify({'status': 'success'})


# Refresh token function
def refresh_token(refresh_token):
    token_url = 'https://accounts.spotify.com/api/token'
    headers = {
        'Authorization': 'Basic ' + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode('utf-8'),
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    response = requests.post(token_url, headers=headers, data=data)
    response_data = response.json()
    new_access_token = response_data['access_token']
    # Here you can store the new access token as needed
    print(f"New Access Token: {new_access_token}")
    return new_access_token


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


def query_for_song(token, query):
    headers = {'Authorization': f'Bearer {token}'}
    query = quote(query)
    search_response = requests.get(f'https://api.spotify.com/v1/search?q={query}&type=track', headers=headers)
    return search_response.json()['tracks']['items'][0]


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
