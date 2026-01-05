import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. SETTING UI ---
st.set_page_config(page_title="Professional Trade Manager", layout="wide")
st.title("🛡️ Smart Trading System: Strategy + Risk Management")

# --- 2. SIDEBAR CONFIGURATION ---
st.sidebar.header("⚙️ System Config")
symbol = st.sidebar.text_input("Ticker Symbol", value="BTC-USD").upper()
days_back = st.sidebar.slider("Lookback Period (Days)", 60, 1000, 365)

with st.sidebar.expander("Risk Management Settings"):
    sl_buffer = st.sidebar.slider("Stop Loss Buffer (%)", 0.5, 5.0, 2.0) / 100
    min_rr = st.sidebar.slider("Min Risk:Reward Ratio", 1.0, 5.0, 1.5)

# --- 3. DATA FETCHING ---
@st.cache_data
def get_data(ticker, days):
    try:
        start = datetime.now() - timedelta(days=days)
        data = yf.download(ticker, start=start, multi_level_index=False)
        return data if not data.empty else None
    except:
        return None

try:
    df = get_data(symbol, days_back)

    if df is not None and len(df) > 30:
        # --- CALCULATIONS ---
        # 1. MACD & RSI
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        m_line, m_hist, m_signal = macd.columns[0], macd.columns[1], macd.columns[2]
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # 2. Support & Resistance
        sr_period = 20
        df['Support'] = df['Low'].rolling(window=sr_period).min()
        df['Resistance'] = df['High'].rolling(window=sr_period).max()

        # 3. Candlestick Analysis (Rejection Wick)
        df['Body'] = abs(df['Close'] - df['Open'])
        df['Upper_Wick'] = df['High'] - df[['Open', 'Close']].max(axis=1)
        df['Is_Rejection'] = (df['Upper_Wick'] > (df['Body'] * 1.5)) & (df['High'] >= df['Resistance'] * 0.99)

        # --- 4. STRATEGY LOGIC ---
        # Buy Entry
        cond_buy_price = df['Low'] <= (df['Support'] * 1.02)
        cond_buy_rsi = (df['RSI'] < 45) & (df['RSI'] > df['RSI'].shift(1))
        cond_buy_macd = (df[m_line] > df[m_signal]) & (df[m_line].shift(1) <= df[m_signal].shift(1))
        df['Final_Buy'] = cond_buy_price & cond_buy_rsi & cond_buy_macd

        # --- 5. VISUALIZATION ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.25, 0.25])

        # Main Chart
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
        
        # Plot TP/SL for the latest Buy Signal
        if df['Final_Buy'].any():
            last_buy_idx = df[df['Final_Buy']].index[-1]
            entry_price = df.loc[last_buy_idx, 'Close']
            sl_price = df.loc[last_buy_idx, 'Support'] * (1 - sl_buffer)
            tp_price = df.loc[last_buy_idx, 'Resistance']
            
            # วาดเส้น TP/SL
            fig.add_hline(y=tp_price, line_dash="dash", line_color="#00FF00", annotation_text=f"Target TP: {tp_price:.2f}", row=1, col=1)
            fig.add_hline(y=sl_price, line_dash="dash", line_color="#FF0000", annotation_text=f"Stop Loss: {sl_price:.2f}", row=1, col=1)
            
            # แสดงลูกศรจุดซื้อ
            fig.add_trace(go.Scatter(x=df[df['Final_Buy']].index, y=df['Low'][df['Final_Buy']] * 0.97, 
                                     mode='markers', marker=dict(symbol='triangle-up', size=15, color='#00FF00'), name='BUY ENTRY'), row=1, col=1)

        # MACD & Zero Line
        fig.add_trace(go.Scatter(x=df.index, y=df[m_line], line=dict(color='cyan'), name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[m_signal], line=dict(color='orange'), name='Signal'), row=2, col=1)
        fig.add_hline(y=0, line_color="white", opacity=0.5, row=2, col=1)

        # RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name='RSI'), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
        fig.add_hline(y=50, line_dash="dash", line_color="gray", row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

        fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- 6. ADVISORY DASHBOARD ---
        st.subheader("🛡️ Trade Manager & Risk Analysis")
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info("🔍 สถานะปัจจุบัน (Trend Check)")
            if curr[m_line] > 0 and curr['RSI'] > 50:
                st.success("✅ **ถือต่อ (Run Trend)**\n\nMACD > 0 และ RSI ยืนเหนือ 50 ได้มั่นคง")
            elif curr[m_line] < 0:
                st.warning("⚠️ **เทรนด์อ่อนแอ**\n\nMACD ยังอยู่ใต้ Zero Line")
            else:
                st.write("สถานะ: รอเลือกทาง")

        with col2:
            st.error("🚨 สัญญาณอันตราย (Emergency)")
            if curr['Is_Rejection']:
                st.markdown("🛑 **รีบขายทันที!**\n\nพบแรงเทขาย (Rejection) ที่แนวต้าน")
            if curr['RSI'] > 70 and curr[m_line] < prev[m_line]:
                st.markdown("🛑 **Overbought + MACD Curve Down**\n\nความแรงเริ่มลดลงระวังการปรับตัว")
            else:
                st.write("ยังไม่พบสัญญาณจบคะแนนลบ")

        with col3:
            st.success("💰 Risk Control (Latest Signal)")
            if df['Final_Buy'].any():
                buy_row = df[df['Final_Buy']].iloc[-1]
                entry = buy_row['Close']
                tp = buy_row['Resistance']
                sl = buy_row['Support'] * (1 - sl_buffer)
                rr = (tp - entry) / (entry - sl) if (entry - sl) != 0 else 0
                
                st.write(f"**Entry:** {entry:,.2f}")
                st.write(f"**Take Profit:** {tp:,.2f}")
                st.write(f"**Stop Loss:** {sl:,.2f}")
                st.metric("Risk:Reward Ratio", f"1:{rr:.2f}")
                
                if rr < min_rr:
                    st.warning("⚠️ ไม่คุ้มเสี่ยง: RR Ratio ต่ำกว่าที่กำหนด")

    else:
        st.warning("กรุณากรอก Ticker ให้ถูกต้อง")

except Exception as e:
    st.error(f"Error: {e}")
