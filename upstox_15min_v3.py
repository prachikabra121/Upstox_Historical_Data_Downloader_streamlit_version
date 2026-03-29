import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time

st.set_page_config(page_title="Upstox Historical Downloader", layout="wide")
st.title("📈 Upstox Historical Data Downloader")

# =====================================================
# LOAD INSTRUMENT FILE
# =====================================================

@st.cache_data
def load_instruments():
    df = pd.read_csv("Instrument_key_data.csv")
    df.columns = df.columns.str.strip().str.lower()

    for col in ["name", "tradingsymbol", "exchange", "instrument_type"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df

instrument_df = load_instruments()

# =====================================================
# AUTH SECTION
# =====================================================

st.subheader("🔐 Authentication")
access_token = st.text_input("Enter Access Token", type="password")

# =====================================================
# SELECTION BASKET INIT
# =====================================================

if "selected_basket" not in st.session_state:
    st.session_state.selected_basket = []

# =====================================================
# SEARCH + ADD TO BASKET
# =====================================================

st.subheader("🔎 Search & Add Instruments")

exchange_option = st.radio(
    "Select Exchange",
    ["NSE", "BSE", "ALL"],
    horizontal=True
)

filtered_df = instrument_df.copy()

if exchange_option == "NSE":
    filtered_df = filtered_df[
        filtered_df["exchange"].str.contains("NSE", case=False, na=False)
    ]
elif exchange_option == "BSE":
    filtered_df = filtered_df[
        filtered_df["exchange"].str.contains("BSE", case=False, na=False)
    ]

search_text = st.text_input("Search Stock (Name or Symbol)")

if search_text:

    search_text = search_text.strip().lower()

    search_df = filtered_df[
        filtered_df["name"].str.lower().str.contains(search_text, na=False)
        |
        filtered_df["tradingsymbol"].str.lower().str.contains(search_text, na=False)
    ]

    if not search_df.empty:

        search_df = search_df.copy()
        search_df["display"] = (
            search_df["name"] + " | " +
            search_df["tradingsymbol"] + " | " +
            search_df["exchange"]
        )

        selected_to_add = st.multiselect(
            "Select Instruments to Add",
            search_df["display"].unique()
        )

        if st.button("➕ Add to Basket"):
            for display in selected_to_add:
                row = search_df[search_df["display"] == display].iloc[0]

                if row["instrument_key"] not in [
                    r["instrument_key"] for r in st.session_state.selected_basket
                ]:
                    st.session_state.selected_basket.append(row)

    else:
        st.warning("No matching stock found.")

# =====================================================
# SHOW SELECTED BASKET
# =====================================================

st.subheader("🧺 Selected Instruments")

if st.session_state.selected_basket:

    for i, row in enumerate(st.session_state.selected_basket):

        col1, col2 = st.columns([5,1])

        with col1:
            st.write(
                f"{row['name']} | {row['tradingsymbol']} | {row['exchange']}"
            )

        with col2:
            if st.button("❌", key=f"remove_{i}"):
                st.session_state.selected_basket.pop(i)
                st.rerun()

else:
    st.info("No instruments selected yet.")

# =====================================================
# DATE & INTERVAL
# =====================================================

st.subheader("📅 Date & Interval")

col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input("Start Date", datetime(2024, 1, 1))

with col2:
    end_date = st.date_input("End Date", datetime.today())

interval = st.selectbox(
    "Select Interval",
    ["1minute", "5minute", "15minute", "30minute", "day"]
)

convert_to_5min = st.checkbox("Convert 1minute → 5minute")

# =====================================================
# FETCH DATA (CORRECTED MULTI-STOCK LOOP)
# =====================================================

if st.button("🚀 Fetch Data"):

    if not access_token:
        st.error("Please enter Access Token")
        st.stop()

    if not st.session_state.selected_basket:
        st.error("Please add at least one instrument")
        st.stop()

    for selected_row in st.session_state.selected_basket:

        # 🔥 IMPORTANT: Reset dates for EACH stock
        start_dt = datetime(start_date.year, start_date.month, start_date.day)
        end_dt = datetime(end_date.year, end_date.month, end_date.day)

        instrument_key = selected_row["instrument_key"]
        symbol = selected_row["tradingsymbol"]

        st.subheader(f"📊 {symbol}")

        all_data = []

        while start_dt < end_dt:

            next_date = start_dt + relativedelta(months=1)

            from_date = start_dt.strftime("%Y-%m-%d")
            to_date = next_date.strftime("%Y-%m-%d")

            url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}"

            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}"
            }

            try:
                response = requests.get(url, headers=headers)
                data = response.json()

                if "data" in data and "candles" in data["data"]:

                    df = pd.DataFrame(
                        data["data"]["candles"],
                        columns=["timestamp","open","high","low","close","volume","oi"]
                    )

                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df = df.sort_values("timestamp")
                    df.set_index("timestamp", inplace=True)

                    if interval == "1minute" and convert_to_5min:
                        df = df.resample("5min").agg({
                            "open":"first",
                            "high":"max",
                            "low":"min",
                            "close":"last",
                            "volume":"sum",
                            "oi":"last"
                        }).dropna()

                    df.reset_index(inplace=True)
                    all_data.append(df)

            except Exception as e:
                st.error(f"Error fetching {symbol}: {e}")

            # 🔥 update only inside this stock loop
            start_dt = next_date
            time.sleep(0.6)

        if all_data:
            final_df = pd.concat(all_data).sort_values("timestamp")

            st.write("Rows:", len(final_df))
            st.write("Min:", final_df["timestamp"].min())
            st.write("Max:", final_df["timestamp"].max())

            st.line_chart(final_df.set_index("timestamp")["close"])

            csv = final_df.to_csv(index=False).encode("utf-8")

            st.download_button(
                f"📥 Download {symbol} CSV",
                data=csv,
                file_name=f"{symbol}_data.csv",
                mime="text/csv",
                key=f"download_{symbol}"
            )

        else:
            st.warning(f"No data collected for {symbol}")