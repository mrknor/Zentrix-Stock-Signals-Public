import joblib
import pandas as pd
from datetime import datetime
from discord.ext import commands
import discord
import asyncio
from polygon import WebSocketClient
from polygon.websocket.models import WebSocketMessage
from typing import List
from pytz import timezone
from database import save_signal, fetch_open_signals, save_message
from check_signals import check_and_update_signals
from secret import Secret

# Load the trained model
model = joblib.load('VERY_GOOD_MODEL.pkl')

# Discord bot setup
intents = discord.Intents.default()
intents.messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

# WebSocket client setup
client = WebSocketClient("KEY")  # replace with your actual API key
client.subscribe("AM.SPY")

# Global variables for candle aggregation
CANDLE_SIZES = [6]
aggregate_data = {size: {} for size in CANDLE_SIZES}
last_data_points = {}


async def handle_msg(msgs: List[WebSocketMessage]):
    global last_data_points, aggregate_data

    for equity_agg in msgs:
        ticker = equity_agg.symbol

        for size in CANDLE_SIZES:
            if ticker not in aggregate_data[size]:
                aggregate_data[size][ticker] = []

            aggregate_data[size][ticker].append(equity_agg)

            if len(aggregate_data[size][ticker]) == size:
                aggregated_candle = aggregate_candles(aggregate_data[size][ticker])
                print(f"Aggregated candle for size {size}: {aggregated_candle}")

                aggregate_data[size][ticker] = []  # Reset after aggregation

                if ticker in last_data_points and size in last_data_points[ticker]:
                    previous_candle = last_data_points[ticker][size]
                    previous_volume = previous_candle['v']
                    current_volume = aggregated_candle['v']
                    volume_confirmed = current_volume > previous_volume

                    # Get prediction confidence
                    confidence = predict_trade_signal_with_model(aggregated_candle)
                    print(f"Trade signal confidence: {confidence}")

                    if confidence is None:
                        continue
                    confidence = 1
                    # Analysis logic
                    analysis_result_short = analyze_for_shorts(previous_candle, aggregated_candle, ticker)
                    analysis_result_long = analyze_for_longs(previous_candle, aggregated_candle, ticker)

                    if confidence == 1:

                        if analysis_result_short:
                            print(f"Short analysis result: {analysis_result_short}")
                            await send_discord_message(format_message_short(analysis_result_short, size, volume_confirmed))
                            save_signal(ticker, 'SHORT', analysis_result_short['entry_point'], analysis_result_short['stop_loss'], analysis_result_short['invalidated_price'], None, volume_confirmed, equity_agg.end_timestamp, confidence)

                        if analysis_result_long:
                            print(f"Long analysis result: {analysis_result_long}")
                            await send_discord_message(format_message_long(analysis_result_long, size, volume_confirmed))
                            save_signal(ticker, 'LONG', analysis_result_long['entry_point'], analysis_result_long['stop_loss'], analysis_result_long['invalidated_price'], None, volume_confirmed, equity_agg.end_timestamp, confidence)

                if ticker not in last_data_points:
                    last_data_points[ticker] = {}
                last_data_points[ticker][size] = aggregated_candle

        await check_and_update_signals(bot, equity_agg)

def predict_trade_signal_with_model(candle):
    features = pd.DataFrame([[
        candle['o'],
        candle['h'],
        candle['l'],
        candle['c'],
        candle['v']
    ]], columns=['open', 'high', 'low', 'close', 'volume'])
    
    prediction = model.predict(features)[0]
    return prediction

def aggregate_candles(candles):
    open_price = candles[0].open
    close_price = candles[-1].close
    high_price = max(candle.high for candle in candles)
    low_price = min(candle.low for candle in candles)
    volume = sum(candle.volume for candle in candles)
    timestamp = candles[-1].end_timestamp

    aggregated_candle = {
        'o': open_price,
        'c': close_price,
        'h': high_price,
        'l': low_price,
        'v': volume,
        't': timestamp
    }

    return aggregated_candle

def analyze_for_shorts(data_point_1, data_point_2, symbol):
    is_sender = False
    recent_candle = data_point_2
    prev_candle = data_point_1
    invalidated_price = None

    if recent_candle['h'] > prev_candle['h']:
        if recent_candle['c'] < recent_candle['o']:
            if recent_candle['c'] < prev_candle['c']:
                entry_point = recent_candle['o']
                invalidated_price = prev_candle['l']
                is_sender = True
            if recent_candle['l'] < prev_candle['l']:
                is_sender = False
        if recent_candle['c'] > recent_candle['o']:
            if recent_candle['c'] < prev_candle['c']:
                entry_point = recent_candle['c']
                invalidated_price = prev_candle['l']
                is_sender = True
            if recent_candle['l'] < prev_candle['l']:
                is_sender = False
    if is_sender:
        return {
            'ticker': symbol,
            'entry_point': entry_point,
            'stop_loss': recent_candle['h'],
            'invalidated_price': invalidated_price,
            'timestamp': recent_candle['t']
        }
    return None

def analyze_for_longs(data_point_1, data_point_2, symbol):
    is_sender = False
    recent_candle = data_point_2
    prev_candle = data_point_1
    invalidated_price = None

    if recent_candle['l'] < prev_candle['l']:
        if recent_candle['o'] < recent_candle['c']:
            if recent_candle['c'] < prev_candle['o']:
                entry_point = recent_candle['o']
                invalidated_price = prev_candle['h']
                is_sender = True
            if recent_candle['h'] > prev_candle['h']:
                is_sender = False
        if recent_candle['o'] > recent_candle['c']:
            if recent_candle['c'] > prev_candle['c']:
                entry_point = recent_candle['c']
                invalidated_price = prev_candle['h']
                is_sender = True
            if recent_candle['h'] > prev_candle['h']:
                is_sender = False
    if is_sender:
        return {
            'ticker': symbol,
            'entry_point': entry_point,
            'stop_loss': recent_candle['l'],
            'invalidated_price': invalidated_price,
            'timestamp': recent_candle['t']
        }
    return None

async def send_discord_message(message):
    await bot.get_channel(Secret.signal_channel_id).send(message)
    save_message(message)

def format_message_short(analysis_result, candle_size, volume):
    volume_text = "[VC]" if volume else ""
    utc_dt = datetime.fromtimestamp(analysis_result['timestamp'] / 1000, timezone('UTC'))
    central_dt = utc_dt.astimezone(timezone('US/Eastern'))
    timestamp = central_dt.strftime('%Y-%m-%d %H:%M:%S')
    return f"SHORT Alert: {analysis_result['ticker']}, Entry: {analysis_result['entry_point']}, Stop: {analysis_result['stop_loss']} | {timestamp}"

def format_message_long(analysis_result, candle_size, volume):
    volume_text = "[VC]" if volume else ""
    utc_dt = datetime.fromtimestamp(analysis_result['timestamp'] / 1000, timezone('UTC'))
    central_dt = utc_dt.astimezone(timezone('US/Eastern'))
    timestamp = central_dt.strftime('%Y-%m-%d %H:%M:%S')
    return f"LONG Alert: {analysis_result['ticker']}, Entry: {analysis_result['entry_point']}, Stop: {analysis_result['stop_loss']} | {timestamp}"

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    asyncio.create_task(start_client())

async def start_client():
    print(f"Starting WebSocket client at {datetime.now().time()}")

    await client.connect(handle_msg)

if __name__ == "__main__":
    bot.run(Secret.token)
