# UC Store: Data Warehouse Penjualan

Hasil praktikum membangun data warehouse penjualan untuk studi kasus fiktif
PT Sembada Niaga Nusantara: dua database sumber (kasir dan member), staging,
MDM hub, star schema dengan SCD tipe 2, data mart, ETL incremental dengan
Python, dan dashboard analitik dengan Streamlit.

Seluruh data di repo ini fiktif dan dibuat dengan angka acak yang dikunci.

## Isi repo

| Path | Isi |
| --- | --- |
| `dashboard.py` | Dashboard analitik (Streamlit + Plotly) |
| `sumber_data.py` | Pembaca data: database `toko_dw`, atau snapshot di `data/` |
| `data/` | Snapshot hasil data warehouse (12.455 baris fakta, 181 pelanggan master) |
| `etl.py` | ETL: extract, validasi, MDM, load star schema, refresh mart |
| `sql/` | Skrip database sumber, arsitektur DW, MDM, mart, query analitik Q1 sampai Q8 |
| `logs/hasil_analitik_Q1-Q8.txt` | Output delapan query analitik |
| `crontab_dw.txt` | Jadwal ETL dan backup harian |

## Menjalankan dashboard

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/streamlit run dashboard.py
```

Bila PostgreSQL dengan database `toko_dw` berjalan di `localhost:5432`,
dashboard membaca langsung dari sana sebagai `bi_user`. Bila tidak,
dashboard membaca snapshot di `data/`. Ini juga yang dipakai saat di-deploy
ke Streamlit Community Cloud.

Setelah ETL dijalankan ulang, perbarui snapshot dengan:

```bash
venv/bin/python sumber_data.py
```

## Membangun ulang data warehouse

Butuh PostgreSQL 18. Urutan skripnya: `sql/01_user_db.sql` (superuser),
`sql/02_oltp.sql`, `sql/02b_crm.sql`, `sql/03_dw.sql`, `python etl.py`,
`sql/07_mart.sql`, lalu `python etl.py` lagi.

Password `EtlPass123` dan `BiPass123` di skrip hanya untuk latihan kelas.
Jangan dipakai di server sungguhan.
