from flask import Flask, request, redirect, render_template
import sqlite3
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
DB_NAME = "songs.db"

def to_embed_url(url: str) -> str:
    """
    Converts any YouTube URL into a clean embed URL with no extra parameters.
    """
    parsed = urlparse(url)

    # Case 1 — Short form: https://youtu.be/<id>
    if "youtu.be" in parsed.netloc:
        video_id = parsed.path.lstrip("/")
        return f"https://www.youtube.com/embed/{video_id}"

    # Case 2 — Regular YouTube URL: https://www.youtube.com/watch?v=<id>
    if "youtube.com" in parsed.netloc:
        params = parse_qs(parsed.query)
        video_id = params.get("v", [None])[0]
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"

    # If not a YouTube URL, return unchanged
    return url


# Initialize database
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            youtube_url TEXT NOT NULL,
            name TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Route 1: Add a song (HTML form + POST handler)
@app.route('/add_song', methods=['GET', 'POST'])
def add_song():
    if request.method == 'POST':
        title = request.form.get('title')
        youtube_url = request.form.get('youtube_url')
        name = request.form.get('name')
        youtube_url = to_embed_url(youtube_url)
        if not title or not youtube_url:
            return "Please provide both a song title and YouTube URL.", 400

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO songs (title, youtube_url, name) VALUES (?, ?, ?)",
                       (title, youtube_url, name))
        conn.commit()
        conn.close()

        return redirect('/add_song')

    # Render HTML form template
    return render_template("add_song.html")

# Route 2: Display all songs in a table
@app.route('/songs', methods=['GET'])
def show_songs():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, youtube_url, name FROM songs")
    songs = cursor.fetchall()
    conn.close()

    return render_template("songs.html", songs=songs)

# Route 3: Main to redirect to others
@app.route('/', methods=['GET'])
def show_redirects():
    return render_template("index.html")

# Route 4: Display the song in the table with the same id
@app.route('/songs/<int:song_id>', methods=['GET'])
def show_song(song_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, youtube_url, name FROM songs WHERE id = ?", (song_id,))
    song = cursor.fetchone()
    conn.close()
    if song is None:
        return f"No song found with ID {song_id} <a href='/songs'>View all songs</a>", 404
    song_ = {}
    song_["id"] = song[0]
    song_["title"] = song[1]
    song_["url"] = song[2]
    song_["name"] = song[3]
    return render_template("song.html", song=song_)


if __name__ == '__main__':
    app.run(debug=True)
