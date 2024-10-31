
# Zentrix Stock Signals

## Overview
The Zentrix Stock Signals bot is an advanced trading signals platform that leverages AI and machine learning to generate stock trading alerts. It operates by analyzing price movements, generating predictions, and sending alerts through Discord. The system includes functionality for managing trades, sending periodic updates, and applying machine learning models for predictive analysis.

## Features
- **Discord Integration**: Sends alerts for trade updates, stop loss hits, take profits, and invalidated trades to a specified Discord channel.
- **Trade Signal Management**: Manages open and closed trades with signals for LONG and SHORT positions.
- **Database Integration**: Stores and updates trade signals in a SQL database.
- **ML Model Prediction**: Uses machine learning to predict potential trade entries.
- **WebSocket Client**: Connects to Polygon.io for live price updates to generate real-time signals.

## Structure
- **main.py**: Initializes and manages the bot, including Discord and WebSocket connections. It also coordinates the message handling and signal checking processes.
- **check_signals.py**: Contains logic for validating and updating the status of trade signals based on real-time market data.
- **database.py**: Handles database interactions for creating tables, saving signals, and updating trade statuses.
- **ml_layer.py**: Contains the ML model and preprocessing steps for making trade predictions.

## Dependencies
- `discord.py`: Python library for integrating with Discord.
- `pyodbc`: For database connections.
- `pandas`: Data manipulation and analysis.
- `sklearn`: Machine learning model and data preprocessing.
- `imblearn`: For handling class imbalance with SMOTE.
- `joblib`: Saving and loading the ML model.
- `asyncio`: Asynchronous programming support.

## Installation
1. Clone the repository:
    ```bash
    git clone https://github.com/mrknor/Zentrix-Backend-Public.git
    ```
2. Install required packages:
    ```bash
    pip install -r requirements.txt
    ```
3. Set up the SQL database by configuring your connection in `database.py`.

## Usage
1. **Run main.py**:
    ```bash
    python main.py
    ```
2. The bot will automatically connect to Discord and Polygon.io, sending trade alerts based on market data.

## Configuration
- **Secrets**: Set up your credentials and API keys in the `Secret` class to ensure secure access to external services.
- **Database**: Customize `connection_string` in `database.py` to match your SQL server.

## Model Training
- To retrain the model, use the functions in `ml_layer.py` to fetch, preprocess, and train on updated data. The trained model can be saved and loaded using `joblib`.

## License
This project is licensed under the MIT License.

## Author
Connor
