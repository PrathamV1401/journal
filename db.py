# db.py
import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text
import streamlit as st

# --- 1. ROBUST CONNECTION MANAGER ---
def get_engine():
    try:
        # Load the URL from secrets
        db_url = st.secrets["supabase"]["DB_URL"]
        return create_engine(db_url)
    except Exception as e:
        st.error(f"❌ Database Connection Error: {e}")
        st.stop()

engine = get_engine()

def run_query(query, params=None):
    with engine.connect() as conn:
        # text() ensures the query is treated safely
        result = conn.execute(text(query), params or {})
        conn.commit()
        return result

def init_db():
    """
    Self-Healing Database Setup.
    """
    # 1. Create Accounts Table
    run_query("""
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            username TEXT,
            name TEXT NOT NULL,
            account_type TEXT,
            initial_balance REAL,
            target_payout REAL,
            max_drawdown_limit REAL
        );
    """)
    
    # 2. Create Trades Table
    run_query("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            account_id INTEGER,
            symbol TEXT,
            direction TEXT,
            entry_date TIMESTAMP,
            quantity REAL,
            pnl REAL,
            status TEXT,
            session TEXT,
            rules_followed TEXT,
            trend TEXT,
            setup TEXT,
            proper_sl TEXT,
            is_event_day TEXT,
            notes TEXT,
            CONSTRAINT fk_account FOREIGN KEY(account_id) REFERENCES accounts(id)
        );
    """)

    # 3. MIGRATION CHECK (Add columns if missing)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='accounts' AND column_name='username';"))
        if res.rowcount == 0:
            conn.execute(text("ALTER TABLE accounts ADD COLUMN username TEXT;"))
            conn.commit()
        
        res_qty = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='trades' AND column_name='quantity';"))
        if res_qty.rowcount == 0:
            conn.execute(text("ALTER TABLE trades ADD COLUMN quantity REAL DEFAULT 0;"))
            conn.commit()

# --- DATA FUNCTIONS ---

def add_account(username, name, acc_type, balance, target, drawdown):
    run_query("""
        INSERT INTO accounts (username, name, account_type, initial_balance, target_payout, max_drawdown_limit)
        VALUES (:user, :name, :type, :bal, :target, :dd)
    """, {'user': username, 'name': name, 'type': acc_type, 'bal': balance, 'target': target, 'dd': drawdown})

def add_trade(account_id, symbol, direction, date, quantity, pnl, status, 
              session, rules, trend, setup, proper_sl, event_day, notes):
    run_query("""
        INSERT INTO trades (
            account_id, symbol, direction, entry_date, quantity, pnl, status, 
            session, rules_followed, trend, setup, proper_sl, is_event_day, notes
        )
        VALUES (:acc_id, :sym, :dir, :date, :qty, :pnl, :stat, 
                :sess, :rules, :trend, :setup, :sl, :evt, :note)
    """, {
        'acc_id': account_id, 'sym': symbol, 'dir': direction, 'date': date, 
        'qty': quantity, 'pnl': pnl, 'stat': status, 'sess': session, 
        'rules': rules, 'trend': trend, 'setup': setup, 'sl': proper_sl, 
        'evt': event_day, 'note': notes
    })

def delete_account(account_id):
    run_query("DELETE FROM trades WHERE account_id = :id", {'id': account_id})
    run_query("DELETE FROM accounts WHERE id = :id", {'id': account_id})

def get_accounts(username):
    # --- FIX IS HERE ---
    # We wrap the query string in text() so SQLAlchemy handles the parameter correctly
    query = text("SELECT * FROM accounts WHERE username = :user")
    
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={'user': username})

def get_trades(account_id=None):
    query_str = "SELECT * FROM trades"
    params = {}
    
    if account_id and account_id != "All Accounts":
        query_str += " WHERE account_id = :acc_id"
        params = {'acc_id': account_id}
    
    # --- FIX IS HERE TOO ---
    with engine.connect() as conn:
        df = pd.read_sql(text(query_str), conn, params=params)
    
    if not df.empty:
        df['entry_date'] = pd.to_datetime(df['entry_date'])
    return df