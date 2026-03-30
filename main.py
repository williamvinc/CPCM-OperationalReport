import pandas as pd
import streamlit as st
import plotly.express as px


# =========================
# DATA LOADING & CLEANING
# =========================
def load_data(file) -> pd.DataFrame:
    """Load Excel starting from row 7."""
    df = pd.read_excel(file, skiprows=6)
    df.columns = df.columns.str.strip()
    return df


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Basic cleaning."""
    df = df.copy()
    df = df.dropna(how="all")

    df["Bill Duration(Mins)"] = pd.to_numeric(
        df["Bill Duration(Mins)"], errors="coerce"
    )

    return df


def filter_date_range(df: pd.DataFrame) -> pd.DataFrame:
    """Filter by Business Date (default last 30 days)."""
    df = df.copy()
    df["Business Date"] = pd.to_datetime(df["Business Date"], errors="coerce")

    min_date = df["Business Date"].min()
    max_date = df["Business Date"].max()

    default_start = max_date - pd.Timedelta(days=30)

    start_date, end_date = st.date_input(
        "Select Date Range",
        value=(default_start, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    mask = (df["Business Date"] >= pd.to_datetime(start_date)) & (
        df["Business Date"] <= pd.to_datetime(end_date)
    )

    return df.loc[mask]


def filter_outlet(df: pd.DataFrame) -> pd.DataFrame:
    """Filter by outlet."""
    outlet = st.selectbox("Select Outlet", df["Outlet"].dropna().unique())
    return df[df["Outlet"] == outlet]


# =========================
# TRANSFORMATION
# =========================
def extract_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract hour safely from Order Start Time and Day from Business Date."""
    df = df.copy()

    def parse_hour(time_range):
        if pd.isna(time_range):
            return None
        try:
            start = str(time_range).split("-")[0].strip()
            return pd.to_datetime(start, format="%I:%M %p").hour
        except Exception:
            return None

    df["hour"] = df["Order Start Time"].apply(parse_hour)
    df = df.dropna(subset=["hour"])
    df["hour"] = df["hour"].astype(int)

    df["Day Name"] = df["Business Date"].dt.day_name()

    return df


def aggregate_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate hourly metrics."""
    agg = (
        df.groupby("hour")
        .agg(
            transactions=("Bill No.", "count"),
            total_duration=("Bill Duration(Mins)", "sum"),
        )
        .reset_index()
    )

    # stress score (advanced metric)
    agg["stress_score"] = agg["transactions"] * agg["total_duration"]

    return agg


def aggregate_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate metrics by Business Date."""
    return (
        df.groupby("Business Date")
        .agg(
            transactions=("Bill No.", "count"),
            total_duration=("Bill Duration(Mins)", "sum"),
        )
        .reset_index()
    )


def aggregate_day_of_week(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate metrics by Day Name."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    agg = (
        df.groupby("Day Name")
        .agg(transactions=("Bill No.", "count"))
        .reindex(days)
        .reset_index()
    )
    agg["transactions"] = agg["transactions"].fillna(0)
    return agg


# =========================
# KPI & INSIGHT
# =========================
def show_kpis(df: pd.DataFrame) -> None:
    total_tx = df["Bill No."].nunique()
    active_days = df["Business Date"].nunique()
    active_hours = df["hour"].nunique()
    avg_proc = df["Bill Duration(Mins)"].mean()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Transactions", total_tx, help="Total unik nomor tagihan. Data ini dihitung dari jumlah nilai unik pada kolom 'Bill No.'.")
    col2.metric("Active Days", active_days, help="Jumlah hari operasional aktif dalam rentang waktu yang dipilih. Dihitung dari 'Business Date'.")
    col3.metric("Active Hours", active_hours, help="Jumlah jam berbeda di mana ada transaksi secara akumulatif. Data ini diekstrak dari kolom 'Order Start Time'.")
    col4.metric("Avg Proc Time (Mins)", f"{avg_proc:.1f}", help="Rata-rata waktu pengerjaan pesanan. Dihitung dari rata-rata kolom 'Bill Duration(Mins)'.")


def show_peak_insight(agg: pd.DataFrame) -> None:
    peak = agg.loc[agg["transactions"].idxmax()]

    st.info(
        f"Peak hour: {peak['hour']}:00 with {peak['transactions']} transactions"
    )


def show_overload(agg: pd.DataFrame) -> None:
    tx_q = agg["transactions"].quantile(0.75)
    dur_q = agg["total_duration"].quantile(0.75)

    overload = agg[
        (agg["transactions"] >= tx_q) &
        (agg["total_duration"] >= dur_q)
    ]

    if not overload.empty:
        st.warning("⚠️ Potential Overload Detected")
        st.dataframe(overload)
    else:
        st.success("No overload detected")


def show_idle(agg: pd.DataFrame) -> None:
    threshold = agg["transactions"].quantile(0.25)
    idle = agg[agg["transactions"] <= threshold]

    st.subheader("Low Activity Window", help="Daftar jam dengan aktivitas terendah (berada di bawah persentil ke-25). Perhitungan didasarkan pada jumlah transaksi dari kolom 'Bill No.'.")
    st.dataframe(idle)


# =========================
# VISUALIZATION
# =========================
def plot_daily_trend(agg_daily: pd.DataFrame) -> None:
    fig = px.line(agg_daily, x="Business Date", y="transactions", title="Daily Transactions Trend", markers=True)
    st.plotly_chart(fig, width="stretch")


