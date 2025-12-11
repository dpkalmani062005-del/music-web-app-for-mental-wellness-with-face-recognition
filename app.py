import os
import random
import requests
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=os.path.join('static'),
        template_folder=os.path.join('templates'),
    )
    CORS(app)

    # Map moods to available songs in /static/static_music/{mood}/ folders
    music_root = os.path.join(app.static_folder, 'static_music')

    # Build a dictionary of mood -> [filenames] from mood-specific folders
    mood_to_files = {
        'happy': [],
        'sad': [],
        'angry': [],
        'neutral': [],
        'surprised': [],
        'fearful': [],
        'disgusted': [],
    }

    # Auto-discover files in mood-specific folders
    for mood in mood_to_files.keys():
        mood_folder = os.path.join(music_root, mood)
        if os.path.isdir(mood_folder):
            for filename in os.listdir(mood_folder):
                if filename.lower().endswith('.mp3'):
                    # Store path relative to /static/static_music/
                    mood_to_files[mood].append(f"{mood}/{filename}")

    # Provide simple fallbacks if exact mood has no files
    # neutral should have at least one default if present
    fallback_order = ['neutral', 'happy', 'sad', 'angry']

    # Track last served filename per mood to avoid immediate repeats
    last_served_for_mood: dict[str, str | None] = {m: None for m in mood_to_files}

    # Spotify API configuration
    SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', '')
    SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', '')
    USE_SPOTIFY = bool(SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)

    # Mood to Spotify search terms mapping
    mood_to_spotify_terms = {
        'happy': 'upbeat happy energetic',
        'sad': 'sad melancholic emotional',
        'angry': 'intense aggressive powerful',
        'neutral': 'calm peaceful ambient',
        'surprised': 'energetic exciting dynamic',
        'fearful': 'dark atmospheric tense',
        'disgusted': 'intense dramatic',
    }

    def get_spotify_token():
        """Get Spotify access token using Client Credentials flow"""
        if not USE_SPOTIFY:
            return None
        try:
            auth_url = 'https://accounts.spotify.com/api/token'
            auth_response = requests.post(
                auth_url,
                {
                    'grant_type': 'client_credentials',
                    'client_id': SPOTIFY_CLIENT_ID,
                    'client_secret': SPOTIFY_CLIENT_SECRET,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            if auth_response.status_code == 200:
                return auth_response.json().get('access_token')
        except Exception as e:
            print(f"Spotify token error: {e}")
        return None

    def search_spotify_track(mood: str, token: str):
        """Search for a track on Spotify based on mood"""
        if not token:
            print("No Spotify token available")
            return None
        try:
            # Get mood-specific search term
            search_term = mood_to_spotify_terms.get(mood, 'music')
            print(f"Searching Spotify for mood '{mood}' with term: {search_term}")
            search_url = 'https://api.spotify.com/v1/search'
            headers = {'Authorization': f'Bearer {token}'}
            params = {
                'q': search_term,
                'type': 'track',
                'limit': 50,  # Get more results for better selection
                'market': 'US'  # US market for better song availability
            }
            response = requests.get(search_url, headers=headers, params=params, timeout=10)
            print(f"Spotify API response status: {response.status_code}")
            
            if response.status_code == 200:
                tracks = response.json().get('tracks', {}).get('items', [])
                print(f"Found {len(tracks)} tracks")
                
                if tracks:
                    # Prioritize tracks with preview URLs
                    tracks_with_preview = [t for t in tracks if t.get('preview_url')]
                    
                    # Use tracks with preview URLs first, then all tracks
                    if tracks_with_preview:
                        tracks_to_use = tracks_with_preview
                        print(f"Using {len(tracks_with_preview)} tracks with preview URLs")
                    else:
                        tracks_to_use = tracks
                        print(f"Using {len(tracks_to_use)} tracks (some may not have preview)")
                    
                    # Select a random track
                    track = random.choice(tracks_to_use)
                    
                    result = {
                        'name': track['name'],
                        'artist': ', '.join([a['name'] for a in track['artists']]),
                        'preview_url': track.get('preview_url'),
                        'external_url': track['external_urls'].get('spotify'),
                        'album_image': track['album']['images'][0]['url'] if track['album']['images'] else None
                    }
                    print(f"Selected track: {result['name']} by {result['artist']}, preview_url: {result['preview_url'] is not None}")
                    return result
                else:
                    print("No tracks found in Spotify response")
            else:
                print(f"Spotify API error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Spotify search error: {e}")
            import traceback
            traceback.print_exc()
        return None

    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.get('/api/status')
    def get_status():
        """Get API status and configuration"""
        return jsonify({
            'spotify_configured': USE_SPOTIFY,
            'spotify_client_id_set': bool(SPOTIFY_CLIENT_ID),
            'local_files_available': sum(len(files) for files in mood_to_files.values()) > 0,
            'mood_files': {mood: len(files) for mood, files in mood_to_files.items()}
        })

    @app.get('/api/song/<mood>')
    def get_song_for_mood(mood: str):
        mood = mood.lower()
        use_spotify = request.args.get('spotify', 'false').lower() == 'true'
        
        print(f"Request for mood: {mood}, use_spotify: {use_spotify}, USE_SPOTIFY: {USE_SPOTIFY}")
        
        # Try Spotify first if enabled and requested
        spotify_failed = False
        if use_spotify:
            if not USE_SPOTIFY:
                print("Spotify requested but credentials not configured, falling back to local files")
                spotify_failed = True
            else:
                token = get_spotify_token()
                if token:
                    print("Got Spotify token, searching for track...")
                    spotify_track = search_spotify_track(mood, token)
                    if spotify_track:
                        if spotify_track.get('preview_url'):
                            print(f"Returning Spotify track with preview: {spotify_track['name']}")
                            return jsonify({
                                'ok': True,
                                'source': 'spotify',
                                'mood': mood,
                                'name': spotify_track['name'],
                                'artist': spotify_track['artist'],
                                'preview_url': spotify_track['preview_url'],
                                'external_url': spotify_track['external_url'],
                                'album_image': spotify_track['album_image']
                            })
                        else:
                            print(f"Spotify track found but no preview URL: {spotify_track['name']}")
                            # Still try local files if no preview
                            spotify_failed = True
                    else:
                        print("No Spotify track found, falling back to local files")
                        spotify_failed = True
                else:
                    print("Failed to get Spotify token, falling back to local files")
                    spotify_failed = True
        
        # Fallback to local files (always try this)
        print(f"Trying local files for mood: {mood}")
        
        # Fallback to local files
        files = mood_to_files.get(mood, [])
        if not files:
            # Search fallbacks
            for fb in fallback_order:
                if mood_to_files.get(fb):
                    files = mood_to_files[fb]
                    break

        if not files:
            # Try Spotify as fallback if local files not available
            if USE_SPOTIFY and not use_spotify:
                print("No local files, trying Spotify as fallback...")
                token = get_spotify_token()
                if token:
                    spotify_track = search_spotify_track(mood, token)
                    if spotify_track and spotify_track.get('preview_url'):
                        return jsonify({
                            'ok': True,
                            'source': 'spotify',
                            'mood': mood,
                            'name': spotify_track['name'],
                            'artist': spotify_track['artist'],
                            'preview_url': spotify_track['preview_url'],
                            'external_url': spotify_track['external_url'],
                            'album_image': spotify_track['album_image']
                        })
            
            # No files at all; return helpful message
            message = 'No music files found for this mood. '
            if USE_SPOTIFY:
                message += 'Spotify is configured but no preview available. '
            message += 'Add MP3s in /static/static_music/{mood}/ folders or configure Spotify API with preview URLs.'
            return jsonify({
                'ok': False,
                'message': message
            }), 404

        # Avoid immediate repeat per mood if possible
        chosen = None
        if len(files) == 1:
            chosen = files[0]
        else:
            previous = last_served_for_mood.get(mood)
            candidates = [f for f in files if f != previous]
            chosen = random.choice(candidates) if candidates else random.choice(files)

        last_served_for_mood[mood] = chosen

        # Return path relative to /static
        static_path = f"/static/static_music/{chosen}"
        return jsonify({
            'ok': True,
            'source': 'local',
            'path': static_path,
            'mood': mood,
            'file': chosen
        })

    return app


app = create_app()


if __name__ == '__main__':
    # Ensure the server runs on a friendly host/port
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)


