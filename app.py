from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'supersegretissima'

# --- Setup database path ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'database.db')


# --- Database Helpers ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Create UTENTE table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS UTENTE (
            username TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Create NOTIFICA table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS NOTIFICA (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usernameN TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            entry_timestamp TEXT NOT NULL,
            exit_timestamp TEXT NOT NULL,
            account_size REAL NOT NULL,
            fraction_invested REAL NOT NULL,
            notes TEXT,
            asset_type TEXT,
            FOREIGN KEY (usernameN) REFERENCES UTENTE(username)
        )
    ''')
    conn.commit()
    conn.close()


# --- Dummy Analyzer Function ---
def analyze_biases(trades):
    # Replace this logic with your real detection
    results = {
        "Overconfidence": False,
        "Loss Aversion": False,
        "Feedback": "Analysis complete. No major biases detected."
    }

    for trade in trades:
        if float(trade["fraction_invested"]) > 0.05:
            results["Overconfidence"] = True
            results["Feedback"] = "You may be overconfident – high position size."
        if float(trade["exit_price"]) < float(trade["entry_price"]):
            results["Loss Aversion"] = True
            results["Feedback"] += " Possible loss aversion behavior detected."

    return results


# --- Routes ---
@app.route('/')
def home():
    if 'user' in session:
        return redirect('/trade_input')
    return redirect('/login')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO UTENTE (username, email, password) VALUES (?, ?, ?)',
                         (username, email, password))
            conn.commit()
            session['user'] = username
            return redirect('/trade_input')
        except sqlite3.IntegrityError:
            return "Username or email already in use."
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM UTENTE WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user'] = user['username']
            return redirect('/trade_input')
        else:
            return "Invalid username or password"

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/trade_input', methods=['GET', 'POST'])
def trade_input():
    if 'user' not in session:
        return redirect('/login')

    if request.method == 'POST':
        username = session['user']
        entry_price = request.form['entry_price']
        exit_price = request.form['exit_price']
        entry_timestamp = request.form['entry_timestamp']
        exit_timestamp = request.form['exit_timestamp']
        account_size = request.form['account_size']
        fraction_invested = request.form['fraction_invested']
        notes = request.form['notes']
        asset_type = request.form['asset_type']

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO NOTIFICA (
                usernameN, entry_price, exit_price, entry_timestamp, exit_timestamp,
                account_size, fraction_invested, notes, asset_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            username, entry_price, exit_price, entry_timestamp, exit_timestamp,
            account_size, fraction_invested, notes, asset_type
        ))
        conn.commit()

        # Fetch all trades from user
        trades = conn.execute('SELECT * FROM NOTIFICA WHERE usernameN = ?', (username,)).fetchall()
        conn.close()

        # Analyze trades
        trade_dicts = [dict(row) for row in trades]
        results = analyze_biases(trade_dicts)
        session['last_results'] = results  # store for result page

        return redirect('/analysis_results')

    return render_template('trade_input.html')


@app.route('/analysis_results')
def analysis_results():
    if 'last_results' not in session:
        return "No analysis results available."

    results = session['last_results']
    return render_template('analysis_results.html', results=results)


# --- Initialize DB and Run ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True)


