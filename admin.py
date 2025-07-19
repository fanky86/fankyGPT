from fastapi import Header, HTTPException
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_KEY")
SUPABASE: Client = create_client(SUPABASE_URL, SUPABASE_API_KEY)

def verify_supabase_admin(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token tidak valid")

    token = authorization.split(" ")[1]

    try:
        user = SUPABASE.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token tidak valid atau expired")

    if not user or not user.user or not user.user.email:
        raise HTTPException(status_code=401, detail="Token tidak valid atau tidak ada email")

    user_email = user.user.email

    # Ambil role dari tabel profiles berdasarkan email
    result = SUPABASE.table("profiles").select("role").eq("email", user_email).single().execute()

    if not result.data or result.data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Akses hanya untuk admin")

    return user
