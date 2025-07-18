from supabase import create_client
from datetime import datetime
import os

# Langsung ditulis, tanpa os.getenv
SUPABASE_URL = "https://kphtlpzsmvbbpkqkouoq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtwaHRscHpzbXZiYnBrcWtvdW9xIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Mjc4MTU5OSwiZXhwIjoyMDY4MzU3NTk5fQ._Ot5ef5xx7eAfFDFuYPdHA4l8hSKBvPCrsur5-8nOqI"
BUCKET_NAME = "model-bucket"

# Inisialisasi Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_to_supabase(file_path):
    """Upload file model ke Supabase Storage"""
    try:
        file_name = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            supabase.storage.from_(BUCKET_NAME).upload(
                file_name, f,
                {"x-upsert": "true"}
            )
        print(f"[✔] Model '{file_name}' berhasil diupload ke Supabase.")
    except Exception as e:
        print(f"[✖] Gagal upload ke Supabase: {e}")

def download_model_from_supabase(file_path):
    """Download model dari Supabase Storage jika tersedia"""
    try:
        file_name = os.path.basename(file_path)
        data = supabase.storage.from_(BUCKET_NAME).download(file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(data)
        print(f"[✔] Model '{file_name}' berhasil didownload dari Supabase.")
    except Exception as e:
        print(f"[✖] Gagal download dari Supabase: {e}")

def save_chat_to_supabase(user_input, response_text):
    """Simpan obrolan user dan respon GPT ke Supabase table chat_logs"""
    try:
        data = {
            "input": user_input,
            "output": response_text,
            "timestamp": datetime.utcnow().isoformat()
        }
        supabase.table("chat_logs").insert(data).execute()
        print("[✔] Obrolan disimpan ke Supabase.")
    except Exception as e:
        print(f"[✖] Gagal simpan obrolan ke Supabase: {e}")
