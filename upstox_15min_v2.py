import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import time

st.set_page_config(page_title="Upstox Historical Downloader", layout="wide")
st.title("📈 Upstox Historical Data Downloader")

# =====================================================
# LOAD INSTRUMENT FILE (LOCAL)
# =====================================================

@st.cache_data
def load_instruments():
    df = pd.read_csv("Instrument_key_data.csv")

    # Clean columns
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
# INSTRUMENT SEARCH
# =====================================================

st.subheader("🔎 Instrument Search")

exchange_option = st.radio(
    "Select Exchange",
    ["NSE", "BSE", "ALL"],
    horizontal=True
)

filtered_df = instrument_df.copy()

# Handle NSE_EQ / BSE_EQ etc.
if exchange_option == "NSE":
    filtered_df = filtered_df[
        filtered_df["exchange"].str.contains("NSE", case=False, na=False)
    ]
elif exchange_option == "BSE":
    filtered_df = filtered_df[
        filtered_df["exchange"].str.contains("BSE", case=False, na=False)
    ]

search_text = st.text_input("Search Stock (Name or Symbol e.g. RELIANCE, TCS, INFY)")

selected_instrument_key = None
selected_row = None

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
            search_df["name"] +
            " | " +
            search_df["tradingsymbol"] +
            " | " +
            search_df["exchange"]
        )

        selected_display = st.selectbox(
            "Select Correct Instrument",
            search_df["display"].unique()
        )

        selected_row = search_df[
            search_df["display"] == selected_display
        ].iloc[0]

        selected_instrument_key = selected_row["instrument_key"]

        st.success(f"Selected Instrument Key: {selected_instrument_key}")

        st.write("### Instrument Details")
        st.write("Name:", selected_row["name"])
        st.write("Symbol:", selected_row["tradingsymbol"])
        st.write("Exchange:", selected_row["exchange"])

    else:
        st.warning("No matching stock found.")

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
# FETCH DATA (EXACT SAME LOGIC AS YOUR WORKING SCRIPT)
# =====================================================

if st.button("🚀 Fetch Data"):

    if not access_token:
        st.error("Please enter Access Token")
        st.stop()

    if not selected_instrument_key:
        st.error("Please select an instrument")
        st.stop()

    # 🔥 EXACT SAME DATE LOGIC AS YOUR WORKING SCRIPT
    start_dt = datetime(start_date.year, start_date.month, start_date.day)
    end_dt = datetime(end_date.year, end_date.month, end_date.day)

    all_data = []

    while start_dt < end_dt:

        next_date = start_dt + relativedelta(months=1)

        from_date = start_dt.strftime("%Y-%m-%d")
        to_date = next_date.strftime("%Y-%m-%d")

        st.write(f"Fetching {from_date} to {to_date}")

        url = f"https://api.upstox.com/v2/historical-candle/{selected_instrument_key}/{interval}/{to_date}/{from_date}"

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}"
        }

        try:
            response = requests.get(url, headers=headers)
            data = response.json()

            if "data" in data and "candles" in data["data"]:

                candles = data["data"]["candles"]

                df = pd.DataFrame(candles, columns=[
                    "timestamp", "open", "high", "low", "close", "volume", "oi"
                ])

                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.sort_values("timestamp")
                df.set_index("timestamp", inplace=True)

                # Optional conversion
                if interval == "1minute" and convert_to_5min:
                    df = df.resample("5min").agg({
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "volume": "sum",
                        "oi": "last"
                    }).dropna()

                df.reset_index(inplace=True)
                all_data.append(df)

                st.success(f"✅ Done {from_date}")

            else:
                st.warning(f"No data for {from_date}")

        except Exception as e:
            st.error(f"Error fetching {from_date}: {e}")

        # 🔥 EXACT SAME STEP AS WORKING SCRIPT
        start_dt = next_date
        time.sleep(0.6)

    # =====================================================
    # FINAL OUTPUT
    # =====================================================

    if all_data:
        final_df = pd.concat(all_data)
        final_df = final_df.sort_values("timestamp")

        st.success("🎯 All data fetched successfully")

        st.write("Min Timestamp:", final_df["timestamp"].min())
        st.write("Max Timestamp:", final_df["timestamp"].max())
        st.write("Total Rows:", len(final_df))

        st.line_chart(final_df.set_index("timestamp")["close"])

        csv = final_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "📥 Download CSV",
            data=csv,
            file_name=f"{selected_row['tradingsymbol']}_data.csv",
            mime="text/csv"
        )
    else:
        st.error("No data collected.")