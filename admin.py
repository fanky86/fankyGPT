from fastapi import Header, HTTPException
import requests
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_KEY")

def verify_supabase_admin(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token tidak valid")
    
    token = authorization.split(" ")[1]

    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": SUPABASE_API_KEY
    }

    response = requests.get(f"{SUPABASE_URL}/auth/v1/user", headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Gagal verifikasi token")

    user_data = response.json()
    
    # Contoh validasi: hanya email tertentu boleh akses
    if not user_data.get("email", "").endswith("@gmail.com"):
        raise HTTPException(status_code=403, detail="Akses hanya untuk admin")
    
    return user_data
