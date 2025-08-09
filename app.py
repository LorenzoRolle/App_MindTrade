# Aggiungi queste modifiche al tuo app.py

# Aggiorna la route bias_analysis per usare il template corretto
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

# Aggiorna format_trade_for_algorithm per gestire meglio i dati
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

# Aggiorna la route trade_input per gestire il nuovo template
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