"""ETL toko: kasir + CRM -> staging -> MDM -> star schema -> mart.

Pemakaian:
  python etl.py                  jalankan semua tahap
  python etl.py --sampai extract berhenti setelah staging
  python etl.py --sampai mdm     berhenti setelah MDM hub
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

BASE = "postgresql+psycopg://etl_user:EtlPass123@localhost:5432/"
kasir = create_engine(os.getenv("KASIR_URL", BASE + "toko_oltp"))
crm = create_engine(os.getenv("CRM_URL", BASE + "toko_crm"))
dw = create_engine(os.getenv("DW_URL", BASE + "toko_dw"))
FOLDER = Path(__file__).resolve().parent
TAHAP = ["extract", "validasi", "mdm", "load", "mart"]


def log(pesan):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {pesan}", flush=True)


def sql(conn, perintah, **param):
    return conn.execute(text(perintah), param)


# ---------- TAHAP 1-2: EXTRACT KE STAGING ----------
def extract(conn, batch):
    wm = dict(sql(conn, "SELECT sumber, nilai_terakhir FROM audit.watermark").all())
    tabel = {
        "kasir_cabang": pd.read_sql("SELECT * FROM cabang", kasir),
        "kasir_produk": pd.read_sql(
            "SELECT p.*, k.nama_kategori FROM produk p "
            "JOIN kategori k ON k.id_kategori = p.id_kategori", kasir),
        "kasir_pelanggan": pd.read_sql("SELECT * FROM pelanggan", kasir),
        "crm_member": pd.read_sql("SELECT * FROM member", crm),
        "kasir_penjualan": pd.read_sql(
            text("SELECT * FROM penjualan WHERE id_penjualan > :w"), kasir,
            params={"w": wm["kasir.penjualan"]}),
        "kasir_detail": pd.read_sql(
            text("SELECT * FROM detail_penjualan WHERE id_detail > :w"), kasir,
            params={"w": wm["kasir.detail_penjualan"]}),
    }
    total = 0
    for nama, df in tabel.items():
        df["batch_id"] = batch
        df["diambil_pada"] = datetime.now()
        if df.empty and sql(conn, "SELECT to_regclass(:t)", t=f"stg.{nama}").scalar():
            sql(conn, f"TRUNCATE stg.{nama}")  # kosongkan, tipe kolom tetap
        else:
            df.to_sql(nama, conn, schema="stg", if_exists="replace", index=False)
        log(f"stg.{nama:<16}: {len(df)} baris")
        total += len(df)
    return total


# ---------- TAHAP 3: VALIDASI, NILAI DITOLAK MASUK audit.reject ----------
def validasi(conn, batch):
    n = sql(conn, """
        INSERT INTO audit.reject (batch_id, sumber, id_sumber, alasan)
        SELECT :b, 'kasir.detail_penjualan', id_detail::text,
               CASE WHEN qty <= 0 THEN 'qty <= 0' ELSE 'harga_satuan <= 0' END
        FROM stg.kasir_detail s WHERE (qty <= 0 OR harga_satuan <= 0)
          AND NOT EXISTS (SELECT 1 FROM audit.reject r
                          WHERE r.sumber = 'kasir.detail_penjualan'
                            AND r.id_sumber = s.id_detail::text)""", b=batch).rowcount
    n += sql(conn, """
        INSERT INTO audit.reject (batch_id, sumber, id_sumber, alasan)
        SELECT :b, 'kasir.penjualan', j.no_nota, 'nota tanpa detail'
        FROM stg.kasir_penjualan j
        WHERE NOT EXISTS (SELECT 1 FROM stg.kasir_detail d
                          WHERE d.id_penjualan = j.id_penjualan)
          AND NOT EXISTS (SELECT 1 FROM audit.reject r
                          WHERE r.sumber = 'kasir.penjualan'
                            AND r.id_sumber = j.no_nota)""", b=batch).rowcount
    log(f"audit.reject     : {n} baris ditolak")
    return n


# ---------- MDM HUB: MATCH, MERGE, PUBLISH ----------
def mdm(conn, batch):
    skrip = (FOLDER / "sql" / "06_mdm.sql").read_text()
    conn.connection.driver_connection.execute(skrip)  # jalankan file SQL apa adanya
    master, xref = sql(conn, """
        SELECT (SELECT count(*) FROM mdm.golden_pelanggan),
               (SELECT count(*) FROM mdm.xref_pelanggan)""").one()
    log(f"mdm              : {xref} record sumber -> {master} pelanggan master")


# ---------- TAHAP 3-4: TRANSFORM DAN LOAD KE STAR SCHEMA ----------
def load(conn, batch):
    sql(conn, """
        INSERT INTO dw.dim_cabang (id_cabang, nama_cabang, kota)
        SELECT id_cabang, nama_cabang, kota FROM stg.kasir_cabang
        ON CONFLICT (id_cabang) DO UPDATE SET
          nama_cabang = EXCLUDED.nama_cabang, kota = EXCLUDED.kota""")
    sql(conn, """
        INSERT INTO dw.dim_produk
          (id_produk, nama_produk, kategori, satuan, harga_beli)
        SELECT id_produk, initcap(trim(nama_produk)), nama_kategori,
               satuan, harga_beli
        FROM stg.kasir_produk
        ON CONFLICT (id_produk) DO UPDATE SET
          nama_produk = EXCLUDED.nama_produk, kategori = EXCLUDED.kategori,
          satuan = EXCLUDED.satuan, harga_beli = EXCLUDED.harga_beli""")
    # SCD tipe 2 untuk pelanggan
    sql(conn, """
        UPDATE dw.dim_pelanggan d SET nama = g.nama, jenis = g.jenis, kota = g.kota
        FROM mdm.golden_pelanggan g
        WHERE d.id_master = g.id_master AND d.is_current
          AND d.berlaku_mulai = current_date
          AND (d.nama, d.jenis, d.kota)
              IS DISTINCT FROM (g.nama, g.jenis, g.kota)""")
    tutup = sql(conn, """
        UPDATE dw.dim_pelanggan d
        SET berlaku_sampai = current_date - 1, is_current = false
        FROM mdm.golden_pelanggan g
        WHERE d.id_master = g.id_master AND d.is_current
          AND (d.nama, d.jenis, d.kota)
              IS DISTINCT FROM (g.nama, g.jenis, g.kota)""").rowcount
    baru = sql(conn, """
        INSERT INTO dw.dim_pelanggan (id_master, nama, jenis, kota, berlaku_mulai)
        SELECT g.id_master, g.nama, g.jenis, g.kota,
               CASE WHEN EXISTS (SELECT 1 FROM dw.dim_pelanggan x
                                 WHERE x.id_master = g.id_master)
                    THEN current_date ELSE DATE '2024-01-01' END
        FROM mdm.golden_pelanggan g
        WHERE NOT EXISTS (SELECT 1 FROM dw.dim_pelanggan d
                          WHERE d.id_master = g.id_master AND d.is_current)
        ORDER BY g.id_master""").rowcount
    log(f"dim_pelanggan    : {baru} versi baru, {tutup} versi lama ditutup")
    n = sql(conn, """
        INSERT INTO dw.fakta_penjualan
          (id_detail, no_nota, id_waktu, sk_produk, sk_pelanggan, sk_cabang,
           id_pelanggan_sumber, qty, total_penjualan, total_hpp, laba_kotor, batch_id)
        SELECT d.id_detail, j.no_nota, to_char(j.tgl_penjualan, 'YYYYMMDD')::int,
               p.sk_produk, dp.sk_pelanggan, c.sk_cabang, j.id_pelanggan, d.qty,
               d.qty * d.harga_satuan - d.diskon,
               d.qty * p.harga_beli,
               d.qty * d.harga_satuan - d.diskon - d.qty * p.harga_beli,
               :b
        FROM stg.kasir_detail d
        JOIN stg.kasir_penjualan j ON j.id_penjualan = d.id_penjualan
        JOIN dw.dim_produk p ON p.id_produk = d.id_produk
        JOIN dw.dim_cabang c ON c.id_cabang = j.id_cabang
        JOIN mdm.xref_pelanggan x
          ON x.sistem = 'KASIR' AND x.id_sumber = j.id_pelanggan::text
        JOIN dw.dim_pelanggan dp ON dp.id_master = x.id_master
         AND j.tgl_penjualan::date BETWEEN dp.berlaku_mulai AND dp.berlaku_sampai
        WHERE d.qty > 0 AND d.harga_satuan > 0
        ON CONFLICT (id_detail) DO NOTHING""", b=batch).rowcount
    log(f"fakta_penjualan  : {n} baris baru dimuat")
    sql(conn, """
        UPDATE audit.watermark w SET nilai_terakhir = s.maks
        FROM (SELECT 'kasir.penjualan' AS sumber, max(id_penjualan) AS maks
              FROM stg.kasir_penjualan
              UNION ALL
              SELECT 'kasir.detail_penjualan', max(id_detail) FROM stg.kasir_detail) s
        WHERE w.sumber = s.sumber AND s.maks IS NOT NULL""")
    return n


# ---------- TAHAP 5: REFRESH DATA MART ----------
def mart(conn, batch):
    mv = sql(conn, "SELECT matviewname FROM pg_matviews "
                   "WHERE schemaname = 'mart'").scalars().all()
    for nama in mv:
        conn.exec_driver_sql(f"REFRESH MATERIALIZED VIEW mart.{nama}")
    log(f"mart             : {len(mv)} materialized view di-refresh")


def main():
    sampai = "mart"
    if "--sampai" in sys.argv:
        sampai = sys.argv[sys.argv.index("--sampai") + 1]
    with dw.begin() as conn:
        batch = sql(conn, "INSERT INTO audit.etl_batch (status) VALUES ('JALAN') "
                          "RETURNING batch_id").scalar()
    log(f"=== ETL batch {batch} mulai ===")
    hasil = {"staging": None, "reject": None, "fakta": None}
    try:
        # satu transaksi: gagal di tengah berarti tidak ada yang tersimpan
        with dw.begin() as conn:
            for tahap in TAHAP[:TAHAP.index(sampai) + 1]:
                n = globals()[tahap](conn, batch)
                if tahap == "extract":
                    hasil["staging"] = n
                elif tahap == "validasi":
                    hasil["reject"] = n
                elif tahap == "load":
                    hasil["fakta"] = n
        status, pesan = "SUKSES", f"sampai tahap {sampai}"
    except Exception as e:
        status, pesan = "GAGAL", str(e)[:500]
        log(f"ETL GAGAL: {e}")
    with dw.begin() as conn:
        sql(conn, """UPDATE audit.etl_batch
                     SET selesai = now(), status = :s, pesan = :p,
                         baris_staging = :st, baris_reject = :r, baris_fakta = :f
                     WHERE batch_id = :b""",
            s=status, p=pesan, st=hasil["staging"], r=hasil["reject"],
            f=hasil["fakta"], b=batch)
    log(f"=== ETL batch {batch} {status} ===")
    sys.exit(0 if status == "SUKSES" else 1)


if __name__ == "__main__":
    main()
