-- data mart penjualan bulanan untuk dashboard
CREATE MATERIALIZED VIEW mart.penjualan_bulanan AS
SELECT w.tahun, w.bulan, w.nama_bulan, c.nama_cabang, p.kategori,
       COUNT(DISTINCT f.no_nota)   AS jumlah_nota,
       COUNT(DISTINCT dp.id_master) AS pelanggan_aktif,
       SUM(f.qty)                  AS qty,
       SUM(f.total_penjualan)      AS omzet,
       SUM(f.laba_kotor)           AS laba
FROM dw.fakta_penjualan f
JOIN dw.dim_waktu w      ON w.id_waktu = f.id_waktu
JOIN dw.dim_cabang c     ON c.sk_cabang = f.sk_cabang
JOIN dw.dim_produk p     ON p.sk_produk = f.sk_produk
JOIN dw.dim_pelanggan dp ON dp.sk_pelanggan = f.sk_pelanggan
GROUP BY w.tahun, w.bulan, w.nama_bulan, c.nama_cabang, p.kategori;

-- data mart profil pelanggan (satu baris per pelanggan master)
CREATE MATERIALIZED VIEW mart.pelanggan_360 AS
SELECT dp.id_master, cur.nama, cur.jenis, cur.kota,
       COUNT(DISTINCT f.no_nota)              AS jumlah_nota,
       SUM(f.total_penjualan)                 AS total_belanja,
       MAX(w.tanggal)                         AS transaksi_terakhir,
       COUNT(DISTINCT f.id_pelanggan_sumber)  AS jumlah_id_kasir
FROM dw.fakta_penjualan f
JOIN dw.dim_pelanggan dp  ON dp.sk_pelanggan = f.sk_pelanggan
JOIN dw.dim_pelanggan cur ON cur.id_master = dp.id_master AND cur.is_current
JOIN dw.dim_waktu w       ON w.id_waktu = f.id_waktu
GROUP BY dp.id_master, cur.nama, cur.jenis, cur.kota;

GRANT SELECT ON ALL TABLES IN SCHEMA mart TO bi_user;
