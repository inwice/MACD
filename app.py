import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. SETTING UI ---
st.set_page_config(page_title="Professional Trading System", layout="wide")
st.title("🛡️ Advanced MACD & Risk Management Dashboard")

# --- 2. SIDEBAR CONFIGURATION (แก้ไขจุดที่เลือกไม่ได้) ---
st.sidebar.header("🔍 1. ข้อมูลพื้นฐาน")
symbol = st.sidebar.text_input("ชื่อหุ้น/Ticker", value="BTC-USD").upper()
days_back = st.sidebar.number_input("ดูย้อนหลัง (วัน)", min_value=30, max_value=2000, value=365)

st.sidebar.divider()
st.sidebar.header("🛡️ 2. Risk Management Settings")
# ย้ายออกมาจาก Expander เพื่อให้เลือกได้ทันที
sl_buffer_pct = st.sidebar.slider("Stop Loss Buffer (%)", 0.5, 5.0, 2.0, step=0.1)
sl_buffer = sl_buffer_pct / 100
min_rr = st.sidebar.slider("Minimum Risk:Reward Ratio", 1.0, 5.0, 1.5, step=0.1)

st.sidebar.divider()
st.sidebar.header("⚙️ 3. Strategy Thresholds")
rsi_buy_zone = st.sidebar.slider("RSI Buy Zone (<)", 20, 50, 45)
rsi_sell_zone = st.sidebar.slider("RSI Sell Zone (>)", 50, 80, 70)

# --- 3. DATA FETCHING ---
@st.cache_data
def get_data(ticker, days):
    try:
        start = datetime.now() - timedelta(days=int(days))
        # บังคับดึงข้อมูลชั้นเดียว
        data = yf.download(ticker, start=start, multi_level_index=False)
        return data if not data.empty else None
    except Exception as e:
        return None

try:
    df = get_data(symbol, days_back)

    if df is not None and len(df) > 30:
        # --- CALCULATIONS ---
        # 1. Indicators
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        m_line, m_hist, m_signal = macd.columns[0], macd.columns[1], macd.columns[2]
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # 2. Support & Resistance
        sr_period = 20
        df['Support'] = df['Low'].rolling(window=sr_period).min()
        df['Resistance'] = df['High'].rolling(window=sr_period).max()

        # 3. Candle Rejection
        df['Body'] = abs(df['Close'] - df['Open'])
        df['Upper_Wick'] = df['High'] - df[['Open', 'Close']].max(axis=1)
        df['Is_Rejection'] = (df['Upper_Wick'] > (df['Body'] * 1.5)) & (df['High'] >= df['Resistance'] * 0.98)

        # --- 4. SIGNAL LOGIC ---
        # Buy: Near Support + RSI Up + MACD Golden Cross
        cond_buy_price = df['Low'] <= (df['Support'] * 1.02)
        cond_buy_rsi = (df['RSI'] < rsi_buy_zone) & (df['RSI'] > df['RSI'].shift(1))
        cond_buy_macd = (df[m_line] > df[m_signal]) & (df[m_line].shift(1) <= df[m_signal].shift(1))
        df['Final_Buy'] = cond_buy_price & cond_buy_rsi & cond_buy_macd

        # --- 5. VISUALIZATION ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.25, 0.25])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)

        # แสดงข้อมูลสัญญาณล่าสุดบนกราฟ
        has_signal = df['Final_Buy'].any()
        if has_signal:
            last_buy = df[df['Final_Buy']].iloc[-1]
            entry = last_buy['Close']
            tp = last_buy['Resistance']
            sl = last_buy['Support'] * (1 - sl_buffer)
            
            fig.add_hline(y=tp, line_dash="dash", line_color="#00FF00", annotation_text=f"Target TP: {tp:.2f}", row=1, col=1)
            fig.add_hline(y=sl, line_dash="dash", line_color="#FF0000", annotation_text=f"Stop Loss: {sl:.2f}", row=1, col=1)
            fig.add_trace(go.Scatter(x=df[df['Final_Buy']].index, y=df['Low'][df['Final_Buy']] * 0.97, mode='markers', marker=dict(symbol='triangle-up', size=15, color='#00FF00'), name='BUY'), row=1, col=1)

        fig.add_trace(go.Scatter(x=df.index, y=df[m_line], line=dict(color='cyan'), name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[m_signal], line=dict(color='orange'), name='Signal'), row=2, col=1)
        fig.add_hline(y=0, line_color="white", opacity=0.3, row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='magenta'), name='RSI'), row=3, col=1)

        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- 6. ADVISORY DASHBOARD ---
        st.divider()
        c1, c2, c3 = st.columns(3)
        curr = df.iloc[-1]
        
        with c1:
            st.subheader("🔍 Trend Status")
            if curr[m_line] > 0 and curr['RSI'] > 50:
                st.success("✅ **ถือต่อ (Run Trend)**")
                st.write("โมเมนตัมเป็นบวกและยืนเหนือ RSI 50")
            else:
                st.warning("⚠️ **ระมัดระวัง**")
                st.write("เทรนด์ยังไม่อยู่ในจุดแข็งแกร่งที่สุด")

        with c2:
            st.subheader("🚨 Warning Signals")
            if curr['Is_Rejection']: st.error("🛑 **Price Rejection!** พบแรงขายที่แนวต้าน")
            elif curr['RSI'] > rsi_sell_zone: st.warning(f"⚠️ **RSI Overbought (> {rsi_sell_zone})**")
            else: st.info("🟢 สัญญาณราคายังปกติ")

        with c3:
            st.subheader("💰 Risk Control")
            if has_signal:
                last_buy_row = df[df['Final_Buy']].iloc[-1]
                entry_v = float(last_buy_row['Close'])
                tp_v = float(last_buy_row['Resistance'])
                sl_v = float(last_buy_row['Support'] * (1 - sl_buffer))
                
                risk = entry_v - sl_v
                reward = tp_v - entry_v
                rr_v = reward / risk if risk > 0 else 0
                
                st.write(f"**สัญญาณล่าสุด:** {df[df['Final_Buy']].index[-1].date()}")
                st.write(f"**Entry:** {entry_v:,.2f}")
                st.write(f"**TP:** {tp_v:,.2f} | **SL:** {sl_v:,.2f}")
                
                rr_color = "green" if rr_v >= min_rr else "red"
                st.markdown(f"**Risk:Reward Ratio:** <span style='color:{rr_color}'>1:{rr_v:.2f}</span>", unsafe_allow_html=True)
            else:
                st.info("ยังไม่มีสัญญาณซื้อตามเงื่อนไข")

    else:
        st.error("ข้อมูลไม่เพียงพอ กรุณาตรวจสอบ Ticker หรือเพิ่มจำนวนวันย้อนหลัง")

except Exception as e:
    st.error(f"เกิดข้อผิดพลาด: {e}")
