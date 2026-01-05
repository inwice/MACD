import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. SETTING UI ---
st.set_page_config(page_title="MACD Pro Scanner", layout="wide")
st.title("📈 MACD Trading Signal System (Fixed Version)")
st.markdown("""
    ระบบนี้จะช่วยคำนวณสัญญาณซื้อ-ขาย โดยใช้หลักการ **MACD Crossover** และแก้ไขปัญหาชื่อ Column ผิดพลาดอัตโนมัติ
""")

# --- 2. SIDEBAR CONFIGURATION ---
st.sidebar.header("⚙️ การตั้งค่าพารามิเตอร์")
symbol = st.sidebar.text_input("ระบุชื่อหุ้น (Ticker)", value="BTC-USD").upper()

# ปรับช่วงวันให้อัตโนมัติ (ย้อนหลัง 1 ปี)
default_start = datetime.now() - timedelta(days=365)
start_date = st.sidebar.date_input("วันที่เริ่มต้น", value=default_start)
end_date = st.sidebar.date_input("วันที่สิ้นสุด", value=datetime.now())

with st.sidebar.expander("ปรับค่า MACD Settings"):
    fast_ema = st.number_input("Fast EMA", value=12)
    slow_ema = st.number_input("Slow EMA", value=26)
    signal_ema = st.number_input("Signal Line", value=9)

# --- 3. DATA FETCHING & PROCESSING ---
@st.cache_data
def get_clean_data(ticker, start, end):
    data = yf.download(ticker, start=start, end=end)
    if data.empty:
        return None
    
    # แก้ปัญหา Multi-index ของ yfinance (ถ้ามี)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    return data

try:
    df = get_clean_data(symbol, start_date, end_date)

    if df is not None and len(df) > slow_ema:
        # คำนวณ MACD
        # pandas_ta จะคืนค่ามาเป็น DataFrame ที่มี 3 columns
        macd_df = ta.macd(df['Close'], fast=fast_ema, slow=slow_ema, signal=signal_ema)
        
        # --- [จุดที่แก้ไข] ดึงชื่อ Column แบบ Dynamic ---
        # macd_df.columns[0] = MACD Line
        # macd_df.columns[1] = Histogram
        # macd_df.columns[2] = Signal Line
        macd_line_col = macd_df.columns[0]
        hist_col = macd_df.columns[1]
        signal_line_col = macd_df.columns[2]

        # รวมข้อมูลเข้าด้วยกัน
        df = pd.concat([df, macd_df], axis=1)

        # คำนวณ Buy/Sell Signal
        # Buy: MACD ตัด Signal Line ขึ้น
        df['Buy_Signal'] = (df[macd_line_col] > df[signal_line_col]) & \
                           (df[macd_line_col].shift(1) <= df[signal_line_col].shift(1))
        
        # Sell: MACD ตัด Signal Line ลง
        df['Sell_Signal'] = (df[macd_line_col] < df[signal_line_col]) & \
                            (df[macd_line_col].shift(1) >= df[signal_line_col].shift(1))

        # --- 4. VISUALIZATION ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.05, row_heights=[0.6, 0.4])

        # กราฟราคา
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                     low=df['Low'], close=df['Close'], name=f"Price ({symbol})"), row=1, col=1)

        # สัญญาณ Buy (สีเขียว)
        fig.add_trace(go.Scatter(x=df[df['Buy_Signal']].index, y=df['Close'][df['Buy_Signal']],
                                 mode='markers', marker=dict(symbol='triangle-up', size=15, color='#00ff00'),
                                 name='Buy Signal'), row=1, col=1)

        # สัญญาณ Sell (สีแดง)
        fig.add_trace(go.Scatter(x=df[df['Sell_Signal']].index, y=df['Close'][df['Sell_Signal']],
                                 mode='markers', marker=dict(symbol='triangle-down', size=15, color='#ff0000'),
                                 name='Sell Signal'), row=1, col=1)

        # กราฟ MACD
        fig.add_trace(go.Scatter(x=df.index, y=df[macd_line_col], line=dict(color='#17BECF', width=2), name='MACD'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df[signal_line_col], line=dict(color='#FF7F0E', width=2), name='Signal'), row=2, col=1)
        
        # Histogram
        hist_colors = ['#ff4b4b' if val < 0 else '#26a69a' for val in df[hist_col]]
        fig.add_trace(go.Bar(x=df.index, y=df[hist_col], marker_color=hist_colors, name='Histogram'), row=2, col=1)

        fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False,
                          margin=dict(l=50, r=50, t=30, b=50))
        st.plotly_chart(fig, use_container_width=True)

        # --- 5. SUMMARY TABLE ---
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("💡 สัญญาณปัจจุบัน")
            last_row = df.iloc[-1]
            if last_row['Buy_Signal']:
                st.success("แนวโน้ม: สัญญาณซื้อ (Golden Cross)")
            elif last_row['Sell_Signal']:
                st.error("แนวโน้ม: สัญญาณขาย (Dead Cross)")
            else:
                st.info("แนวโน้ม: ถือครอง / รอสัญญาณใหม่")

        with col2:
            st.subheader("📝 ประวัติสัญญาณ 5 ครั้งล่าสุด")
            history = df[(df['Buy_Signal']) | (df['Sell_Signal'])].tail(5).copy()
            if not history.empty:
                history['Type'] = history['Buy_Signal'].apply(lambda x: "BUY 🟢" if x else "SELL 🔴")
                history = history[['Close', 'Type']].sort_index(ascending=False)
                st.dataframe(history, use_container_width=True)

    else:
        st.warning("ข้อมูลไม่เพียงพอ กรุณาเลือกช่วงเวลาให้กว้างขึ้น หรือตรวจสอบชื่อ Ticker")

except Exception as e:
    st.error(f"เกิดข้อผิดพลาดทางเทคนิค: {e}")
