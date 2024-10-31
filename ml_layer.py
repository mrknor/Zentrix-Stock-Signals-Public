import pyodbc
import pandas as pd
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
from sklearn.impute import SimpleImputer
from imblearn.over_sampling import SMOTE
from secret import Secret
import joblib

model = joblib.load('trained_model.pkl')

# Database connection
connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={Secret.server};DATABASE={Secret.database};UID={Secret.username};PWD={Secret.password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'

def create_connection():
    return pyodbc.connect(connection_string)

# Fetch trade signals with the specified conditions
def fetch_trade_signals():
    query = """
    SELECT [id], [symbol], [created_at], [total_profit]
    FROM [trade_signals]
    WHERE volume_confirmed = 0 AND confidence = 1
    """
    with create_connection() as conn:
        df = pd.read_sql(query, conn)
    return df

# Fetch candlestick data
def fetch_candlestick_data():
    query = """
    SELECT [symbol], [timestamp], [open], [high], [low], [close], [volume]
    FROM [candlestick_data]
    """
    with create_connection() as conn:
        df = pd.read_sql(query, conn)
    return df

# Merge data and prepare it for model training
def merge_data(trade_signals, candlestick_data):
    trade_signals['created_at'] = pd.to_datetime(trade_signals['created_at'])
    candlestick_data['timestamp'] = pd.to_datetime(candlestick_data['timestamp'])

    merged_data = []

    for _, trade in trade_signals.iterrows():
        relevant_candles = candlestick_data[(candlestick_data['symbol'] == trade['symbol']) &
                                            (candlestick_data['timestamp'] < trade['created_at'])].tail(6)
        if len(relevant_candles) == 6:
            for _, candle in relevant_candles.iterrows():
                merged_data.append({
                    'open': candle['open'],
                    'high': candle['high'],
                    'low': candle['low'],
                    'close': candle['close'],
                    'volume': candle['volume'],
                    'total_profit': trade['total_profit']
                })
    
    return pd.DataFrame(merged_data)

# Prepare data for training
def prepare_data(df):
    # Features and target variable
    features = df[['open', 'high', 'low', 'close', 'volume']]
    target = df['total_profit'].apply(lambda x: 1 if x > 0 else 0)  # 1 for profit, 0 for loss
    
    return features, target

# Predict trade signal using the trained model
def predict_trade_signal(candle):
    features = pd.DataFrame([[
        candle['o'],
        candle['h'],
        candle['l'],
        candle['c'],
        candle['v']
    ]], columns=['open', 'high', 'low', 'close', 'volume'])
    
    prediction = model.predict(features)[0]
    return prediction

if __name__ == "__main__":
    # Fetch and merge data
    trade_signals = fetch_trade_signals()
    candlestick_data = fetch_candlestick_data()
    merged_data = merge_data(trade_signals, candlestick_data)

    # Handle missing values
    features = merged_data[['open', 'high', 'low', 'close', 'volume']]
    target = merged_data['total_profit']
    imputer = SimpleImputer(strategy='mean')
    features_imputed = imputer.fit_transform(features)

    # Prepare data
    X, y = prepare_data(pd.concat([pd.DataFrame(features_imputed, columns=features.columns), target.reset_index(drop=True)], axis=1))

    # Handle class imbalance with SMOTE
    smote = SMOTE(random_state=42)
    X_res, y_res = smote.fit_resample(X, y)

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X_res, y_res, test_size=0.2, random_state=42)

    # Train model with cross-validation
    model = RandomForestClassifier(n_estimators=100, random_state=42)

    # Perform cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=5)
    print(f"Cross-validation scores: {cv_scores}")
    print(f"Average cross-validation score: {cv_scores.mean()}")

    # Train model on full training data
    model.fit(X_train, y_train)

    # Save model
    joblib.dump(model, 'trained_model.pkl')
    print("Model saved to trained_model.pkl")

    # Evaluate model
    y_pred = model.predict(X_test)
    print("Accuracy:", accuracy_score(y_test, y_pred))
    print(classification_report(y_test, y_pred))