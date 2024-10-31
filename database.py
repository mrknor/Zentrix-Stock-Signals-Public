import pyodbc
from datetime import datetime
from pytz import timezone
from secret import Secret

connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={Secret.server};DATABASE={Secret.database};UID={Secret.username};PWD={Secret.password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
def create_connection():
    return pyodbc.connect(connection_string)

def create_table():
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='trade_signals' AND xtype='U')
            CREATE TABLE trade_signals (
                id INT PRIMARY KEY IDENTITY(1,1),
                symbol NVARCHAR(50) NOT NULL,
                signal_type NVARCHAR(10) NOT NULL,
                entry_point FLOAT NOT NULL,
                stop_loss FLOAT NOT NULL,
                invalidated_price FLOAT,
                take_profit FLOAT,
                sentiment FLOAT,
                is_open BIT DEFAULT 0,
                invalidated BIT DEFAULT 0,
                volume_confirmed BIT DEFAULT 0,
                total_profit FLOAT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                confidence NVARCHAR(10)
            );
        ''')
        conn.commit()

def save_signal(symbol, signal_type, entry_point, stop_loss, invalidated_price, sentiment, volume_confirmed, timestamp, confidence):
    create_table()  # Ensure the table exists
    
    # Convert volume_confirmed to standard Python bool
    volume_confirmed = bool(volume_confirmed)
    
    # Convert the integer timestamp to a datetime object
    try:
        utc_dt = datetime.fromtimestamp(timestamp / 1000, timezone('UTC'))  # Assuming timestamp is in milliseconds
        est_time = utc_dt.astimezone(timezone('US/Eastern'))
    except (OSError, OverflowError, ValueError):
        print(f"Invalid timestamp: {timestamp}")
        return
    
    # Convert confidence to string
    confidence = str(confidence)
    
    # Calculate the profit target (PT), which is 3 times the risk
    risk = abs(entry_point - stop_loss)
    if risk < 0.05:
        risk = 0.05
    take_profit = entry_point + 3 * risk if signal_type == 'LONG' else entry_point - 3 * risk
    
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trade_signals (symbol, signal_type, entry_point, stop_loss, invalidated_price, take_profit, sentiment, volume_confirmed, created_at, updated_at, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, signal_type, float(entry_point), float(stop_loss), float(invalidated_price), float(take_profit), float(sentiment) if sentiment is not None else None, volume_confirmed, est_time, est_time, confidence))
        conn.commit()

def update_signal_stop_loss(signal_id, new_stop_loss, timestamp):
    # Convert the integer timestamp to a datetime object
    try:
        utc_dt = datetime.fromtimestamp(timestamp / 1000, timezone('UTC'))  # Assuming timestamp is in milliseconds
        est_time = utc_dt.astimezone(timezone('US/Eastern'))
    except (OSError, OverflowError, ValueError):
        print(f"Invalid timestamp: {timestamp}")
        return
    
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE trade_signals
            SET stop_loss = ?, updated_at = ?
            WHERE id = ?
        ''', (float(new_stop_loss), est_time, signal_id))
        conn.commit()

def update_signal(signal_id, total_profit, is_open, invalidated, timestamp, entry_point=None):
    # Convert timestamp to CST

    utc_dt = datetime.fromtimestamp(timestamp / 1000, timezone('UTC'))  # Assuming timestamp is in milliseconds
    cst_time = utc_dt.astimezone(timezone('US/Eastern'))
    
    with create_connection() as conn:
        cursor = conn.cursor()
        if entry_point is not None:
            cursor.execute('''
                UPDATE trade_signals
                SET total_profit = ?, is_open = ?, invalidated = ?, updated_at = ?, entry_point = ?
                WHERE id = ?
            ''', (total_profit, is_open, invalidated, cst_time, entry_point, signal_id))
        else:
            cursor.execute('''
                UPDATE trade_signals
                SET total_profit = ?, is_open = ?, invalidated = ?, updated_at = ?
                WHERE id = ?
            ''', (total_profit, is_open, invalidated, cst_time, signal_id))
        conn.commit()

def fetch_open_signals():
    create_table() 
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM trade_signals WHERE invalidated = 0')
        return cursor.fetchall()

def save_message(message):
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO signal_messages (message)
            VALUES (?)
        ''', (message,))
        conn.commit()
