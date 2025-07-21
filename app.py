from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

# Definisci il percorso assoluto per il database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'database.db')

print(f"Database path: {DATABASE_PATH}")

def init_db():
    """Inizializza il database con SQL diretto"""
    print(f"Inizializzando database in: {DATABASE_PATH}")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        # Verifica se la tabella UTENTE esiste
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='UTENTE';
        """)
        
        if not cursor.fetchone():
            print("Tabelle non trovate, creando con SQL diretto...")
            
            # Crea tabella UTENTE
            cursor.execute("""
                CREATE TABLE UTENTE(
                    username VARCHAR(50) PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL
                )
            """)
            print("Tabella UTENTE creata.")
            
            # Crea tabella NOTIFICA
            cursor.execute("""
                CREATE TABLE NOTIFICA (
                    id INTEGER PRIMARY KEY,
                    usernameN VARCHAR(50) NOT NULL,
                    entry_price DECIMAL(10, 2) NOT NULL,
                    exit_price DECIMAL(10, 2) NOT NULL,
                    entry_timestamp TIMESTAMP NOT NULL,
                    exit_timestamp TIMESTAMP NOT NULL,
                    account_size DECIMAL(15, 2) NOT NULL,
                    fraction_invested DECIMAL(5, 4) NOT NULL,
                    notes TEXT,
                    asset_type VARCHAR(10) CHECK (asset_type IN ('Stock', 'ETF', 'Crypto', 'Forex')),
                    FOREIGN KEY (usernameN) REFERENCES UTENTE(username)
                        ON DELETE CASCADE
                        ON UPDATE CASCADE
                )
            """)
            print("Tabella NOTIFICA creata.")
            
            conn.commit()
            print("Tutte le tabelle create con successo!")
            
        else:
            print("Tabelle esistenti trovate.")
            # Debug: mostra quanti utenti ci sono
            cursor.execute("SELECT COUNT(*) FROM UTENTE")
            user_count = cursor.fetchone()[0]
            print(f"Utenti esistenti nel database: {user_count}")
        
    except sqlite3.Error as e:
        print(f"ERRORE SQLite: {e}")
        print(f"Tipo errore: {type(e)}")
        
    finally:
        conn.close()

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Per accedere alle colonne per nome
    return conn

def debug_database():
    """Funzione per debug del database"""
    if os.path.exists(DATABASE_PATH):
        print(f"File database esistente: {DATABASE_PATH}")
        print(f"Dimensione file: {os.path.getsize(DATABASE_PATH)} bytes")
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM UTENTE")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM NOTIFICA")
        notifica_count = cursor.fetchone()[0]
        
        print(f"Utenti nel database: {user_count}")
        print(f"Notifiche nel database: {notifica_count}")
        
        # Mostra tutti gli username
        cursor.execute("SELECT username FROM UTENTE")
        users = cursor.fetchall()
        print(f"Utenti registrati: {[user[0] for user in users]}")
        
        conn.close()
    else:
        print(f"File database NON trovato in: {DATABASE_PATH}")

app = Flask(__name__)
app.secret_key = 'supersegretissima'

# Inizializza il database all'avvio
print("Verificando/creando il database...")
init_db()
debug_database()
print("Database pronto!")

@app.route('/')
def home():
    if 'user' in session:
        return redirect('/trade_input')
    return redirect('/keyaccesspage')
    

@app.route('/keyaccesspage', methods=['GET', 'POST'])
def keyaccesspage():
    if request.method == 'POST':
        access_key = request.form['access_key']
        if access_key == 'X9v!$dZ7#rQf@P3&lmT^wYSjNkV8Hg6':
            session['access_granted'] = True
            return redirect('/intro')
        else:
            return "Access Denied. Invalid Key."
    return render_template('keyaccesspage.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    # Controlla se l'accesso è stato concesso
    if 'access_granted' not in session:
        return redirect('/keyaccesspage')
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT username, email, password FROM UTENTE WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user'] = user['username']
            session['email'] = user['email']  # Aggiungi email alla sessione
            print(f"Login riuscito per utente: {username}")
            return redirect('/trade_input')
        else:
            print(f"Login fallito per utente: {username}")
            return "Username o password errati"

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Controlla se l'accesso è stato concesso
    if 'access_granted' not in session:
        return redirect('/keyaccesspage')
        
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO UTENTE (username, email, password) VALUES (?, ?, ?)", 
                      (username, email, password))
            conn.commit()
            print(f"Utente registrato: {username}")
            
            # Dopo la registrazione, imposta la sessione
            session['user'] = username
            session['email'] = email
            
        except sqlite3.IntegrityError as e:
            conn.close()
            print(f"Errore registrazione: {e}")
            return "Username o email già usati"
        finally:
            conn.close()

        return redirect('/trade_input')

    return render_template('register.html')

@app.route('/intro', methods=['GET', 'POST'])
def intro():
    if 'access_granted' not in session:
        return redirect('/keyaccesspage')
    return render_template('intro.html')

@app.route('/trade_input', methods=['GET', 'POST'])
def trade_input():
    if 'user' not in session:
        return redirect('/login')
    
    if 'access_granted' not in session:
        return redirect('/keyaccesspage')

    if request.method == 'POST':
        username = session['user']  # Usa username invece di email
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
                    usernameN, entry_price, exit_price, entry_timestamp, exit_timestamp,
                    account_size, fraction_invested, notes, asset_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                username, entry_price, exit_price, entry_timestamp, exit_timestamp,
                account_size, fraction_invested, notes, asset_type
            ))
            conn.commit()
            print(f"Trade salvato per utente: {username}")
        except sqlite3.IntegrityError as e:
            conn.close()
            print(f"Errore salvataggio trade: {e}")
            return f'Error in saving: {e}'
        finally:
            conn.close()
        return 'Data successfully saved!'

    return render_template('trade_input.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/keyaccesspage')

# Funzione per visualizzare le notifiche (opzionale)
@app.route('/view_notifications')
def view_notifications():
    if 'user' not in session:
        return redirect('/login')
    
    username = session['user']
    conn = get_db_connection()
    notifications = conn.execute(
        'SELECT * FROM NOTIFICA WHERE usernameN = ? ORDER BY entry_timestamp DESC',
        (username,)
    ).fetchall()
    conn.close()
    
    return render_template('notifications.html', notifications=notifications)

# Route per debug del database
@app.route('/debug_db')
def debug_db():
    debug_database()
    return "Check console for database info"

if __name__ == '__main__':
    app.run(debug=True)
