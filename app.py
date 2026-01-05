import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. SETTING UI ---
st.set_page_config(page_title="MACD Signal Dashboard", layout="wide")
st.title("📈 MACD Trading Signal System")
st.write("ระบบวิเคราะห์สัญญาณซื้อ-ขายหุ้นอัตโนมัติด้วย MACD Strategy")

# --- 2. SIDEBAR CONFIGURATION ---
st.sidebar.header("การตั้งค่าพารามิเตอร์")
symbol = st.sidebar.text_input("ระบุชื่อหุ้น (Ticker)", value="AAPL")
start_date = st.sidebar.date_input("วันที่เริ่มต้น", value=pd.to_datetime("2025-01-01"))
end_date = st.sidebar.date_input("วันที่สิ้นสุด", value=pd.to_datetime("today"))

st.sidebar.subheader("MACD Settings")
fast_ema = st.sidebar.number_input("Fast EMA", value=12)
slow_ema = st.sidebar.number_input("Slow EMA", value=26)
signal_ema = st.sidebar.number_input("Signal Line", value=9)

# --- 3. DATA FETCHING & CALCULATION ---
@st.cache_data # เก็บ Cache ข้อมูลเพื่อลดการโหลดซ้ำ
def load_data(ticker, start, end):
    df = yf.download(ticker, start=start, end=end)
    return df

try:
    df = load_data(symbol, start_date, end_date)
    
    if not df.empty:
        # คำนวณ MACD โดยใช้ pandas_ta
        macd = ta.macd(df['Close'], fast=fast_ema, slow=slow_ema, signal=signal_ema)
        df = pd.concat([df, macd], axis=1)

        # สร้าง Logic สำหรับ Buy/Sell Signal
        # Buy: MACD ตัด Signal Line ขึ้น
        df['Buy_Signal'] = (df[f'MACD_{fast_ema}_{slow_ema}_{signal_ema}'] > df[f'MACDs_{fast_ema}_{slow_ema}_{signal_ema}']) & \
                           (df[f'MACD_{fast_ema}_{slow_ema}_{signal_ema}'].shift(1) <= df[f'MACDs_{fast_ema}_{slow_ema}_{signal_ema}'].shift(1))
        
        # Sell: MACD ตัด Signal Line ลง
        df['Sell_Signal'] = (df[f'MACD_{fast_ema}_{slow_ema}_{signal_ema}'] < df[f'MACDs_{fast_ema}_{slow_ema}_{signal_ema}']) & \
                            (df[f'MACD_{fast_ema}_{slow_ema}_{signal_ema}'].shift(1) >= df[f'MACDs_{fast_ema}_{slow_ema}_{signal_ema}'].shift(1))

        # --- 4. VISUALIZATION ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.1, row_heights=[0.7, 0.3])

        # กราฟราคา (Candlestick)
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                     low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)

        # จุดสัญญาณซื้อ (ลูกศรสีเขียว)
        fig.add_trace(go.Scatter(x=df[df['Buy_Signal']].index, y=df['Close'][df['Buy_Signal']],
                                 mode='markers', marker=dict(symbol='triangle-up', size=12, color='green'),
                                 name='Buy Signal'), row=1, col=1)

        # จุดสัญญาณขาย (ลูกศรสีแดง)
        fig.add_trace(go.Scatter(x=df[df['Sell_Signal']].index, y=df['Close'][df['Sell_Signal']],
                                 mode='markers', marker=dict(symbol='triangle-down', size=12, color='red'),
                                 name='Sell Signal'), row=1, col=1)

        # กราฟ MACD & Signal Line
        fig.add_trace(go.Scatter(x=df.index, y=df[f'MACD_{fast_ema}_{slow_ema}_{signal_ema}'], 
                                 line=dict(color='blue', width=2), name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[f'MACDs_{fast_ema}_{slow_ema}_{signal_ema}'], 
                                 line=dict(color='orange', width=2), name='Signal Line'), row=2, col=1)
        
        # Histogram
        colors = ['red' if val < 0 else 'green' for val in df[f'MACDh_{fast_ema}_{slow_ema}_{signal_ema}']]
        fig.add_trace(go.Bar(x=df.index, y=df[f'MACDh_{fast_ema}_{slow_ema}_{signal_ema}'], 
                             marker_color=colors, name='Histogram'), row=2, col=1)

        fig.update_layout(height=800, xaxis_rangeslider_visible=False, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

        # --- 5. SIGNAL SUMMARY TABLE ---
        st.subheader("📋 สรุปสัญญาณล่าสุด")
        latest_signals = df[(df['Buy_Signal']) | (df['Sell_Signal'])].tail(5)
        if not latest_signals.empty:
            # ปรับแต่งการแสดงผลตาราง
            summary = latest_signals[['Close', 'Buy_Signal']].copy()
            summary['Action'] = summary['Buy_Signal'].apply(lambda x: "🟢 BUY" if x else "🔴 SELL")
            st.table(summary[['Close', 'Action']].sort_index(ascending=False))
        else:
            st.info("ไม่พบสัญญาณในช่วงเวลาที่เลือก")

    else:
        st.error("ไม่พบข้อมูลหุ้นที่คุณระบุ กรุณาตรวจสอบ Ticker อีกครั้ง")

except Exception as e:
    st.warning(f"กรุณากรอก Ticker ให้ถูกต้อง (เช่น AAPL, BTC-USD หรือ PTT.BK): {e}")
