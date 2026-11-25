INSERT INTO penjualan (no_nota, tgl_penjualan, id_pelanggan, id_cabang)
VALUES ('NT900001', now(), 1, 1);
INSERT INTO detail_penjualan (id_penjualan, id_produk, qty, harga_satuan, diskon)
SELECT id_penjualan, 7, 3, 69000, 0 FROM penjualan WHERE no_nota = 'NT900001';
INSERT INTO detail_penjualan (id_penjualan, id_produk, qty, harga_satuan, diskon)
SELECT id_penjualan, 1, 0, 17500, 0 FROM penjualan WHERE no_nota = 'NT900001';
