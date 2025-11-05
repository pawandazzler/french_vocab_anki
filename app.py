from flask import Flask, render_template, jsonify, request, session, send_file
from gtts import gTTS
import sqlite3, os, random

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_PATH = 'vocab.db'
AUDIO_DIR = 'static/audio'
os.makedirs(AUDIO_DIR, exist_ok=True)

# ----------------- DB -----------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                english TEXT UNIQUE,
                french TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_word (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                english TEXT,
                color TEXT DEFAULT 'gray',
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        conn.commit()

def seed_words():
    words = [
        ('cat', 'chat'),
        ('dog', 'chien'),
        ('house', 'maison'),
        ('apple', 'pomme'),
        ('book', 'livre'),
        ('car', 'voiture'),
        ('table', 'table'),
        ('water', 'eau'),
        ('bread', 'pain'),
        ('sun', 'soleil'),
        ('moon', 'lune'),
    ]

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        # Ensure 'english' is UNIQUE in table creation
        c.execute('''
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                english TEXT UNIQUE,
                french TEXT
            )
        ''')
        # Insert words; ignore if already present
        c.executemany("INSERT OR IGNORE INTO vocabulary (english, french) VALUES (?, ?)", words)
        conn.commit()


# ----------------- Helpers -----------------
def get_user_id():
    username = session.get("username")
    if not username:
        return None
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        row = c.fetchone()
        if row:
            return row[0]
    return None

# ----------------- Routes -----------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/get_color_counts')
def get_color_counts():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'green':0,'amber':0,'red':0,'gray':0})

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        counts = {}
        for color in ['green','amber','red','gray']:
            c.execute("SELECT COUNT(*) FROM user_word WHERE user_id=? AND color=?", (user_id,color))
            counts[color] = c.fetchone()[0]
    return jsonify(counts)

@app.route('/api/add_vocab_bulk', methods=['POST'])
def add_vocab_bulk():
    """
    Expects JSON payload:
    {
        "words": [
            {"english": "flower", "french": "fleur"},
            {"english": "tree", "french": "arbre"},
            ...
        ]
    }
    """
    data = request.get_json()
    if not data or 'words' not in data:
        return jsonify({"error": "Missing 'words' in request"}), 400

    words = data['words']
    if not isinstance(words, list) or not words:
        return jsonify({"error": "'words' must be a non-empty list"}), 400

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Insert words into vocabulary table (ignore duplicates)
        for word in words:
            english = word.get('english', '').strip()
            french = word.get('french', '').strip()
            if english and french:
                c.execute("INSERT OR IGNORE INTO vocabulary (english, french) VALUES (?, ?)", (english, french))

        # Get all users
        c.execute("SELECT id FROM users")
        user_ids = [row[0] for row in c.fetchall()]

        # Insert into user_word table for each user (ignore duplicates)
        for user_id in user_ids:
            for word in words:
                english = word.get('english', '').strip()
                if english:
                    c.execute("INSERT OR IGNORE INTO user_word (user_id, english, color) VALUES (?, ?, 'gray')", (user_id, english))

        conn.commit()

    return jsonify({"success": True, "added": len(words)})

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    if not username:
        return "Invalid username", 400

    session['username'] = username

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Create user if not exists
        c.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (username,))
        conn.commit()
        user_id = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()[0]

        # Ensure all vocabulary words exist for this user
        c.execute("SELECT english FROM vocabulary")
        words = [row[0] for row in c.fetchall()]

        # Insert into user_word only if combination (user_id, english) does NOT exist
        for w in words:
            c.execute("""
                INSERT OR IGNORE INTO user_word (user_id, english, color)
                VALUES (?, ?, 'gray')
            """, (user_id, w))
        conn.commit()

    return jsonify({"success": True})

@app.route('/api/get_random_words')
def get_random_words():
    color_filter = request.args.get('color', '').strip().lower()
    user_id = get_user_id()
    if not user_id:
        return jsonify([])

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if color_filter in ('red','amber','green'):
            c.execute("""
                SELECT uw.english, v.french, uw.color FROM user_word uw
                JOIN vocabulary v ON uw.english=v.english
                WHERE uw.user_id=? AND uw.color=?
                ORDER BY RANDOM() LIMIT 5
            """, (user_id, color_filter))
        else:
            c.execute("""
                SELECT uw.english, v.french, uw.color FROM user_word uw
                JOIN vocabulary v ON uw.english=v.english
                WHERE uw.user_id=?
                ORDER BY RANDOM() LIMIT 5
            """, (user_id,))
        rows = c.fetchall()
        return jsonify([dict(r) for r in rows])

@app.route('/api/check_answer', methods=['POST'])
def check_answer():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error':'no user'}), 400

    data = request.get_json()
    english = data.get('english', '').strip().lower()
    french_input = data.get('french', '').strip().lower()

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT french FROM vocabulary WHERE english=?", (english,))
        row = c.fetchone()
        if not row:
            return jsonify({'correct': False, 'correct_answer': 'Unknown'})
        correct_answer = row[0].lower()
        correct = (french_input == correct_answer)

        color = 'green' if correct else 'red'
        c.execute("UPDATE user_word SET color=? WHERE user_id=? AND english=?", (color, user_id, english))
        conn.commit()

    return jsonify({'correct': correct, 'correct_answer': correct_answer})

@app.route('/api/update_color', methods=['POST'])
def update_color():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error':'no user'}), 400

    data = request.get_json()
    english = data.get('english', '').strip()
    color = data.get('color', 'gray').strip().lower()

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE user_word SET color=? WHERE user_id=? AND english=?", (color, user_id, english))
        conn.commit()
    return jsonify({'success': True})

@app.route('/api/play_audio')
def play_audio():
    english = request.args.get('english', '').strip().lower()
    if not english:
        return jsonify({'error': 'missing parameter'}), 400

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT french FROM vocabulary WHERE english=?", (english,))
        row = c.fetchone()
        if not row:
            return jsonify({'error': 'word not found'}), 404
        french_word = row[0]

    # Generate audio
    audio_path = os.path.join(AUDIO_DIR, f"{french_word}.mp3")
    if not os.path.exists(audio_path):
        tts = gTTS(french_word, lang='fr')
        tts.save(audio_path)

    return send_file(audio_path, mimetype='audio/mpeg')

# ----------------- Main -----------------
if __name__ == '__main__':
    init_db()
    seed_words()
    app.run(host='0.0.0.0', port=5000, debug=True)
