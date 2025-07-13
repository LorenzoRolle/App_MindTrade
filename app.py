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
        return redirect('/trade_input')
    return redirect('/keyaccesspage')
    

@app.route('/keyaccesspage', methods=['GET', 'POST'])
def keyaccess():
    if request.method == 'POST':
        access_key = request.form['access_key']
        if access_key == 'X9v!$dZ7#rQf@P3&lmT^wYSjNkV8Hg6':
            return redirect('/intro')
        else:
            return "Access Denied. Invalid Key."
    return render_template('keyaccesspage.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT password FROM UTENTE WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[0], password):
            session['user'] = username
            return redirect('/trade_input')
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
            c.execute("INSERT INTO UTENTE (username, email, password) VALUES (?, ?, ?)", 
                      (username, email, password))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Username o email già usati"
        finally:
            conn.close()

        return redirect('/trade_input')

    return render_template('register.html')

@app.route('/intro', methods=['GET', 'POST'])
def intro():
    return render_template('intro.html')

@app.route('/trade_input', methods=['GET', 'POST'])
def trade_input():
    if 'user' not in session:
        return redirect('/login')

    if request.method == 'POST':
        email = session['email']
        entry_price = request.form['entry_price']
        exit_price = request.form['exit_price']
        entry_timestamp = request.form['entry_timestamp']
        exit_timestamp = request.form['exit_timestamp']
        account_size = request.form['account_size']
        fraction_invested = request.form['fraction_invested']
        notes = request.form['notes']
        asset_type = request.form['asset_type']

        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO NOTIFICA (
                    email, entry_price, exit_price, entry_timestamp, exit_timestamp,
                    account_size, fraction_invested, notes, asset_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                email, entry_price, exit_price, entry_timestamp, exit_timestamp,
                account_size, fraction_invested, notes, asset_type
            ))
            conn.commit()
        except sqlite3.IntegrityError as e:
            conn.close()
            return f'Error in saving: {e}'
        conn.close()
        return 'Data successfully saved!'

    return render_template('trade_input.html')

if __name__ == '__main__':
    app.run(debug=True)

#per adesso ho chiesto a chat, poi mi informo bene su come funziona il ciò
