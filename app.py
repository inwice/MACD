import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. SETTING UI ---
st.set_page_config(page_title="Safe Rule-Based System", layout="wide")
st.title("🎯 Strict Strategy: MACD + RSI + S/R + Patterns")

# --- 2. SIDEBAR CONFIGURATION ---
st.sidebar.header("⚙️ System Config")
symbol = st.sidebar.text_input("Ticker Symbol", value="BTC-USD").upper()
days_back = st.sidebar.slider("Lookback Period (Days)", 60, 1000, 365)

with st.sidebar.expander("Strategy Thresholds"):
    rsi_low = st.sidebar.slider("RSI Buy Zone (Lower than)", 10, 50, 40)
    rsi_high = st.sidebar.slider("RSI Sell Zone (Higher than)", 50, 90, 65)
    sr_window = st.sidebar.slider("S/R Lookback Window", 10, 50, 20)

# --- 3. DATA FETCHING ---
@st.cache_data
def get_data(ticker, days):
    try:
        start = datetime.now() - timedelta(days=days)
        # ใช้ multi_level_index=False เพื่อป้องกันปัญหา Column ซ้อนกันใน yfinance รุ่นใหม่
        data = yf.download(ticker, start=start, multi_level_index=False)
        if data.empty:
            return None
        return data
    except:
        return None

try:
    df = get_data(symbol, days_back)

    if df is not None and len(df) > sr_window:
        # --- CALCULATIONS ---
        
        # 1. MACD (ตรวจสอบ None)
        macd = ta.macd(df['Close'])
        if macd is not None:
            df = pd.concat([df, macd], axis=1)
            m_line = macd.columns[0]
            m_hist = macd.columns[1]
            m_signal = macd.columns[2]
        else:
            st.error("ไม่สามารถคำนวณ MACD ได้ ข้อมูลอาจไม่เพียงพอ")
            st.stop()

        # 2. RSI & Trend
        rsi_series = ta.rsi(df['Close'], length=14)
        if rsi_series is not None:
            df['RSI'] = rsi_series
            df['RSI_Up'] = df['RSI'] > df['RSI'].shift(1)
        else:
            st.error("ไม่สามารถคำนวณ RSI ได้")
            st.stop()

        # 3. Support & Resistance
        df['Support'] = df['Low'].rolling(window=sr_window).min()
        df['Resistance'] = df['High'].rolling(window=sr_window).max()

        # 4. Candlestick Patterns (จุดที่มักเกิด Error)
        # แก้ไขโดยการเช็ค None ก่อน Subscript
        patterns = ta.cdl_pattern(df['Open'], df['High'], df['Low'], df['Close'], name="engulfing")
        if patterns is not None and 'CDL_ENGULFING' in patterns.columns:
            df['Bullish_Engulfing'] = patterns['CDL_ENGULFING'] > 0
            df['Bearish_Engulfing'] = patterns['CDL_ENGULFING'] < 0
        else:
            # ถ้าหาไม่เจอหรือ Error ให้กำหนดเป็น False ทั้งหมด
            df['Bullish_Engulfing'] = False
            df['Bearish_Engulfing'] = False

        # --- 4. STRICT DECISION LOGIC ---
        # BUY ENTRY
        cond_buy_price = df['Low'] <= (df['Support'] * 1.02)
        cond_buy_rsi = (df['RSI'] < rsi_low) & (df['RSI_Up'])
        cond_buy_macd = (df[m_line] > df[m_signal]) & (df[m_line].shift(1) <= df[m_signal].shift(1))
        df['Final_Buy'] = cond_buy_price & cond_buy_rsi & cond_buy_macd

        # SELL EXIT
        cond_sell_price = df['High'] >= (df['Resistance'] * 0.98)
        cond_sell_rsi = df['RSI'] > rsi_high
        cond_sell_macd = (df[m_line] < df[m_signal]) & (df[m_line].shift(1) >= df[m_signal].shift(1))
        df['Final_Sell'] = cond_sell_price & cond_sell_rsi & cond_sell_macd

        # --- 5. VISUALIZATION ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.25, 0.25])

        # Price Chart
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Support'], line=dict(color='green', dash='dot', width=1), name='Support'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Resistance'], line=dict(color='red', dash='dot', width=1), name='Resistance'), row=1, col=1)
        
        # Buy/Sell Markers
        if df['Final_Buy'].any():
            fig.add_trace(go.Scatter(x=df[df['Final_Buy']].index, y=df['Low'][df['Final_Buy']] * 0.98, mode='markers', marker=dict(symbol='triangle-up', size=15, color='#00FF00'), name='ENTRY'), row=1, col=1)
        if df['Final_Sell'].any():
            fig.add_trace(go.Scatter(x=df[df['Final_Sell']].index, y=df['High'][df['Final_Sell']] * 1.02, mode='markers', marker=dict(symbol='triangle-down', size=15, color='#FF0000'), name='EXIT'), row=1, col=1)

        # MACD
        fig.add_trace(go.Scatter(x=df.index, y=df[m_line], line=dict(color='cyan'), name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[m_signal], line=dict(color='orange'), name='Signal'), row=2, col=1)

        # RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name='RSI'), row=3, col=1)
        fig.add_hline(y=rsi_high, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=rsi_low, line_dash="dash", line_color="green", row=3, col=1)

        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- 6. DASHBOARD ---
        st.subheader("📋 Strategy Checklist (Latest Bar)")
        last_row = df.iloc[-1]
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 🟢 Buy Entry Check")
            st.checkbox("Price near Support", value=bool(cond_buy_price.iloc[-1]), disabled=True)
            st.checkbox("RSI Oversold/Reversing", value=bool(cond_buy_rsi.iloc[-1]), disabled=True)
            st.checkbox("MACD Golden Cross", value=bool(cond_buy_macd.iloc[-1]), disabled=True)

        with c2:
            st.write("### 🔴 Sell Exit Check")
            st.checkbox("Price near Resistance", value=bool(cond_sell_price.iloc[-1]), disabled=True)
            st.checkbox("RSI Overbought", value=bool(cond_sell_rsi.iloc[-1]), disabled=True)
            st.checkbox("MACD Dead Cross", value=bool(cond_sell_macd.iloc[-1]), disabled=True)

    else:
        st.warning("ไม่พบข้อมูล หรือข้อมูลน้อยเกินไปสำหรับการคำนวณ (ต้องใช้อย่างน้อย 30 แท่ง)")

except Exception as e:
    st.error(f"เกิดข้อผิดพลาด: {e}")
