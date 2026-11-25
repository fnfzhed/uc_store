-- lima skema sesuai tahap alur data warehouse
CREATE SCHEMA stg;    -- tahap 2: staging, salinan mentah dari sumber
CREATE SCHEMA mdm;    -- MDM hub: golden record dan crosswalk
CREATE SCHEMA dw;     -- tahap 4: star schema
CREATE SCHEMA mart;   -- tahap 5: data mart untuk pengguna bisnis
CREATE SCHEMA audit;  -- governance: log batch, reject, watermark
ALTER DATABASE toko_dw SET search_path TO dw, mart, public;
SET search_path TO dw;

CREATE TABLE dim_waktu (
  id_waktu    INT PRIMARY KEY,
  tanggal     DATE NOT NULL,
  hari        SMALLINT,
  nama_hari   VARCHAR(10),
  minggu      SMALLINT,
  bulan       SMALLINT,
  nama_bulan  VARCHAR(10),
  kuartal     SMALLINT,
  tahun       SMALLINT,
  akhir_pekan BOOLEAN
);
CREATE TABLE dim_produk (
  sk_produk   SERIAL PRIMARY KEY,
  id_produk   INT UNIQUE NOT NULL,
  nama_produk VARCHAR(100),
  kategori    VARCHAR(50),
  satuan      VARCHAR(20),
  harga_beli  NUMERIC(12,2)
);
-- SCD tipe 2: satu pelanggan master bisa punya beberapa versi
CREATE TABLE dim_pelanggan (
  sk_pelanggan   SERIAL PRIMARY KEY,
  id_master      VARCHAR(12) NOT NULL,
  nama           VARCHAR(100),
  jenis          VARCHAR(20),
  kota           VARCHAR(50),
  berlaku_mulai  DATE NOT NULL,
  berlaku_sampai DATE NOT NULL DEFAULT DATE '9999-12-31',
  is_current     BOOLEAN NOT NULL DEFAULT true
);
CREATE UNIQUE INDEX uq_pelanggan_current
  ON dim_pelanggan(id_master) WHERE is_current;
CREATE TABLE dim_cabang (
  sk_cabang   SERIAL PRIMARY KEY,
  id_cabang   INT UNIQUE NOT NULL,
  nama_cabang VARCHAR(50),
  kota        VARCHAR(50)
);
CREATE TABLE fakta_penjualan (
  id_fakta            BIGSERIAL PRIMARY KEY,
  id_detail           INT UNIQUE NOT NULL,
  no_nota             VARCHAR(20),
  id_waktu            INT REFERENCES dim_waktu(id_waktu),
  sk_produk           INT REFERENCES dim_produk(sk_produk),
  sk_pelanggan        INT REFERENCES dim_pelanggan(sk_pelanggan),
  sk_cabang           INT REFERENCES dim_cabang(sk_cabang),
  id_pelanggan_sumber INT,   -- lineage: ID pelanggan di kasir
  qty                 INT,
  total_penjualan     NUMERIC(14,2),
  total_hpp           NUMERIC(14,2),
  laba_kotor          NUMERIC(14,2),
  batch_id            INT    -- lineage: batch ETL yang memuat
);
CREATE INDEX idx_fakta_waktu     ON fakta_penjualan(id_waktu);
CREATE INDEX idx_fakta_produk    ON fakta_penjualan(sk_produk);
CREATE INDEX idx_fakta_pelanggan ON fakta_penjualan(sk_pelanggan);
CREATE INDEX idx_fakta_cabang    ON fakta_penjualan(sk_cabang);

-- dim_waktu diisi sekali untuk 3 tahun (2025-2027)
INSERT INTO dim_waktu
SELECT to_char(d, 'YYYYMMDD')::int, d::date,
       EXTRACT(ISODOW FROM d),
       (ARRAY['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu',
              'Minggu'])[EXTRACT(ISODOW FROM d)::int],
       EXTRACT(WEEK FROM d), EXTRACT(MONTH FROM d),
       (ARRAY['Januari','Februari','Maret','April','Mei','Juni','Juli',
              'Agustus','September','Oktober','November',
              'Desember'])[EXTRACT(MONTH FROM d)::int],
       EXTRACT(QUARTER FROM d), EXTRACT(YEAR FROM d),
       EXTRACT(ISODOW FROM d) IN (6, 7)
FROM generate_series(DATE '2025-01-01', DATE '2027-12-31', INTERVAL '1 day') d;

-- MDM hub
CREATE SEQUENCE mdm.seq_master;
CREATE TABLE mdm.golden_pelanggan (
  id_master     VARCHAR(12) PRIMARY KEY
                DEFAULT 'PLG-' || lpad(nextval('mdm.seq_master')::text, 5, '0'),
  kunci_match   VARCHAR(40) UNIQUE NOT NULL,
  nama          VARCHAR(100),
  telepon       VARCHAR(20),
  jenis         VARCHAR(20),
  kota          VARCHAR(50),
  jumlah_sumber INT,
  sumber_nama   VARCHAR(30),
  diperbarui    TIMESTAMP DEFAULT now()
);
CREATE TABLE mdm.xref_pelanggan (
  sistem      VARCHAR(10),
  id_sumber   VARCHAR(20),
  id_master   VARCHAR(12) REFERENCES mdm.golden_pelanggan(id_master),
  kunci_match VARCHAR(40),
  PRIMARY KEY (sistem, id_sumber)
);

-- governance
CREATE TABLE audit.etl_batch (
  batch_id      SERIAL PRIMARY KEY,
  mulai         TIMESTAMP DEFAULT now(),
  selesai       TIMESTAMP,
  status        VARCHAR(10),
  baris_staging INT,
  baris_reject  INT,
  baris_fakta   INT,
  pesan         TEXT
);
CREATE TABLE audit.reject (
  id        BIGSERIAL PRIMARY KEY,
  batch_id  INT,
  sumber    VARCHAR(40),
  id_sumber VARCHAR(30),
  alasan    VARCHAR(100),
  dicatat   TIMESTAMP DEFAULT now()
);
CREATE TABLE audit.watermark (
  sumber         VARCHAR(40) PRIMARY KEY,
  nilai_terakhir BIGINT NOT NULL
);
INSERT INTO audit.watermark VALUES
  ('kasir.penjualan', 0), ('kasir.detail_penjualan', 0);

-- bi_user hanya membaca dw dan mart
GRANT CONNECT ON DATABASE toko_dw TO bi_user;
GRANT USAGE ON SCHEMA dw, mart TO bi_user;
GRANT SELECT ON ALL TABLES IN SCHEMA dw TO bi_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA dw, mart GRANT SELECT ON TABLES TO bi_user;
