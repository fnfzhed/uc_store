"""Dashboard eksplorasi analitik PT Sembada Niaga Nusantara.

Membaca data warehouse toko_dw sebagai bi_user (hanya baca skema dw dan mart).

Menjalankan:
  venv/bin/streamlit run dashboard.py
Lalu buka http://localhost:8501
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from sumber_data import baca

# Warna kategorikal, urutan tetap. Warna mengikuti entitas, bukan peringkat.
SLOT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
        "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
            "#256abf", "#184f95", "#0d366b"]
UKURAN = {"Omzet": "omzet", "Laba kotor": "laba", "HPP": "hpp", "Qty": "qty"}

st.set_page_config(page_title="Analitik Penjualan Toko", layout="wide")


# ---------------------------------------------------------------- data
@st.cache_data(ttl=600, show_spinner="Membaca data warehouse...")
def muat_fakta():
    df, asal = baca("fakta")
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    df["periode"] = df["tanggal"].dt.to_period("M").dt.to_timestamp()
    df["akhir_pekan"] = df["akhir_pekan"].astype(bool)
    for k in ("omzet", "hpp", "laba"):
        df[k] = df[k].astype(float)
    return df, asal


@st.cache_data(ttl=600)
def muat_pelanggan_360():
    return baca("pelanggan_360")[0]


def rupiah(x, singkat=True):
    if singkat:
        for batas, akhiran in ((1e9, " M"), (1e6, " jt"), (1e3, " rb")):
            if abs(x) >= batas:
                return f"Rp{x / batas:,.1f}{akhiran}".replace(",", "#") \
                    .replace(".", ",").replace("#", ".")
    return f"Rp{x:,.0f}".replace(",", ".")


def warna(nilai_urut):
    """Peta warna tetap per entitas, urut alfabet supaya stabil saat difilter."""
    return {v: SLOT[i % len(SLOT)] for i, v in enumerate(sorted(nilai_urut))}


def rapikan(fig, tinggi=360, legenda=True):
    fig.update_layout(
        template="plotly_white", height=tinggi,
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified" if fig.data and fig.data[0].type == "scatter" else "closest",
        # legenda di bawah grafik supaya tidak menimpa judul
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0, title=None),
        showlegend=legenda, font=dict(size=13),
    )
    fig.update_xaxes(showgrid=False, title=None)
    fig.update_yaxes(gridcolor="#ecebe8", title=None, zeroline=False)
    fig.update_traces(selector=dict(type="scatter"), line=dict(width=2),
                      marker=dict(size=8))
    return fig


try:
    data, asal_data = muat_fakta()
except Exception as e:  # noqa: BLE001
    st.error(f"Data tidak bisa dibaca dari toko_dw maupun snapshot: {e}")
    st.stop()

WARNA_CABANG = warna(data["cabang"].unique())
WARNA_KATEGORI = warna(data["kategori"].unique())
WARNA_JENIS = warna(data["jenis"].dropna().unique())

# ---------------------------------------------------------------- filter
st.title("Analitik Penjualan — PT Sembada Niaga Nusantara")
if asal_data == "database":
    st.caption("Sumber: data warehouse toko_dw (skema dw dan mart), dibaca sebagai bi_user.")
else:
    st.caption("Sumber: snapshot data warehouse toko_dw (folder data/), "
               "karena database tidak terjangkau dari server ini.")

with st.sidebar:
    st.header("Filter")
    bulan_list = sorted(data["periode"].unique())
    awal, akhir = st.select_slider(
        "Rentang bulan", options=bulan_list,
        value=(bulan_list[0], bulan_list[-1]),
        format_func=lambda d: pd.Timestamp(d).strftime("%b %Y"))
    cabang = st.multiselect("Cabang", sorted(data["cabang"].unique()),
                            default=sorted(data["cabang"].unique()))
    kategori = st.multiselect("Kategori", sorted(data["kategori"].unique()),
                              default=sorted(data["kategori"].unique()))
    jenis = st.multiselect("Jenis pelanggan", sorted(data["jenis"].dropna().unique()),
                           default=sorted(data["jenis"].dropna().unique()))
    # bulan dengan nota < 20% median dianggap belum lengkap (mis. bulan berjalan)
    nota_bln = data.groupby("periode")["no_nota"].nunique()
    bulan_parsial = nota_bln[nota_bln < 0.2 * nota_bln.median()].index
    sembunyikan = st.checkbox(
        "Sembunyikan bulan belum lengkap", value=True,
        help="Bulan: " + ", ".join(pd.Timestamp(b).strftime("%b %Y")
                                   for b in bulan_parsial)
             + ". Isinya hanya nota uji dari Lab 7 dan Lab 9.")
    ukuran_label = st.radio("Ukuran utama", list(UKURAN), horizontal=True)
    ukuran = UKURAN[ukuran_label]
    if st.button("Muat ulang data"):
        st.cache_data.clear()
        st.rerun()

df = data[(data["periode"] >= awal) & (data["periode"] <= akhir)
          & data["cabang"].isin(cabang) & data["kategori"].isin(kategori)
          & data["jenis"].isin(jenis)]
if sembunyikan:
    df = df[~df["periode"].isin(bulan_parsial)]

if df.empty:
    st.warning("Tidak ada data untuk kombinasi filter ini.")
    st.stop()

# ---------------------------------------------------------------- KPI
omzet, laba = df["omzet"].sum(), df["laba"].sum()
k = st.columns(6)
k[0].metric("Omzet", rupiah(omzet))
k[1].metric("Laba kotor", rupiah(laba))
k[2].metric("Margin", f"{100 * laba / omzet:.1f}%".replace(".", ","))
k[3].metric("Jumlah nota", f"{df['no_nota'].nunique():,}".replace(",", "."))
k[4].metric("Pelanggan (master)", df["id_master"].nunique())
k[5].metric("Pelanggan (ID kasir)", df["id_pelanggan_sumber"].nunique(),
            delta=f"{df['id_pelanggan_sumber'].nunique() - df['id_master'].nunique()} "
                  "terhitung ganda", delta_color="off")

tab = st.tabs(["Tren", "Produk & kategori", "Cabang", "Pelanggan",
               "Pola hari", "Eksplorasi bebas"])

# ---------------------------------------------------------------- Tren
with tab[0]:
    bulanan = df.groupby("periode", as_index=False)[["omzet", "laba", "hpp", "qty"]].sum()
    bulanan["tumbuh"] = bulanan[ukuran].pct_change() * 100

    c1, c2 = st.columns(2)
    fig = px.line(bulanan, x="periode", y=ukuran, markers=True,
                  title=f"{ukuran_label} per bulan", color_discrete_sequence=[SLOT[0]])
    fig.update_traces(hovertemplate="%{x|%b %Y}: %{y:,.0f}<extra></extra>")
    c1.plotly_chart(rapikan(fig, legenda=False), width="stretch")

    fig = go.Figure(go.Bar(
        x=bulanan["periode"], y=bulanan["tumbuh"],
        marker_color=[SLOT[2] if v >= 0 else SLOT[7] for v in bulanan["tumbuh"].fillna(0)],
        hovertemplate="%{x|%b %Y}: %{y:.1f}%<extra></extra>"))
    fig.update_layout(title=f"Pertumbuhan {ukuran_label.lower()} vs bulan lalu (%)")
    c2.plotly_chart(rapikan(fig, legenda=False), width="stretch")

    per_kat = df.groupby(["periode", "kategori"], as_index=False)[ukuran].sum()
    fig = px.area(per_kat, x="periode", y=ukuran, color="kategori",
                  color_discrete_map=WARNA_KATEGORI,
                  title=f"Komposisi {ukuran_label.lower()} per kategori")
    st.plotly_chart(rapikan(fig, 380), width="stretch")
    if not sembunyikan and len(bulan_parsial):
        st.caption("Bulan terakhir hanya berisi nota uji NT900001/NT900002 dari "
                   "Lab 7 dan Lab 9, jadi nilainya kecil dan tren tampak jatuh.")

# ---------------------------------------------------------------- Produk
with tab[1]:
    c1, c2 = st.columns(2)
    kat = df.groupby("kategori", as_index=False)[ukuran].sum().sort_values(ukuran)
    fig = px.bar(kat, x=ukuran, y="kategori", orientation="h", color="kategori",
                 color_discrete_map=WARNA_KATEGORI,
                 title=f"{ukuran_label} per kategori", text_auto=".3s")
    c1.plotly_chart(rapikan(fig, legenda=False), width="stretch")

    n_top = c2.slider("Jumlah produk", 3, 10, 5)
    prod = (df.groupby(["produk", "kategori"], as_index=False)[ukuran].sum()
              .nlargest(n_top, ukuran).sort_values(ukuran))
    fig = px.bar(prod, x=ukuran, y="produk", orientation="h", color="kategori",
                 color_discrete_map=WARNA_KATEGORI,
                 title=f"Top {n_top} produk berdasarkan {ukuran_label.lower()}")
    fig.update_yaxes(categoryorder="total ascending")  # urut nilai, bukan per warna
    c2.plotly_chart(rapikan(fig), width="stretch")

    margin = df.groupby("produk", as_index=False)[["omzet", "laba", "qty"]].sum()
    margin["margin_%"] = 100 * margin["laba"] / margin["omzet"]
    margin["laba_per_unit"] = margin["laba"] / margin["qty"]
    st.subheader("Margin per produk")
    st.dataframe(
        margin.sort_values("laba", ascending=False), hide_index=True,
        width="stretch",
        column_config={
            "omzet": st.column_config.NumberColumn("Omzet", format="Rp %,.0f"),
            "laba": st.column_config.NumberColumn("Laba", format="Rp %,.0f"),
            "qty": st.column_config.NumberColumn("Qty", format="%,d"),
            "margin_%": st.column_config.ProgressColumn(
                "Margin", format="%.1f%%", min_value=0, max_value=30),
            "laba_per_unit": st.column_config.NumberColumn(
                "Laba per unit", format="Rp %,.0f"),
        })

    st.subheader("Musiman: kategori × kuartal")
    pv = df.pivot_table(index="kategori", columns=["tahun", "kuartal"],
                        values=ukuran, aggfunc="sum")
    pv.columns = [f"{t} Q{q}" for t, q in pv.columns]
    fig = px.imshow(pv, color_continuous_scale=SEQ_BLUE, aspect="auto",
                    text_auto=".3s")
    fig.update_traces(xgap=2, ygap=2)
    st.plotly_chart(rapikan(fig, 320, legenda=False), width="stretch")

# ---------------------------------------------------------------- Cabang
with tab[2]:
    c1, c2 = st.columns(2)
    cb = df.groupby("cabang", as_index=False)[ukuran].sum()
    fig = px.bar(cb, x="cabang", y=ukuran, color="cabang",
                 color_discrete_map=WARNA_CABANG, text_auto=".3s",
                 title=f"{ukuran_label} per cabang")
    c1.plotly_chart(rapikan(fig, legenda=False), width="stretch")

    ck = df.groupby(["cabang", "kategori"], as_index=False)[ukuran].sum()
    fig = px.bar(ck, x="cabang", y=ukuran, color="kategori", barmode="group",
                 color_discrete_map=WARNA_KATEGORI,
                 title=f"{ukuran_label} cabang × kategori")
    fig.update_layout(bargap=0.25, bargroupgap=0.08)
    c2.plotly_chart(rapikan(fig), width="stretch")

    tr = df.groupby(["periode", "cabang"], as_index=False)[ukuran].sum()
    fig = px.line(tr, x="periode", y=ukuran, color="cabang", markers=True,
                  color_discrete_map=WARNA_CABANG,
                  title=f"Tren {ukuran_label.lower()} per cabang")
    st.plotly_chart(rapikan(fig, 380), width="stretch")

    st.subheader("Tabel ROLLUP cabang × kategori")
    roll = ck.pivot(index="cabang", columns="kategori", values=ukuran).fillna(0)
    roll["Subtotal"] = roll.sum(axis=1)
    roll.loc["SEMUA CABANG"] = roll.sum()
    st.dataframe(roll.style.format("{:,.0f}"), width="stretch")

# ---------------------------------------------------------------- Pelanggan
with tab[3]:
    pa = df.groupby("periode").agg(versi_kasir=("id_pelanggan_sumber", "nunique"),
                                   versi_master=("id_master", "nunique")).reset_index()
    pa = pa.melt("periode", var_name="hitungan", value_name="pelanggan")
    pa["hitungan"] = pa["hitungan"].map({"versi_kasir": "Menurut ID kasir",
                                         "versi_master": "Menurut master ID (MDM)"})
    fig = px.line(pa, x="periode", y="pelanggan", color="hitungan", markers=True,
                  color_discrete_sequence=SLOT[:2],
                  title="Pelanggan aktif per bulan: ID kasir vs master ID (dampak MDM)")
    st.plotly_chart(rapikan(fig, 360), width="stretch")

    c1, c2 = st.columns(2)
    top = (df.groupby(["id_master", "pelanggan", "jenis", "kota"], as_index=False)
             .agg(omzet=("omzet", "sum"), laba=("laba", "sum"),
                  nota=("no_nota", "nunique"),
                  id_kasir=("id_pelanggan_sumber", "nunique"),
                  terakhir=("tanggal", "max"))
             .sort_values("omzet", ascending=False))
    c1.subheader("Pelanggan teratas")
    c1.dataframe(top.head(20), hide_index=True, width="stretch",
                 column_config={
                     "omzet": st.column_config.NumberColumn("Omzet", format="Rp %,.0f"),
                     "laba": st.column_config.NumberColumn("Laba", format="Rp %,.0f"),
                     "terakhir": st.column_config.DateColumn("Transaksi terakhir"),
                 })

    kota = df.groupby("kota", as_index=False).agg(
        pelanggan=("id_master", "nunique"), omzet=("omzet", "sum"))
    fig = px.bar(kota.sort_values("omzet"), x="omzet", y="kota", orientation="h",
                 color_discrete_sequence=[SLOT[0]], hover_data=["pelanggan"],
                 title="Omzet per kota pelanggan (versi terkini)")
    c2.plotly_chart(rapikan(fig, legenda=False), width="stretch")

    st.subheader("Pelanggan dengan lebih dari satu ID kasir (mart.pelanggan_360)")
    p360 = muat_pelanggan_360()
    st.dataframe(p360[p360["jumlah_id_kasir"] > 1]
                 .sort_values("total_belanja", ascending=False),
                 hide_index=True, width="stretch")

# ---------------------------------------------------------------- Pola hari
with tab[4]:
    urutan_hari = (df.groupby("nama_hari")["tanggal"].first()
                     .dt.day_of_week.sort_values().index.tolist())
    c1, c2 = st.columns(2)
    hari = df.groupby(["nama_hari", "jenis"], as_index=False).agg(
        nota=("no_nota", "nunique"))
    fig = px.bar(hari, x="nama_hari", y="nota", color="jenis", barmode="group",
                 category_orders={"nama_hari": urutan_hari},
                 color_discrete_map=WARNA_JENIS,
                 title="Jumlah nota per hari dan jenis pelanggan")
    c1.plotly_chart(rapikan(fig), width="stretch")

    df_h = df.assign(jenis_hari=df["akhir_pekan"].map(
        {True: "Akhir pekan", False: "Hari kerja"}))
    ringkas = df_h.groupby(["jenis", "jenis_hari"]).agg(
        nota=("no_nota", "nunique"), hari=("tanggal", "nunique"),
        rata2_item=("omzet", "mean")).reset_index()
    ringkas["nota_per_hari"] = ringkas["nota"] / ringkas["hari"]
    fig = px.bar(ringkas, x="jenis", y="nota_per_hari", color="jenis_hari",
                 barmode="group", color_discrete_sequence=SLOT[:2],
                 title="Rata-rata nota per hari: hari kerja vs akhir pekan")
    c2.plotly_chart(rapikan(fig), width="stretch")
    st.dataframe(ringkas, hide_index=True, width="stretch",
                 column_config={"rata2_item": st.column_config.NumberColumn(
                     "Rata-rata per item", format="Rp %,.0f"),
                     "nota_per_hari": st.column_config.NumberColumn(format="%.2f")})

# ---------------------------------------------------------------- Eksplorasi
with tab[5]:
    st.write("Pilih dimensi dan ukuran sendiri (slice and dice).")
    dimensi = {"Bulan": "periode", "Tahun": "tahun", "Kuartal": "kuartal",
               "Cabang": "cabang", "Kategori": "kategori", "Produk": "produk",
               "Jenis pelanggan": "jenis", "Kota pelanggan": "kota",
               "Nama hari": "nama_hari"}
    c1, c2, c3 = st.columns(3)
    baris = c1.selectbox("Baris / sumbu X", list(dimensi), index=0)
    warna_dim = c2.selectbox("Pecah warna", ["(tidak ada)"] + list(dimensi), index=4)
    jenis_grafik = c3.selectbox("Grafik", ["Garis", "Batang", "Tabel pivot"])

    kunci = [dimensi[baris]]
    if warna_dim != "(tidak ada)" and dimensi[warna_dim] not in kunci:
        kunci.append(dimensi[warna_dim])
    agg = df.groupby(kunci, as_index=False).agg(
        omzet=("omzet", "sum"), laba=("laba", "sum"), hpp=("hpp", "sum"),
        qty=("qty", "sum"), nota=("no_nota", "nunique"),
        pelanggan_master=("id_master", "nunique"))
    warna_kol = kunci[1] if len(kunci) > 1 else None
    peta = {"cabang": WARNA_CABANG, "kategori": WARNA_KATEGORI,
            "jenis": WARNA_JENIS}.get(warna_kol)
    if warna_kol and agg[warna_kol].nunique() > len(SLOT):
        st.info(f"{warna_kol} punya lebih dari {len(SLOT)} nilai; "
                "tampilkan sebagai tabel pivot agar warna tetap terbaca.")
        jenis_grafik = "Tabel pivot"

    if jenis_grafik == "Tabel pivot":
        if kunci[0] == "periode":  # label teks supaya baris "Total" bisa ditambah
            agg = agg.assign(periode=agg["periode"].dt.strftime("%Y-%m"))
        if warna_kol:
            tabel = agg.pivot_table(index=kunci[0], columns=warna_kol,
                                    values=ukuran, aggfunc="sum", margins=True,
                                    margins_name="Total")
        else:
            tabel = agg.set_index(kunci[0])
        st.dataframe(tabel.style.format("{:,.0f}"), width="stretch")
    else:
        fungsi = px.line if jenis_grafik == "Garis" else px.bar
        arg = dict(markers=True) if jenis_grafik == "Garis" else dict(barmode="group")
        fig = fungsi(agg, x=kunci[0], y=ukuran, color=warna_kol,
                     color_discrete_map=peta, color_discrete_sequence=SLOT,
                     title=f"{ukuran_label} per {baris.lower()}"
                           + (f" × {warna_dim.lower()}" if warna_kol else ""), **arg)
        st.plotly_chart(rapikan(fig, 420, legenda=bool(warna_kol)),
                        width="stretch")

    st.caption("Catatan: pelanggan_master adalah ukuran non-additive. "
               "Jangan dijumlahkan antar baris; omzet dan laba aman dijumlahkan.")
    st.download_button("Unduh hasil (CSV)", agg.to_csv(index=False).encode(),
                       "eksplorasi.csv", "text/csv")
