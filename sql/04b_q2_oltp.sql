-- Q2 versi OLTP (toko_oltp): butuh 3-4 join + hitung laba manual
EXPLAIN ANALYZE
SELECT initcap(pr.nama_produk) AS nama_produk, k.nama_kategori AS kategori,
       SUM(d.qty) AS qty_terjual,
       SUM(d.qty * d.harga_satuan - d.diskon - d.qty * pr.harga_beli) AS laba
FROM detail_penjualan d
JOIN penjualan j ON j.id_penjualan = d.id_penjualan
JOIN produk pr   ON pr.id_produk = d.id_produk
JOIN kategori k  ON k.id_kategori = pr.id_kategori
WHERE d.qty > 0 AND d.harga_satuan > 0
GROUP BY pr.nama_produk, k.nama_kategori
ORDER BY laba DESC LIMIT 5;
