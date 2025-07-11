from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

def init_db():
    conn = sqlite3.connect('database.db')
    with open('data.sql', 'r') as f:
        sql_script = f.read()
    conn.executescript(sql_script)
    conn.commit()
    conn.close()

app = Flask(__name__)
app.secret_key = 'supersegretissima'

@app.route('/')
def home():
    if 'user' in session:
        return redirect('/welcome')
    return redirect('/test_login_pt1')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT password FROM utenti WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[0], password):
            session['user'] = username
            return redirect('/welcome')
        else:
            return "Username o password errati"

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO utenti (username, email, password) VALUES (?, ?, ?)", 
                      (username, email, password))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Username o email già usati"
        finally:
            conn.close()

        return redirect('/login')

    return render_template('register.html')

@app.route('/welcome')
def welcome():
    if 'user' not in session:
        return redirect('/login')
    return render_template('welcome.html', user=session['user'])

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')
    
if __name__ == '__main__':
    init_db()  # crea il DB e le tabelle da data.sql
    app.run(debug=True)

#per adesso ho chiesto a chat, poi mi informo bene su come funziona il ciò
