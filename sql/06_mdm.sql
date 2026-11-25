-- 1. Kumpulkan pelanggan dari kasir dan CRM, lalu standarkan
CREATE TEMP TABLE pelanggan_sumber AS
SELECT 'KASIR' AS sistem, id_pelanggan::text AS id_sumber,
       nama, telepon, kota, jenis, tgl_daftar::date AS tgl, 2 AS prioritas
FROM stg.kasir_pelanggan
UNION ALL
SELECT 'CRM', id_member, nama_member, no_hp, kota, segmen, diperbarui::date, 1
FROM stg.crm_member;

UPDATE pelanggan_sumber SET
  nama = regexp_replace(regexp_replace(regexp_replace(
           initcap(trim(nama)), '^Tk\.? ', 'Toko '), '^Ud ', 'UD '), '^Cv ', 'CV '),
  telepon = regexp_replace(coalesce(telepon, ''), '\D', '', 'g');
UPDATE pelanggan_sumber SET telepon = CASE
  WHEN telepon LIKE '62%' THEN '0' || substr(telepon, 3)
  WHEN telepon LIKE '8%'  THEN '0' || telepon
  ELSE telepon END;
UPDATE pelanggan_sumber SET telepon = NULL WHERE telepon !~ '^08[0-9]{8,11}$';

-- 2. Match: telepon yang sama berarti pelanggan yang sama
ALTER TABLE pelanggan_sumber ADD kunci_match VARCHAR(40);
UPDATE pelanggan_sumber
SET kunci_match = coalesce(telepon, sistem || ':' || id_sumber);

-- 3. Merge: pilih nilai terbaik per atribut (survivorship)
INSERT INTO mdm.golden_pelanggan
  (kunci_match, nama, telepon, jenis, kota, jumlah_sumber, sumber_nama)
SELECT kunci_match,
       (array_agg(nama ORDER BY prioritas, tgl))[1],
       max(telepon),
       (array_agg(jenis ORDER BY prioritas, tgl DESC)
          FILTER (WHERE jenis IS NOT NULL))[1],
       coalesce((array_agg(kota ORDER BY prioritas, tgl DESC)
          FILTER (WHERE kota IS NOT NULL))[1], 'Tidak Diketahui'),
       count(*),
       (array_agg(sistem || ':' || id_sumber ORDER BY prioritas, tgl))[1]
FROM pelanggan_sumber
GROUP BY kunci_match
ORDER BY min(tgl), kunci_match
ON CONFLICT (kunci_match) DO UPDATE SET
  nama = EXCLUDED.nama, telepon = EXCLUDED.telepon,
  jenis = EXCLUDED.jenis, kota = EXCLUDED.kota,
  jumlah_sumber = EXCLUDED.jumlah_sumber,
  sumber_nama = EXCLUDED.sumber_nama, diperbarui = now()
WHERE (mdm.golden_pelanggan.nama, mdm.golden_pelanggan.jenis,
       mdm.golden_pelanggan.kota, mdm.golden_pelanggan.jumlah_sumber)
  IS DISTINCT FROM
      (EXCLUDED.nama, EXCLUDED.jenis, EXCLUDED.kota, EXCLUDED.jumlah_sumber);

-- 4. Publish: crosswalk ID sumber ke master ID
INSERT INTO mdm.xref_pelanggan (sistem, id_sumber, id_master, kunci_match)
SELECT s.sistem, s.id_sumber, g.id_master, s.kunci_match
FROM pelanggan_sumber s
JOIN mdm.golden_pelanggan g ON g.kunci_match = s.kunci_match
ON CONFLICT (sistem, id_sumber) DO UPDATE SET
  id_master = EXCLUDED.id_master, kunci_match = EXCLUDED.kunci_match;
