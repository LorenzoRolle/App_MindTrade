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
            
            # Crea tabella NOTIFICA con i nuovi campi
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
                    trade_reason TEXT,
                    asset_name VARCHAR(255),
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
            # Verifica se esistono i nuovi campi e aggiungili se necessario
            cursor.execute("PRAGMA table_info(NOTIFICA)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'trade_reason' not in columns:
                cursor.execute("ALTER TABLE NOTIFICA ADD COLUMN trade_reason TEXT")
                print("Colonna trade_reason aggiunta.")
                
            if 'asset_name' not in columns:
                cursor.execute("ALTER TABLE NOTIFICA ADD COLUMN asset_name VARCHAR(255)")
                print("Colonna asset_name aggiunta.")
                
            conn.commit()
            
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

def format_trade_for_algorithm(trade_row):
    """Converte una riga del database nel formato richiesto dall'algoritmo"""
    entry_price = float(trade_row['entry_price'])
    exit_price = float(trade_row['exit_price'])
    account_size = float(trade_row['account_size'])
    fraction_invested = float(trade_row['fraction_invested'])
    
    # Calcola PnL corretto
    position_size = account_size * fraction_invested
    shares = position_size / entry_price
    pnl = shares * (exit_price - entry_price)
    
    return {
        'id': trade_row['id'],
        'entry_time': trade_row['entry_timestamp'],
        'exit_time': trade_row['exit_timestamp'],
        'entry_price': entry_price,
        'exit_price': exit_price,
        'pnl': pnl,
        'fraction_invested': fraction_invested,
        'notes': trade_row['notes'] or '',
        'asset_type': trade_row['asset_type'] or '',
        'direction': 'long' if exit_price > entry_price else 'short',
        'trade_reason': trade_row.get('trade_reason', '') or '',
        'asset_name': trade_row.get('asset_name', '') or '',
        'account_size': account_size,
        'size': position_size  # Aggiunto per l'algoritmo
    }

def detect_all_biases(trades_formatted):
    """Placeholder per l'algoritmo di analisi dei bias - da implementare"""
    # Qui dovrai aggiungere la tua logica di analisi dei bias
    # Per ora restituisco un esempio di struttura
    return {
        'total_trades': len(trades_formatted),
        'bias_detected': ['confirmation_bias', 'loss_aversion'],
        'analysis': 'Analysis results will go here...'
    }

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
        username = session['user']
        
        # Raccogli i dati dal form
        trade_data = {
            'asset_name': request.form.get('asset_name', ''),
            'asset_type': request.form.get('asset_type', ''),
            'entry_price': request.form['entry_price'],
            'exit_price': request.form['exit_price'],
            'entry_timestamp': request.form['entry_timestamp'],
            'exit_timestamp': request.form['exit_timestamp'],
            'account_size': request.form['account_size'],
            'fraction_invested': request.form['fraction_invested'],
            'notes': request.form.get('notes', ''),
            'trade_reason': request.form.get('trade_reason', '')
        }

        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO NOTIFICA (
                    usernameN, entry_price, exit_price, entry_timestamp, exit_timestamp,
                    account_size, fraction_invested, notes, asset_type, trade_reason, asset_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                username, 
                trade_data['entry_price'], 
                trade_data['exit_price'], 
                trade_data['entry_timestamp'], 
                trade_data['exit_timestamp'],
                trade_data['account_size'], 
                trade_data['fraction_invested'], 
                trade_data['notes'], 
                trade_data['asset_type'],
                trade_data['trade_reason'], 
                trade_data['asset_name']
            ))
            conn.commit()
            print(f"Trade salvato per utente: {username}")
            
            # Reindirizza all'analisi dopo aver salvato
            return redirect('/bias_analysis')
            
        except sqlite3.Error as e:
            print(f"Errore salvataggio trade: {e}")
            return f'Error saving trade: {e}'
        finally:
            conn.close()

    return render_template('trade_input.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/keyaccesspage')

@app.route('/bias_analysis')
def bias_analysis():
    """Route per l'analisi dei bias usando il nuovo template"""
    if 'user' not in session:
        return redirect('/login')
    
    username = session['user']
    conn = get_db_connection()
    
    # Recupera tutti i trade dell'utente
    trades_raw = conn.execute('''
        SELECT * FROM NOTIFICA 
        WHERE usernameN = ? 
        ORDER BY entry_timestamp ASC
    ''', (username,)).fetchall()
    conn.close()
    
    if not trades_raw:
        return render_template('bias_analysis.html', 
                             message="No trades found. Enter at least one trade to get your psychological analysis.",
                             bias_results=None,
                             total_trades=0)
    
    # Converti i trade nel formato richiesto dall'algoritmo
    trades_formatted = []
    for trade in trades_raw:
        trade_dict = format_trade_for_algorithm(trade)
        trades_formatted.append(trade_dict)
    
    # Esegui l'analisi dei bias
    bias_results = detect_all_biases(trades_formatted)
    
    return render_template('bias_analysis.html', 
                         bias_results=bias_results,
                         total_trades=len(trades_formatted))

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

# Aggiungi una route per test rapidi
@app.route('/debug_trades')
def debug_trades():
    """Route di debug per vedere i trade formattati"""
    if 'user' not in session:
        return redirect('/login')
    
    username = session['user']
    conn = get_db_connection()
    
    trades_raw = conn.execute('''
        SELECT * FROM NOTIFICA 
        WHERE usernameN = ? 
        ORDER BY entry_timestamp ASC
    ''', (username,)).fetchall()
    conn.close()
    
    trades_formatted = [format_trade_for_algorithm(trade) for trade in trades_raw]
    
    return f"<pre>{trades_formatted}</pre>"

if __name__ == '__main__':
    app.run(debug=True)
