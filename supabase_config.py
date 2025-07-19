from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime
import os
import uuid

# Load variabel lingkungan dari .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "model-bucket"

# Inisialisasi client Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ──────────────── Upload / Download Model ──────────────── #
def upload_to_supabase(file_path):
    """Upload file model ke Supabase Storage"""
    try:
        file_name = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            supabase.storage.from_(BUCKET_NAME).upload(
                file_name, f, {"x-upsert": "true"}
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

# ──────────────── Chat Logs (user ↔ bot) ──────────────── #
def save_chat_to_supabase(user_input, response_text, user_id):
    """Simpan obrolan ke Supabase"""
    try:
        data = {
            "user_id": user_id,
            "input": user_input,
            "output": response_text,
            "timestamp": datetime.utcnow().isoformat()
        }
        supabase.table("chat_logs").insert(data).execute()
        print("[✔] Obrolan disimpan ke Supabase.")
    except Exception as e:
        print(f"[✖] Gagal simpan obrolan ke Supabase: {e}")

def get_memory(user_id):
    """Ambil riwayat obrolan dari Supabase berdasarkan user_id"""
    try:
        response = (
            supabase.table("chat_logs")
            .select("input, output")
            .eq("user_id", user_id)
            .order("timestamp", desc=False)
            .execute()
        )
        chat_data = response.data
        return [{"user": item["input"], "bot": item["output"]} for item in chat_data]
    except Exception as e:
        print(f"[✖] Gagal ambil riwayat chat dari Supabase: {e}")
        return []

SUPABASE = supabase
