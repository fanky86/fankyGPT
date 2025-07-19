from fastapi import Request, HTTPException, Depends
from supabase_config import SUPABASE

def verify_supabase_admin(request: Request):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Token hilang")

    user = SUPABASE.auth.get_user(token.replace("Bearer ", ""))
    user_email = user.user.email

    # Ambil role dari tabel "profiles"
    result = SUPABASE.table("profiles").select("role").eq("email", user_email).single().execute()
    if not result.data or result.data["role"] != "admin":
        raise HTTPException(status_code=403, detail="Bukan admin")

    return {
        "user": {
            "email": user_email,
            "role": result.data["role"]
        }
    }
