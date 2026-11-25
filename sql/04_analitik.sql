-- Q1 Penjualan dan laba per bulan
SELECT w.tahun, w.bulan, w.nama_bulan,
       SUM(f.total_penjualan) AS omzet,
       SUM(f.laba_kotor)      AS laba
FROM fakta_penjualan f
JOIN dim_waktu w ON w.id_waktu = f.id_waktu
GROUP BY w.tahun, w.bulan, w.nama_bulan
ORDER BY w.tahun, w.bulan;
 
-- Q2 Top 5 produk berdasarkan laba
SELECT p.nama_produk, p.kategori,
       SUM(f.qty) AS qty_terjual,
       SUM(f.laba_kotor) AS laba
FROM fakta_penjualan f
JOIN dim_produk p ON p.sk_produk = f.sk_produk
GROUP BY p.nama_produk, p.kategori
ORDER BY laba DESC
LIMIT 5;
 
-- Q3 Omzet cabang x kategori dengan subtotal (ROLLUP)
SELECT COALESCE(c.nama_cabang, 'SEMUA CABANG') AS cabang,
       COALESCE(p.kategori, 'Subtotal')        AS kategori,
       SUM(f.total_penjualan)                  AS omzet
FROM fakta_penjualan f
JOIN dim_cabang c ON c.sk_cabang = f.sk_cabang
JOIN dim_produk p ON p.sk_produk = f.sk_produk
GROUP BY ROLLUP (c.nama_cabang, p.kategori)
ORDER BY c.nama_cabang NULLS LAST, p.kategori NULLS LAST;
 
-- Q4 Pertumbuhan omzet bulan ke bulan (window function)
WITH bulanan AS (
  SELECT w.tahun, w.bulan, SUM(f.total_penjualan) AS omzet
  FROM fakta_penjualan f
  JOIN dim_waktu w ON w.id_waktu = f.id_waktu
  GROUP BY w.tahun, w.bulan
)
SELECT tahun, bulan, omzet,
       LAG(omzet) OVER (ORDER BY tahun, bulan) AS omzet_bulan_lalu,
       ROUND(100.0 * (omzet - LAG(omzet) OVER (ORDER BY tahun, bulan))
             / NULLIF(LAG(omzet) OVER (ORDER BY tahun, bulan), 0), 1) AS tumbuh_persen
FROM bulanan
ORDER BY tahun, bulan;
 
-- Q5 Pivot omzet per kuartal per kategori, tahun 2025
SELECT p.kategori,
       SUM(f.total_penjualan) FILTER (WHERE w.kuartal = 1) AS q1,
       SUM(f.total_penjualan) FILTER (WHERE w.kuartal = 2) AS q2,
       SUM(f.total_penjualan) FILTER (WHERE w.kuartal = 3) AS q3,
       SUM(f.total_penjualan) FILTER (WHERE w.kuartal = 4) AS q4
FROM fakta_penjualan f
JOIN dim_waktu  w ON w.id_waktu  = f.id_waktu
JOIN dim_produk p ON p.sk_produk = f.sk_produk
WHERE w.tahun = 2025
GROUP BY p.kategori
ORDER BY p.kategori;
 
-- Q6 Hari kerja vs akhir pekan per jenis pelanggan
SELECT pl.jenis,
       CASE WHEN w.akhir_pekan THEN 'Akhir pekan' ELSE 'Hari kerja' END AS jenis_hari,
       COUNT(DISTINCT f.no_nota) AS jumlah_nota,
       ROUND(AVG(f.total_penjualan), 0) AS rata2_per_item
FROM fakta_penjualan f
JOIN dim_waktu     w  ON w.id_waktu      = f.id_waktu
JOIN dim_pelanggan pl ON pl.sk_pelanggan = f.sk_pelanggan
GROUP BY pl.jenis, jenis_hari
ORDER BY pl.jenis, jenis_hari;

-- Q7 Dampak MDM: jumlah pelanggan menurut ID kasir dan menurut master ID
SELECT COUNT(DISTINCT f.id_pelanggan_sumber) AS pelanggan_versi_kasir,
       COUNT(DISTINCT dp.id_master)         AS pelanggan_versi_master
FROM fakta_penjualan f
JOIN dim_pelanggan dp ON dp.sk_pelanggan = f.sk_pelanggan;

-- Q8 Pelanggan yang tercatat dengan lebih dari satu ID kasir
SELECT id_master, nama, kota, jumlah_id_kasir, jumlah_nota, total_belanja
FROM mart.pelanggan_360
WHERE jumlah_id_kasir > 1
ORDER BY total_belanja DESC
LIMIT 5;
