import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. SETTING UI ---
st.set_page_config(page_title="Rule-Based Trading System", layout="wide")
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
    start = datetime.now() - timedelta(days=days)
    data = yf.download(ticker, start=start)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

try:
    df = get_data(symbol, days_back)

    if df is not None and len(df) > sr_window:
        # --- CALCULATIONS ---
        # 1. MACD
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        m_line = macd.columns[0]
        m_hist = macd.columns[1]
        m_signal = macd.columns[2]

        # 2. RSI & Trend
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['RSI_Up'] = df['RSI'] > df['RSI'].shift(1)

        # 3. Support & Resistance (Rolling)
        df['Support'] = df['Low'].rolling(window=sr_window).min()
        df['Resistance'] = df['High'].rolling(window=sr_window).max()

        # 4. Candlestick Patterns (Bullish/Bearish Engulfing)
        df['Bullish_Engulfing'] = ta.cdl_pattern(df['Open'], df['High'], df['Low'], df['Close'], name="engulfing")['CDL_ENGULFING'] > 0
        df['Bearish_Engulfing'] = ta.cdl_pattern(df['Open'], df['High'], df['Low'], df['Close'], name="engulfing")['CDL_ENGULFING'] < 0

        # --- 4. STRICT DECISION LOGIC ---
        
        # BUY ENTRY: Support + RSI Reversal + MACD Golden Cross
        cond_buy_price = df['Low'] <= (df['Support'] * 1.02) # ใกล้แนวรับไม่เกิน 2%
        cond_buy_rsi = (df['RSI'] < rsi_low) & (df['RSI_Up'])
        cond_buy_macd = (df[m_line] > df[m_signal]) & (df[m_line].shift(1) <= df[m_signal].shift(1))
        
        df['Final_Buy'] = cond_buy_price & cond_buy_rsi & cond_buy_macd

        # SELL EXIT: Resistance + RSI Overbought + MACD Dead Cross
        cond_sell_price = df['High'] >= (df['Resistance'] * 0.98) # ใกล้แนวต้านไม่เกิน 2%
        cond_sell_rsi = df['RSI'] > rsi_high
        cond_sell_macd = (df[m_line] < df[m_signal]) & (df[m_line].shift(1) >= df[m_signal].shift(1))
        
        df['Final_Sell'] = cond_sell_price & cond_sell_rsi & cond_sell_macd

        # --- 5. VISUALIZATION ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.25, 0.25])

        # Price Chart
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Support'], line=dict(color='green', dash='dot'), name='Support'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Resistance'], line=dict(color='red', dash='dot'), name='Resistance'), row=1, col=1)
        
        # Markers
        fig.add_trace(go.Scatter(x=df[df['Final_Buy']].index, y=df['Low'][df['Final_Buy']] * 0.98, mode='markers', marker=dict(symbol='star-triangle-up', size=18, color='#00FF00'), name='ENTRY'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df[df['Final_Sell']].index, y=df['High'][df['Final_Sell']] * 1.02, mode='markers', marker=dict(symbol='star-triangle-down', size=18, color='#FF0000'), name='EXIT'), row=1, col=1)

        # MACD
        fig.add_trace(go.Scatter(x=df.index, y=df[m_line], line=dict(color='cyan'), name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[m_signal], line=dict(color='orange'), name='Signal'), row=2, col=1)

        # RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name='RSI'), row=3, col=1)
        fig.add_hline(y=rsi_high, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=rsi_low, line_dash="dash", line_color="green", row=3, col=1)

        fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- 6. DECISION DASHBOARD ---
        st.subheader("📋 Real-time Strategy Checklist")
        last_row = df.iloc[-1]
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("### 🟢 Buy Entry Check")
            st.checkbox("Price at Support (Near 2% zone)", value=bool(cond_buy_price.iloc[-1]), disabled=True)
            st.checkbox(f"RSI Reversal (< {rsi_low} & Turning Up)", value=bool(cond_buy_rsi.iloc[-1]), disabled=True)
            st.checkbox("MACD Golden Cross", value=bool(cond_buy_macd.iloc[-1]), disabled=True)
            if last_row['Bullish_Engulfing']: st.success("✨ Pattern Found: Bullish Engulfing!")

        with c2:
            st.write("### 🔴 Sell Exit Check")
            st.checkbox("Price at Resistance (Near 2% zone)", value=bool(cond_sell_price.iloc[-1]), disabled=True)
            st.checkbox(f"RSI Overbought (> {rsi_high})", value=bool(cond_sell_rsi.iloc[-1]), disabled=True)
            st.checkbox("MACD Dead Cross", value=bool(cond_sell_macd.iloc[-1]), disabled=True)
            if last_row['Bearish_Engulfing']: st.error("⚠️ Pattern Found: Bearish Engulfing!")

        if last_row['Final_Buy']:
            st.success("🚀 **STRATEGY SIGNAL: BUY ENTRY NOW**")
        elif last_row['Final_Sell']:
            st.error("🛑 **STRATEGY SIGNAL: SELL EXIT NOW**")

    else:
        st.info("กรุณาระบุชื่อหุ้นเพื่อเริ่มต้นการวิเคราะห์")

except Exception as e:
    st.error(f"ระบบขัดข้อง: {e}")
