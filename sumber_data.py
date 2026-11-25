"""Sumber data dashboard: database toko_dw, atau snapshot CSV di folder data/.

Database dipakai bila bisa dihubungi (laptop praktikum). Di server deploy
(misalnya Streamlit Community Cloud) database lokal tidak terjangkau, jadi
dashboard membaca snapshot yang dibuat dengan:

  venv/bin/python sumber_data.py
"""
import os
from pathlib import Path

import pandas as pd

DB_URL = os.getenv(
    "BI_URL", "postgresql+psycopg://bi_user:BiPass123@localhost:5432/toko_dw")
FOLDER = Path(__file__).resolve().parent / "data"

QUERY = {
    "fakta": """
        SELECT f.no_nota, w.tanggal, w.tahun, w.bulan, w.kuartal, w.nama_hari,
               w.akhir_pekan, c.nama_cabang AS cabang, p.nama_produk AS produk,
               p.kategori, dp.id_master, cur.nama AS pelanggan,
               cur.jenis, cur.kota, f.id_pelanggan_sumber,
               f.qty, f.total_penjualan AS omzet, f.total_hpp AS hpp,
               f.laba_kotor AS laba
        FROM dw.fakta_penjualan f
        JOIN dw.dim_waktu w      ON w.id_waktu = f.id_waktu
        JOIN dw.dim_cabang c     ON c.sk_cabang = f.sk_cabang
        JOIN dw.dim_produk p     ON p.sk_produk = f.sk_produk
        JOIN dw.dim_pelanggan dp ON dp.sk_pelanggan = f.sk_pelanggan
        JOIN dw.dim_pelanggan cur ON cur.id_master = dp.id_master AND cur.is_current
        ORDER BY f.id_detail""",
    "pelanggan_360": "SELECT * FROM mart.pelanggan_360 ORDER BY id_master",
}


def _engine():
    from sqlalchemy import create_engine
    return create_engine(DB_URL, connect_args={"connect_timeout": 3})


def baca(nama):
    """Kembalikan (DataFrame, asal) dengan asal 'database' atau 'snapshot'."""
    if os.getenv("DATA_SOURCE") != "snapshot":
        try:
            return pd.read_sql(QUERY[nama], _engine()), "database"
        except Exception:  # noqa: BLE001 - database tidak terjangkau
            pass
    return pd.read_csv(FOLDER / f"{nama}.csv.gz"), "snapshot"


def ekspor():
    FOLDER.mkdir(exist_ok=True)
    for nama, q in QUERY.items():
        df = pd.read_sql(q, _engine())
        df.to_csv(FOLDER / f"{nama}.csv.gz", index=False)
        print(f"data/{nama}.csv.gz: {len(df)} baris")


if __name__ == "__main__":
    ekspor()
