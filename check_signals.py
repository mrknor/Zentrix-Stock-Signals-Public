import asyncio
from datetime import datetime
from pytz import timezone
from database import fetch_open_signals, update_signal, update_signal_stop_loss, save_message
from secret import Secret
import discord

utc = timezone('UTC')
central = timezone('US/Eastern')

async def init_globals(bot):
    global channel, utc_dt, central_dt, timestamp
    channel = bot.get_channel(Secret.signal_channel_id)
    utc_dt = datetime.now(utc)
    central_dt = utc_dt.astimezone(central)
    timestamp = central_dt.strftime('%Y-%m-%d %H:%M:%S')

async def check_and_update_signals(bot, candle):
    await init_globals(bot)  # Initialize global variables

    signals = fetch_open_signals()
    latest_price = candle.close  # Assuming the close price is in the 'c' key
    timestamp = candle.end_timestamp  # Assuming the timestamp is in the 't' key

    for signal in signals:
        if signal.is_open:
            risk = abs(signal.entry_point - signal.stop_loss)
            if signal.signal_type == 'LONG':
                if candle.low <= signal.stop_loss:
                    signal.total_profit = round(signal.stop_loss - signal.entry_point, 2)
                    await send_stoploss_hit_message(signal)
                    update_signal(signal.id, signal.total_profit, is_open=False, invalidated=1, timestamp=timestamp)

                elif latest_price >= signal.take_profit:
                    signal.total_profit = round(signal.take_profit - signal.entry_point, 2)
                    await send_take_profit_hit_message(signal)
                    update_signal(signal.id, signal.total_profit, is_open=False, invalidated=1, timestamp=timestamp)

                elif latest_price - signal.entry_point >= risk:
                    signal.stop_loss = signal.entry_point  # Move stop loss to break even
                    update_signal_stop_loss(signal.id, signal.entry_point, timestamp)
            elif signal.signal_type == 'SHORT':
                if candle.high >= signal.stop_loss:
                    signal.total_profit = round(signal.entry_point - signal.stop_loss, 2)
                    await send_stoploss_hit_message(signal)
                    update_signal(signal.id, signal.total_profit, is_open=False, invalidated=1, timestamp=timestamp)

                elif latest_price <= signal.take_profit:
                    signal.total_profit = round(signal.entry_point - signal.take_profit, 2)
                    await send_take_profit_hit_message(signal)
                    update_signal(signal.id, signal.total_profit, is_open=False, invalidated=1, timestamp=timestamp)

                elif signal.entry_point - latest_price >= risk:
                    signal.stop_loss = signal.entry_point  # Move stop loss to break even
                    update_signal_stop_loss(signal.id, signal.entry_point, timestamp)
        else:
            if signal.signal_type == 'LONG':
                if candle.high >= signal.invalidated_price:
                    await send_invalidated_message(signal)
                    update_signal(signal.id, signal.total_profit, is_open=False, invalidated=1, timestamp=timestamp)
                elif latest_price >= signal.entry_point:
                    update_signal(signal.id, signal.total_profit, is_open=True, invalidated=0, timestamp=timestamp, entry_point=latest_price)
            elif signal.signal_type == 'SHORT':
                if candle.low <= signal.invalidated_price:
                    await send_invalidated_message(signal)
                    update_signal(signal.id, signal.total_profit, is_open=False, invalidated=1, timestamp=timestamp)
                elif latest_price <= signal.entry_point:
                    update_signal(signal.id, signal.total_profit, is_open=True, invalidated=0, timestamp=timestamp, entry_point=latest_price)

async def send_stoploss_hit_message(signal):
    message = f"STOPLOSS HIT [{signal.symbol}] at {signal.stop_loss} for total loss of {signal.total_profit:.2f} | {timestamp}"
    await channel.send(message)
    save_message(message)

async def send_filled_message(signal):
    message = f"FILLED {signal.signal_type} [{signal.symbol}] at {signal.entry_point} | {timestamp}"
    await channel.send(message)
    save_message(message)

async def send_invalidated_message(signal):
    message = f"INVALIDATED {signal.signal_type} [{signal.symbol}] at {signal.invalidated_price} | {timestamp}"
    await channel.send(message)
    save_message(message)

async def send_take_profit_hit_message(signal):
    message = f"TAKE PROFIT HIT [{signal.symbol}] at {signal.take_profit} for a total profit of {signal.total_profit:.2f} | {timestamp}"
    await channel.send(message)
    save_message(message)

async def send_six_minute_update(bot, latest_price):
    await init_globals(bot)  # Initialize global variables

    signals = fetch_open_signals()
    for signal in signals:
        pl = round((latest_price - signal.entry_point), 2) if signal.signal_type == 'LONG' else round((signal.entry_point - latest_price), 2)

        message = f"TRADE UPDATE [{signal.symbol}] {signal.signal_type} P/L: {pl:.2f} | {timestamp}"
        await channel.send(message)
        save_message(message)
