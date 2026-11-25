-- aplikasi member (CRM): sumber kedua data pelanggan
CREATE TABLE member (
  id_member   VARCHAR(10) PRIMARY KEY,
  nama_member VARCHAR(100),
  no_hp       VARCHAR(20) NOT NULL,
  kota        VARCHAR(50),
  segmen      VARCHAR(20),
  poin        INT,
  diperbarui  DATE
);

INSERT INTO member
SELECT 'M' || lpad(g::text, 4, '0'),
       upper((ARRAY['Toko','Kios','Warung','UD','CV','Toko'])[1 + (g-1) % 6])
       || ' ' ||
       (ARRAY['Abadi','Amanah','Anugerah','Bahagia','Barokah','Berkah',
              'Bintang','Cahaya','Damai','Harapan','Indah','Jaya',
              'Karya','Lestari','Maju','Makmur','Mandiri','Mulia',
              'Murni','Nusantara','Permata','Rejeki','Sejahtera',
              'Sentosa','Setia','Subur','Sumber','Surya','Tunas',
              'Utama','Baru','Lancar'])[1 + (g-1) / 6],
       CASE WHEN g % 2 = 0
            THEN '628' || (11 + g % 9) || lpad((g * 104729 % 100000000)::text, 8, '0')
            ELSE '08' || (11 + g % 9) || '-'
                 || substr(lpad((g * 104729 % 100000000)::text, 8, '0'), 1, 4) || '-'
                 || substr(lpad((g * 104729 % 100000000)::text, 8, '0'), 5) END,
       CASE WHEN g % 20 = 0
            THEN (ARRAY['Jayapura','Sentani','Abepura','Waena'])[1 + (g + 1) % 4]
            ELSE (ARRAY['Jayapura','Sentani','Abepura','Waena'])[1 + g % 4] END,
       CASE WHEN g % 10 IN (0,3,7) THEN 'Grosir' ELSE 'Retail' END,
       (g * 37) % 5000,
       DATE '2026-06-01' + g % 120
FROM generate_series(1, 190) g
WHERE g % 3 <> 0 OR g > 180;
