-- angka acak dikunci supaya hasil semua peserta sama
SELECT setseed(0.42);

CREATE TABLE cabang (
  id_cabang   SERIAL PRIMARY KEY,
  nama_cabang VARCHAR(50) NOT NULL,
  kota        VARCHAR(50)
);
CREATE TABLE kategori (
  id_kategori   SERIAL PRIMARY KEY,
  nama_kategori VARCHAR(50) NOT NULL
);
CREATE TABLE produk (
  id_produk   SERIAL PRIMARY KEY,
  nama_produk VARCHAR(100) NOT NULL,
  id_kategori INT REFERENCES kategori(id_kategori),
  satuan      VARCHAR(20),
  harga_beli  NUMERIC(12,2),
  harga_jual  NUMERIC(12,2)
);
CREATE TABLE pelanggan (
  id_pelanggan SERIAL PRIMARY KEY,
  nama         VARCHAR(100) NOT NULL,
  jenis        VARCHAR(20),
  kota         VARCHAR(50),
  telepon      VARCHAR(20),
  tgl_daftar   DATE
);
CREATE TABLE penjualan (
  id_penjualan  SERIAL PRIMARY KEY,
  no_nota       VARCHAR(20) UNIQUE NOT NULL,
  tgl_penjualan TIMESTAMP NOT NULL,
  id_pelanggan  INT REFERENCES pelanggan(id_pelanggan),
  id_cabang     INT REFERENCES cabang(id_cabang)
);
CREATE TABLE detail_penjualan (
  id_detail    SERIAL PRIMARY KEY,
  id_penjualan INT REFERENCES penjualan(id_penjualan),
  id_produk    INT REFERENCES produk(id_produk),
  qty          INT NOT NULL,
  harga_satuan NUMERIC(12,2) NOT NULL,
  diskon       NUMERIC(12,2) DEFAULT 0
);

INSERT INTO cabang (nama_cabang, kota) VALUES
  ('Cabang Pusat','Jayapura'), ('Cabang Abepura','Jayapura'),
  ('Cabang Sentani','Kab. Jayapura');
INSERT INTO kategori (nama_kategori) VALUES
  ('Minyak'), ('Gula'), ('Tepung'), ('Beras'), ('Plastik');
INSERT INTO produk (nama_produk, id_kategori, satuan, harga_beli, harga_jual) VALUES
  ('minyak goreng 1 liter', 1, 'pouch', 15500, 17500),
  ('minyak goreng 2 liter', 1, 'pouch', 30500, 34000),
  ('gula pasir 1 kg', 2, 'kg', 16000, 18000),
  ('gula merah 500 gr', 2, 'pak', 9000, 11000),
  ('tepung terigu 1 kg', 3, 'kg', 11000, 13000),
  ('tepung beras 500 gr', 3, 'pak', 7000, 8500),
  ('beras medium 5 kg', 4, 'karung', 62000, 69000),
  ('beras premium 5 kg', 4, 'karung', 72000, 80000),
  ('kantong plastik 1 pak', 5, 'pak', 8000, 10000),
  ('plastik klip 1 pak', 5, 'pak', 5000, 6500);

-- 180 pelanggan
INSERT INTO pelanggan (nama, jenis, kota, telepon, tgl_daftar)
SELECT (ARRAY['Toko','Kios','Warung','UD','CV','Toko'])[1 + (g-1) % 6]
       || ' ' ||
       (ARRAY['Abadi','Amanah','Anugerah','Bahagia','Barokah','Berkah',
              'Bintang','Cahaya','Damai','Harapan','Indah','Jaya',
              'Karya','Lestari','Maju','Makmur','Mandiri','Mulia',
              'Murni','Nusantara','Permata','Rejeki','Sejahtera',
              'Sentosa','Setia','Subur','Sumber','Surya','Tunas',
              'Utama'])[1 + (g-1) / 6],
       CASE WHEN g % 10 IN (0,3,7) THEN 'Grosir' ELSE 'Retail' END,
       CASE WHEN g % 5 = 0 THEN NULL
            ELSE (ARRAY['Jayapura','Sentani','Abepura','Waena'])[1 + g % 4] END,
       CASE WHEN g % 13 = 0 THEN NULL
            ELSE '08' || (11 + g % 9)
                 || lpad((g * 104729 % 100000000)::text, 8, '0') END,
       DATE '2024-01-01' + (g * 3) % 600
FROM generate_series(1, 180) g;

-- 20 pelanggan lama yang didaftarkan ulang di cabang lain
INSERT INTO pelanggan (nama, jenis, kota, telepon, tgl_daftar)
SELECT CASE WHEN p.id_pelanggan % 2 = 0 THEN upper(p.nama)
            ELSE replace(p.nama, 'Toko ', 'Tk. ') END,
       p.jenis, p.kota,
       '+62 ' || substr(p.telepon, 2, 3) || '-' || substr(p.telepon, 5),
       p.tgl_daftar + 200
FROM pelanggan p
WHERE p.id_pelanggan % 9 = 0
ORDER BY p.id_pelanggan;

INSERT INTO penjualan (no_nota, tgl_penjualan, id_pelanggan, id_cabang)
SELECT 'NT' || lpad(g::text, 6, '0'),
       TIMESTAMP '2025-01-01 07:00'
         + floor(random() * 669)::int * INTERVAL '1 day'
         + floor(random() * 13)::int * INTERVAL '1 hour',
       1 + floor(random() * 200)::int,
       1 + floor(random() * 3)::int
FROM generate_series(1, 5000) g;

-- setiap nota mendapat rata-rata 2-3 produk acak
INSERT INTO detail_penjualan (id_penjualan, id_produk, qty, harga_satuan, diskon)
SELECT p.id_penjualan, pr.id_produk, pr.qty, pr.harga_jual, pr.diskon
FROM penjualan p
CROSS JOIN LATERAL (
  SELECT id_produk, harga_jual,
         1 + floor(random() * 10)::int AS qty,
         CASE WHEN random() < 0.1 THEN 2000 ELSE 0 END AS diskon
  FROM produk
  WHERE random() < 0.25 AND p.id_penjualan > 0
) pr
ORDER BY p.id_penjualan, pr.id_produk;
