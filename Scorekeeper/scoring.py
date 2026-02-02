from flask import  Blueprint, request, redirect, render_template, jsonify, g, url_for
from urllib.parse import urlparse, parse_qs
import sqlite3
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from time import sleep


scoring = Blueprint("scoring", __name__ ,static_folder="../static", template_folder="../templates")
DATABASE = "scoring.db"

# Database helper functions
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid

# Initialize database (non-destructive)
def init_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row

    # Create Session table if not exists
    db.execute('''
        CREATE TABLE IF NOT EXISTS Session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT DEFAULT ''
        )
    ''')

    # Create Gamer table if not exists
    db.execute('''
        CREATE TABLE IF NOT EXISTS Gamer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            total_points INTEGER DEFAULT 0,
            points_history TEXT DEFAULT ''
        )
    ''')

    # Create Team table if not exists
    db.execute('''
        CREATE TABLE IF NOT EXISTS Team (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES Session(id) ON DELETE CASCADE,
            UNIQUE(session_id, name)
        )
    ''')

    # Create TeamMember junction table if not exists
    db.execute('''
        CREATE TABLE IF NOT EXISTS TeamMember (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            gamer_id INTEGER NOT NULL,
            FOREIGN KEY (team_id) REFERENCES Team(id) ON DELETE CASCADE,
            FOREIGN KEY (gamer_id) REFERENCES Gamer(id) ON DELETE CASCADE,
            UNIQUE(team_id, gamer_id)
        )
    ''')

    # Create Game table if not exists
    db.execute('''
        CREATE TABLE IF NOT EXISTS Game (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            date_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            game_type TEXT NOT NULL CHECK(game_type IN ('team', 'individual')),
            FOREIGN KEY (session_id) REFERENCES Session(id) ON DELETE CASCADE
        )
    ''')

    # Create GameScore table if not exists
    db.execute('''
        CREATE TABLE IF NOT EXISTS GameScore (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            team_id INTEGER,
            gamer_id INTEGER,
            points INTEGER NOT NULL,
            FOREIGN KEY (game_id) REFERENCES Game(id) ON DELETE CASCADE,
            FOREIGN KEY (team_id) REFERENCES Team(id) ON DELETE CASCADE,
            FOREIGN KEY (gamer_id) REFERENCES Gamer(id) ON DELETE CASCADE,
            CHECK((team_id IS NULL AND gamer_id IS NOT NULL) OR
                  (team_id IS NOT NULL AND gamer_id IS NULL))
        )
    ''')
    db.commit()
    db.close()
    print("Database initialized successfully!")

# Routes

init_db()

# ===== SESSION ROUTES =====

@scoring.route("/session/create")
def create_session():
    """Create a new session"""
    if request.method == "POST":
        try:
            print(request.form)
            name = request.form.get('session_name')
            desc = request.form.get('desc')
            execute_db('INSERT INTO Session (name, description) VALUES (?, ?)',
                               (name, desc))
            sleep(5)
            return redirect(url_for('scoring.get_gamers'))
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Gamer with this name already exists'}), 400
    return render_template("session_create.html")

# ===== GAMER ROUTES =====

@scoring.route("/gamer/create", methods=['GET', 'POST'])
def create_gamer():
    """Create a new gamer"""
    if request.method == "POST":
        try:
            print(request.form)
            name = request.form.get('name')
            gamer_id = execute_db('INSERT INTO Gamer (name) VALUES (?)', (name,))
            sleep(5)
            return redirect(url_for('scoring.get_gamers'))
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Gamer with this name already exists'}), 400
    return render_template("gamer_create.html")

@scoring.route('/gamer/list', methods=['GET'])
def get_gamers():
    """Get all gamers"""
    gamers = query_db('SELECT * FROM Gamer ORDER BY total_points DESC')

    return render_template("gamer_list.html", gamers = gamers)

# @scoring.route('/gamers', methods=['POST'])
# def create_gamer():
#     """Create a new gamer"""
#     data = request.json
#     if not data or 'name' not in data:
#         return jsonify({'error': 'Name is required'}), 400

#     try:
#         gamer_id = execute_db('INSERT INTO Gamer (name) VALUES (?)', (data['name'],))
#         return jsonify({'id': gamer_id, 'name': data['name'], 'total_points': 0}), 201
#     except sqlite3.IntegrityError:
#         return jsonify({'error': 'Gamer with this name already exists'}), 400

@scoring.route('/gamers/<int:gamer_id>', methods=['GET'])
def get_gamer(gamer_id):
    """Get a specific gamer"""
    gamer = query_db('SELECT * FROM Gamer WHERE id = ?', [gamer_id], one=True)
    if gamer is None:
        return jsonify({'error': 'Gamer not found'}), 404
    return jsonify(dict(gamer))

# ===== TEAM ROUTES =====

