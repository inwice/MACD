import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. SETTING UI ---
st.set_page_config(page_title="Advanced Trading Scanner", layout="wide")
st.title("🛡️ Pro MACD & Momentum Analyzer")
st.markdown("ระบบวิเคราะห์ความแม่นยำสูง: MACD + RSI + Volume + Support/Resistance")

# --- 2. SIDEBAR CONFIGURATION ---
st.sidebar.header("🔍 Search & Settings")
symbol = st.sidebar.text_input("Ticker Symbol", value="BTC-USD").upper()
days_back = st.sidebar.slider("ดูย้อนหลัง (วัน)", 30, 730, 365)

with st.sidebar.expander("Technical Parameters"):
    rsi_period = st.number_input("RSI Period", value=14)
    vol_sma = st.number_input("Volume SMA Period", value=20)
    fast_ema = st.number_input("MACD Fast", value=12)
    slow_ema = st.number_input("MACD Slow", value=26)

# --- 3. DATA FETCHING & PROCESSING ---
@st.cache_data
def get_data(ticker, days):
    start = datetime.now() - timedelta(days=days)
    data = yf.download(ticker, start=start)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

try:
    df = get_data(symbol, days_back)

    if df is not None and len(df) > 30:
        # --- CALCULATIONS ---
        # 1. MACD
        macd_df = ta.macd(df['Close'], fast=fast_ema, slow=slow_ema)
        df = pd.concat([df, macd_df], axis=1)
        m_line = macd_df.columns[0]
        m_hist = macd_df.columns[1]
        m_signal = macd_df.columns[2]

        # 2. RSI
        df['RSI'] = ta.rsi(df['Close'], length=rsi_period)

        # 3. Volume SMA
        df['Vol_SMA'] = ta.sma(df['Volume'], length=vol_sma)

        # 4. Support/Resistance (Simple Pivot)
        res_level = df['High'].rolling(window=20).max().iloc[-1]
        sup_level = df['Low'].rolling(window=20).min().iloc[-1]

        # --- LOGIC: SIGNALS ---
        df['Buy_Signal'] = (df[m_line] > df[m_signal]) & (df[m_line].shift(1) <= df[m_signal].shift(1))
        df['Sell_Signal'] = (df[m_line] < df[m_signal]) & (df[m_line].shift(1) >= df[m_signal].shift(1))

        # --- 4. VISUALIZATION (3 Rows) ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.05, 
                           row_heights=[0.5, 0.25, 0.25],
                           subplot_titles=("Price & S/R", "MACD & Zero Line", "RSI & Volume"))

        # Row 1: Price + S/R
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
        fig.add_hline(y=res_level, line_dash="dash", line_color="red", annotation_text="Resistance", row=1, col=1)
        fig.add_hline(y=sup_level, line_dash="dash", line_color="green", annotation_text="Support", row=1, col=1)
        
        # Add Signals to Price Chart
        fig.add_trace(go.Scatter(x=df[df['Buy_Signal']].index, y=df['Close'][df['Buy_Signal']], mode='markers', 
                                 marker=dict(symbol='triangle-up', size=15, color='#00ff00'), name='Buy'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df[df['Sell_Signal']].index, y=df['Close'][df['Sell_Signal']], mode='markers', 
                                 marker=dict(symbol='triangle-down', size=15, color='#ff0000'), name='Sell'), row=1, col=1)

        # Row 2: MACD
        fig.add_trace(go.Scatter(x=df.index, y=df[m_line], line=dict(color='cyan'), name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[m_signal], line=dict(color='orange'), name='Signal'), row=2, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df[m_hist], name='Hist', marker_color='gray', opacity=0.5), row=2, col=1)
        fig.add_hline(y=0, line_color="white", opacity=0.3, row=2, col=1)

        # Row 3: RSI & Volume SMA
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

        fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- 5. INTELLIGENT ANALYSIS SECTION ---
        st.subheader("🤖 AI Technical Analysis (Latest Bar)")
        
        last_price = df['Close'].iloc[-1]
        last_rsi = df['RSI'].iloc[-1]
        last_vol = df['Volume'].iloc[-1]
        avg_vol = df['Vol_SMA'].iloc[-1]
        last_macd = df[m_line].iloc[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("RSI State", f"{last_rsi:.2f}")
            if last_rsi > 70: st.warning("⚠️ Overbought (ซื้อมากไป)")
            elif last_rsi < 30: st.success("✅ Oversold (ขายมากไป)")
            else: st.info("Normal Zone")

        with col2:
            st.metric("Volume vs SMA", f"{last_vol/10**6:.1f}M")
            if last_vol > avg_vol: st.success("🔥 High Volume (แรงส่งสูง)")
            else: st.info("Low Volume")

        with col3:
            st.metric("Momentum (Zero Line)", f"{last_macd:.2f}")
            if last_macd > 0: st.success("📈 Bullish Territory")
            else: st.error("📉 Bearish Territory")

        with col4:
            dist_to_res = ((res_level - last_price) / last_price) * 100
            st.metric("Dist. to Resistance", f"{dist_to_res:.1f}%")
            if dist_to_res < 2: st.warning("⚠️ Near Resistance (ระวังติดดอย)")

        # สรุปสัญญาณแบบฉลาด
        st.divider()
        if df['Buy_Signal'].iloc[-1]:
            st.header("📢 Final Action: 🟢 BUY SIGNAL DETECTED")
            score = 0
            if last_rsi < 65: score += 1
            if last_vol > avg_vol: score += 1
            if last_macd > 0: score += 1
            if dist_to_res > 3: score += 1
            
            st.subheader(f"ความเชื่อถือได้: {score}/4")
            if score >= 3: st.balloons()
        elif df['Sell_Signal'].iloc[-1]:
            st.header("📢 Final Action: 🔴 SELL SIGNAL DETECTED")
        else:
            st.info("ยังไม่มีสัญญาณเข้าซื้อใหม่ในขณะนี้")

    else:
        st.error("ไม่สามารถโหลดข้อมูลได้ หรือชื่อหุ้นไม่ถูกต้อง")

except Exception as e:
    st.error(f"Error: {e}")
