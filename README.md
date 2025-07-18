# FankyGPT AutoLearn AI

Proyek AI sederhana yang bisa belajar otomatis dari input baru dan digunakan secara langsung. Cocok untuk deployment di Vercel + GitHub.

## Fitur
- API untuk `/train` dan `/predict`
- Menyimpan data ke JSONL
- Otomatis melatih model setiap input
- Format siap Vercel

## Jalankan lokal
```bash
uvicorn main:app --reload
```

## Coba test manual
```bash
python test_model.py
```