def plot_day_of_week(agg_dow: pd.DataFrame) -> None:
    fig = px.bar(agg_dow, x="Day Name", y="transactions", title="Transactions by Day of Week")
    st.plotly_chart(fig, width="stretch")


def plot_peak_hour(agg: pd.DataFrame) -> None:
    fig = px.bar(agg, x="hour", y="transactions", title="Peak Hour")
    st.plotly_chart(fig, width="stretch")


def plot_stress(agg: pd.DataFrame) -> None:
    fig = px.line(
        agg,
        x="hour",
        y=["transactions", "total_duration"],
        title="Operational Stress"
    )
    st.plotly_chart(fig, width="stretch")


def plot_category(df: pd.DataFrame) -> None:
    cat = df.groupby(["hour", "Category"]).size().reset_index(name="count")
    fig = px.bar(
        cat,
        x="hour",
        y="count",
        color="Category",
        title="Category Behavior (Hourly)"
    )
    st.plotly_chart(fig, width="stretch")


def plot_category_daily(df: pd.DataFrame) -> None:
    cat = df.groupby(["Business Date", "Category"]).size().reset_index(name="count")
    fig = px.bar(
        cat,
        x="Business Date",
        y="count",
        color="Category",
        title="Category Behavior (Daily)"
    )
    st.plotly_chart(fig, width="stretch")


def plot_top_items(df: pd.DataFrame) -> None:
    top_items = df["Item"].value_counts().reset_index().head(10)
    top_items.columns = ["Item", "Sold"]
    top_items = top_items.sort_values("Sold", ascending=True)
    
    fig = px.bar(
        top_items, x="Sold", y="Item", orientation="h", 
        title="Top 10 Selling Items"
    )
    st.plotly_chart(fig, width="stretch")


def plot_top_categories(df: pd.DataFrame) -> None:
    top_cat = df["Category"].value_counts().reset_index().head(10)
    top_cat.columns = ["Category", "Total Orders"]
    top_cat = top_cat.sort_values("Total Orders", ascending=True)
    
    fig = px.bar(
        top_cat, x="Total Orders", y="Category", orientation="h", 
        title="Top 10 Categories"
    )
    st.plotly_chart(fig, width="stretch")


# =========================
# MAIN APP
# =========================
def main() -> None:
    st.title("Outlet Operational Dashboard")

    file = st.file_uploader("Upload Excel", type=["xlsx"])

    if file:
        # pipeline
        df = load_data(file)
        df = clean_data(df)
        df = filter_date_range(df)
        df = filter_outlet(df)
        df = extract_time_features(df)

        agg_hourly = aggregate_hourly(df)
        agg_daily = aggregate_daily(df)
        agg_dow = aggregate_day_of_week(df)

        st.subheader("Executive Summary", help="Ringkasan metrik utama operasional pada periode yang dipilih. Menampilkan performa berdasarkan total transaksi, hari aktif, dan jam aktif.")
        show_kpis(df)
        show_peak_insight(agg_hourly)

        st.subheader("Daily Trend & Day of Week", help="Menampilkan pergerakan jumlah transaksi dari hari ke hari dan agregasi transaksi berdasarkan nama hari (Senin-Minggu). Data dari kolom 'Business Date'.")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            try:
                plot_daily_trend(agg_daily)
            except Exception as e:
                st.error(f"plot_daily_trend error: {repr(e)}")
        with col_c2:
            try:
                plot_day_of_week(agg_dow)
            except Exception as e:
                st.error(f"plot_day_of_week error: {repr(e)}")

        st.subheader("Produk Terlaris", help="Menampilkan 10 menu yang paling banyak dipesan dari rentang waktu yang dipilih berdasar kolom 'Item'.")
        try:
            plot_top_items(df)
        except Exception as e:
            st.error(f"plot_top_items error: {repr(e)}")

        st.subheader("Peak Hour", help="Cek busy time per transaction")
        try:
            plot_peak_hour(agg_hourly)
        except Exception as e:
            st.error(f"plot_peak_hour error: {repr(e)}")

        st.subheader("Operational Stress", help="Cek busy time per transaction + Bill duration")
        try:
            plot_stress(agg_hourly)
        except Exception as e:
            st.error(f"plot_stress error: {repr(e)}")

        st.subheader("Category Behavior", help="Cek distribusi transaction per kategori berdasarkan jam dan hari operasional.")
        try:
            plot_category(df)
        except Exception as e:
            st.error(f"plot_category error: {repr(e)}")

        try:
            plot_category_daily(df)
        except Exception as e:
            st.error(f"plot_category_daily error: {repr(e)}")

        st.subheader("Top Categories", help="Menampilkan peringkat kategori dari yang paling banyak dipesan.")
        try:
            plot_top_categories(df)
        except Exception as e:
            st.error(f"plot_top_categories error: {repr(e)}")

        # Baru insight & table
        # st.subheader("Operational Risk", help="Daftar jam dengan beban paling rawan (Overload). Jam tersebut muncul karena jumlah transaksi dan durasinya sama-sama berada di batas atas (di atas persentil 75). Data menggunakan gabungan dari 'Bill No.' dan 'Bill Duration(Mins)'.")
        # show_overload(agg_hourly)

        # show_idle(agg_hourly)

        # paling bawah baru raw data
        with st.expander("Raw Data"):
            st.dataframe(df.head())


if __name__ == "__main__":
    main()