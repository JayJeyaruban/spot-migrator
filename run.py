import os
import json
import pickle
import sys
import spotipy
import spotipy.util as sutil

token_file = 'token.txt'

spotify_username = sys.argv[1]
playlist_file = sys.argv[2]

scope = 'playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative'

sp = 0


def pickle_to_file(content, filename):
    print('Saving', content, 'to file')
    with open(filename, 'wb') as f:
        pickle.dump(content, f)


def get_new_token():
    global token
    token = sutil.prompt_for_user_token(spotify_username, scope)

    if token:
        pickle_to_file(token, token_file)


def get_token():
    global token
    if os.path.exists(token_file):
        with open(token_file, 'rb') as f:
            token = pickle.load(f)
        print('Read', token, 'from file')
    else:
        get_new_token()
    # TODO: Check token is valid still


def load_json(filename):
    with open(filename, encoding='utf-8') as file:
        json_file = json.load(file)
        print('Successfully loaded file', filename)
        return json_file


def detect_valid_playlists(playlists):
    print('Detecting non-empty playlists')
    valid_playlists = []
    for playlist in playlists:
        playlist_name = playlist['name']
        tracks = playlist['tracks']
        detected_tracks = []
        for track in tracks:
            if track['source'] == '2':
                track_meta = track['track']
                detected_tracks.append(track_meta)

        if len(detected_tracks) > 1:
            valid_playlists.append((playlist_name, detected_tracks))

    return valid_playlists


def is_match(track_meta, spotify_track_meta):
    title, artist, album = track_meta
    spot_title = spotify_track_meta['name']
    spot_artist = spotify_track_meta['artists'][0]['name']
    spot_album = spotify_track_meta['album']['name']

    return title == spot_title and artist == spot_artist


def find_track_match(song_meta):
    name = song_meta['title']
    artist = song_meta['artist']
    album = song_meta['album']
    global sp
    results = sp.search(q=name, type='track', limit='50')

    for track in results['tracks']['items']:
        if is_match((name, artist, album), track):
            return track

    return None


def match_tracks(playlists):
    print('Finding song matches in Spotify library')
    new_playlists = []
    for playlist_name, tracks in playlists:
        matched_tracks = []
        for track in tracks:
            try:
                results = find_track_match(track)
            except spotipy.SpotifyException:
                get_new_token()
                global sp, token
                sp = spotipy.Spotify(auth=token)
                results = find_track_match(track)

            if results is not None:
                matched_tracks.append(results)

        new_playlists.append((playlist_name, matched_tracks))
        # print(results)
    return new_playlists


def playlist_in_list(playlist, list):
    for spot_playlist in list:
        if spot_playlist['name'] == playlist:
            return True, spot_playlist['id']

    return False, None


def track_in_playlist(playlist, track):
    for spot_track in playlist:
        if spot_track['track']['id'] == track['id'] or (
                spot_track['track']['name'] == track['name'] and
                spot_track['track']['artists'][0]['name'] == track['artists'][0]['name']):
            return True

    return False


def create_playlists(playlists):
    print('Creating playlists')
    results = sp.current_user_playlists(limit=50)
    existing_spot_playlists = results['items']
    for playlist, tracks in playlists:
        in_list, playlist_id = playlist_in_list(playlist, existing_spot_playlists)
        if not in_list:
            new_playlist = sp.user_playlist_create(spotify_username, playlist, '')
            playlist_id = new_playlist['id']

        spot_tracks = sp.user_playlist(spotify_username, playlist_id)['tracks']['items']
        tracks_to_add = []
        for track in tracks:
            if not track_in_playlist(spot_tracks, track):
                tracks_to_add.append(track['id'])

        if len(tracks_to_add) > 0:
            result = sp.user_playlist_add_tracks(spotify_username, playlist_id, tracks_to_add)


def migrate_playlists(playlists):
    valid_playlists = detect_valid_playlists(playlists)
    playlists_to_make = match_tracks(valid_playlists)
    create_playlists(playlists_to_make)


def main():
    global token, sp
    get_token()
    if token:
        sp = spotipy.Spotify(auth=token)
        lib_json = load_json(playlist_file)
        migrate_playlists(lib_json)
        # print('Saved')
    else:
        print('Unable to obtain token for', spotify_username)


if __name__ == '__main__':
    main()
