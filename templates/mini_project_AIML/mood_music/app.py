import os
import random
from flask import Flask, jsonify, render_template
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

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.get('/api/song/<mood>')
    def get_song_for_mood(mood: str):
        mood = mood.lower()
        files = mood_to_files.get(mood, [])
        if not files:
            # Search fallbacks
            for fb in fallback_order:
                if mood_to_files.get(fb):
                    files = mood_to_files[fb]
                    break

        if not files:
            # No files at all; return 404 with message
            return jsonify({
                'ok': False,
                'message': 'No music files found in static/static_music. Add MP3s like happy1.mp3, sad1.mp3.'
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
        return jsonify({'ok': True, 'path': static_path, 'mood': mood, 'file': chosen})

    return app


app = create_app()


if __name__ == '__main__':
    # Ensure the server runs on a friendly host/port
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)