@scoring.route('/teams', methods=['GET'])
def get_teams():
    """Get all teams with their members"""
    teams = query_db('SELECT * FROM Team')
    result = []
    for team in teams:
        members = query_db('''
            SELECT g.id, g.name, g.total_points
            FROM Gamer g
            JOIN TeamMember tm ON g.id = tm.gamer_id
            WHERE tm.team_id = ?
        ''', [team['id']])
        result.append({
            'id': team['id'],
            'name': team['name'],
            'members': [dict(m) for m in members]
        })
    return jsonify(result)

@scoring.route('/teams', methods=['POST'])
def create_team():
    """Create a new team"""
    data = request.json
    if not data or 'name' not in data:
        return jsonify({'error': 'Name is required'}), 400

    try:
        team_id = execute_db('INSERT INTO Team (name) VALUES (?)', (data['name'],))

        # Add members if provided
        if 'member_ids' in data and data['member_ids']:
            for gamer_id in data['member_ids']:
                execute_db('INSERT INTO TeamMember (team_id, gamer_id) VALUES (?, ?)',
                          (team_id, gamer_id))

        return jsonify({'id': team_id, 'name': data['name']}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Team name already exists or invalid member ID'}), 400

@scoring.route('/teams/<int:team_id>/members', methods=['POST'])
def add_team_member(team_id):
    """Add a member to a team"""
    data = request.json
    if not data or 'gamer_id' not in data:
        return jsonify({'error': 'gamer_id is required'}), 400

    try:
        execute_db('INSERT INTO TeamMember (team_id, gamer_id) VALUES (?, ?)',
                  (team_id, data['gamer_id']))
        return jsonify({'message': 'Member added successfully'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Member already in team or invalid IDs'}), 400

# ===== GAME ROUTES =====

@scoring.route('/games', methods=['GET'])
def get_games():
    """Get all games"""
    games = query_db('SELECT * FROM Game ORDER BY date_played DESC')
    return jsonify([dict(game) for game in games])

@scoring.route('/games', methods=['POST'])
def create_game():
    """Create a new game and record scores"""
    data = request.json
    if not data or 'name' not in data or 'game_type' not in data or 'scores' not in data:
        return jsonify({'error': 'name, game_type, and scores are required'}), 400

    if data['game_type'] not in ['team', 'individual']:
        return jsonify({'error': 'game_type must be "team" or "individual"'}), 400

    try:
        # Create game
        game_id = execute_db('INSERT INTO Game (name, game_type) VALUES (?, ?)',
                            (data['name'], data['game_type']))

        # Add scores
        for score_entry in data['scores']:
            points = score_entry['points']

            if data['game_type'] == 'team':
                team_id = score_entry['team_id']
                execute_db('INSERT INTO GameScore (game_id, team_id, points) VALUES (?, ?, ?)',
                          (game_id, team_id, points))

                # Update each team member's points
                members = query_db('SELECT gamer_id FROM TeamMember WHERE team_id = ?', [team_id])
                for member in members:
                    update_gamer_points(member['gamer_id'], points, data['name'])

            else:  # individual
                gamer_id = score_entry['gamer_id']
                execute_db('INSERT INTO GameScore (game_id, gamer_id, points) VALUES (?, ?, ?)',
                          (game_id, gamer_id, points))
                update_gamer_points(gamer_id, points, data['name'])

        return jsonify({'id': game_id, 'message': 'Game created successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@scoring.route('/games/<int:game_id>', methods=['GET'])
def get_game(game_id):
    """Get a specific game with scores"""
    game = query_db('SELECT * FROM Game WHERE id = ?', [game_id], one=True)
    if game is None:
        return jsonify({'error': 'Game not found'}), 404

    scores = query_db('''
        SELECT gs.points, gs.team_id, gs.gamer_id,
               t.name as team_name, g.name as gamer_name
        FROM GameScore gs
        LEFT JOIN Team t ON gs.team_id = t.id
        LEFT JOIN Gamer g ON gs.gamer_id = g.id
        WHERE gs.game_id = ?
    ''', [game_id])

    return jsonify({
        'id': game['id'],
        'name': game['name'],
        'date_played': game['date_played'],
        'game_type': game['game_type'],
        'scores': [dict(s) for s in scores]
    })

# ===== LEADERBOARD ROUTE =====

@scoring.route('/leaderboard', methods=['GET'])
def leaderboard():
    """Get leaderboard of all gamers"""
    gamers = query_db('SELECT name, total_points, points_history FROM Gamer ORDER BY total_points DESC')
    return jsonify([dict(g) for g in gamers])

# Helper function to update gamer points
def update_gamer_points(gamer_id, points, game_name):
    """Update a gamer's total points and history"""
    gamer = query_db('SELECT total_points, points_history FROM Gamer WHERE id = ?',
                     [gamer_id], one=True)

    new_total = gamer['total_points'] + points
    new_history = gamer['points_history']
    if new_history:
        new_history += f"\n{game_name}: +{points}"
    else:
        new_history = f"{game_name}: +{points}"

    execute_db('UPDATE Gamer SET total_points = ?, points_history = ? WHERE id = ?',
              (new_total, new_history, gamer_id))