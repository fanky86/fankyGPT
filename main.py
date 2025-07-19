import os, uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import OpenAI
from sympy import sympify
from sympy.core.sympify import SympifyError
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import os, json
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase_config import SUPABASE

# Custom imports
from model_trainer import train_model, predict_input, extract_text_from_url
from supabase_config import download_model_from_supabase, save_chat_to_supabase, get_memory
from admin import verify_supabase_admin
from fastapi import APIRouter, Depends
# from admin_auth import verify_supabase_admin  # jika disimpan di file lain

admin_router = APIRouter()
# Load environment
load_dotenv()

# Setup OpenAI
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY")
)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

MODEL_FILE = "models/model.pkl"
DATA_FILE = "data/training_data.jsonl"

# Middleware agar bisa diakses dari browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Sesuaikan jika perlu
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fungsi verifikasi admin
def verify_supabase_admin(request: Request):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Token hilang")

    user = SUPABASE.auth.get_user(token.replace("Bearer ", ""))
    if not user or not user.user or not user.user.email:
        raise HTTPException(status_code=401, detail="Token tidak valid")

    user_email = user.user.email
    result = SUPABASE.table("profiles").select("role").eq("email", user_email).single().execute()
    
    if not result.data or result.data["role"] != "admin":
        raise HTTPException(status_code=403, detail="Bukan admin")

    return {
        "email": user_email,
        "role": result.data["role"]
    }

# Endpoint /admin yang dipanggil oleh cekAdmin()
@app.get("/admin")
async def get_admin_info(request: Request):
    return verify_supabase_admin(request)


# ─────────────────────── STARTUP ─────────────────────── #
@app.on_event("startup")
def startup_event():
    if not os.path.exists(MODEL_FILE):
        try:
            download_model_from_supabase(MODEL_FILE)
        except Exception as e:
            print(f"[Startup Error] Gagal unduh model: {e}")

# ─────────────────────── MIDDLEWARE ─────────────────────── #
@app.middleware("http")
async def assign_user_id(request: Request, call_next):
    user_id = request.cookies.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
        response = await call_next(request)
        response.set_cookie("user_id", user_id)
        return response
    return await call_next(request)

# ─────────────────────── ROUTES ─────────────────────── #

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user_id = request.cookies.get("user_id")
    chat_history = get_memory(user_id) if user_id else []
    return templates.TemplateResponse("index.html", {
        "request": request,
        "messages": chat_history
    })

@app.get("/lokal", response_class=HTMLResponse)
def lokal_page(request: Request):
    return templates.TemplateResponse("lokal.html", {"request": request})

@app.post("/chat-gpt", response_class=HTMLResponse)
async def chat_gpt(request: Request):
    form = await request.form()
    user_input = form.get("message")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Kamu adalah asisten cerdas bernama FankyGPT."},
                {"role": "user", "content": user_input}
            ]
        )
        reply = response.choices[0].message.content
        save_chat_to_supabase(user_input, reply)
        train_model(user_input, reply)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "chat_input": user_input,
            "chat_response": reply
        })
    except Exception as e:
        return HTMLResponse(f"<p style='color:red;'>Gagal menghubungi ChatGPT: {e}</p>")

@app.post("/chat-gpt-json")
async def chat_gpt_json(request: Request):
    form = await request.form()
    user_input = form.get("message")
    user_id = request.cookies.get("user_id")

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Kamu adalah FankyGPT, asisten cerdas dan cepat."},
                {"role": "user", "content": user_input}
            ]
        )
        reply = response.choices[0].message.content.strip()

        if user_id:
            save_chat_to_supabase(user_input, reply, user_id)

        train_model(user_input, reply)

        return {"reply": reply}
    except Exception as e:
        return {"reply": f"❌ Gagal: {e}"}

# ─────────────────────── MATEMATIKA & LOKAL MODEL ─────────────────────── #

def hitung_ekspresi(text):
    try:
        hasil = sympify(text).evalf()
        return str(int(hasil)) if hasil == int(hasil) else str(hasil)
    except (SympifyError, Exception):
        return None

@app.post("/lokal/predict")
async def predict_local(request: Request, input_text: str = Form(...)):
    hasil_matematika = hitung_ekspresi(input_text)
    if hasil_matematika:
        return templates.TemplateResponse("lokal.html", {
            "request": request,
            "response": f"Hasil Matematika: {hasil_matematika}",
            "last_input": input_text
        })

    try:
        result = predict_input(input_text)
        return templates.TemplateResponse("lokal.html", {
            "request": request,
            "response": result or "❌ Model tidak memberikan prediksi.",
            "last_input": input_text
        })
    except Exception as e:
        return templates.TemplateResponse("lokal.html", {
            "request": request,
            "response": f"❌ Terjadi kesalahan saat prediksi: {str(e)}",
            "last_input": input_text
        })

@app.post("/lokal/train")
async def train_local(request: Request, input_text: str = Form(...), output_text: str = Form(...)):
    train_model(input_text, output_text)
    return RedirectResponse("/lokal", status_code=302)

@app.post("/lokal/train-url", response_class=HTMLResponse)
async def train_from_url_local(request: Request):
    data = await request.form()
    url = data.get("url")
    if not url:
        return HTMLResponse("<p style='color:red;'>URL tidak boleh kosong</p>")
    text = extract_text_from_url(url)
    if not text or text.startswith("[Gagal mengambil"):
        return HTMLResponse(f"<p style='color:red;'>Gagal mengambil teks dari URL: {text}</p>")
    train_model("artikel", text.strip())
    return HTMLResponse("<p style='color:green;'>✅ Model berhasil dilatih dari URL!</p>")

@app.post("/lokal/preview-url", response_class=HTMLResponse)
async def preview_url_local(request: Request):
    data = await request.form()
    url = data.get("url")
    if not url:
        return HTMLResponse("<p style='color:red;'>URL tidak boleh kosong</p>")
    text = extract_text_from_url(url)
    preview = f"<h3>📄 Teks dari URL:</h3><pre>{text}</pre>"
    return HTMLResponse(preview)

# ─────────────────────── FILE HANDLING ─────────────────────── #

@app.get("/download-model")
async def download_model():
    return FileResponse(MODEL_FILE, filename="model.pkl")

@app.get("/hapus-data")
def hapus_data(admin=Depends(verify_supabase_admin)):
    try:
        if os.path.exists("data/training_data.jsonl"):
            os.remove("data/training_data.jsonl")
            return {"status": "success", "message": "✅ Data training dihapus."}
        return {"status": "not_found", "message": "⚠️ File data tidak ditemukan."}
    except Exception as e:
        return {"status": "error", "message": f"❌ Gagal hapus data: {e}"}

@app.get("/hapus-model")
def hapus_model(admin=Depends(verify_supabase_admin)):
    try:
        if os.path.exists(MODEL_FILE):
            os.remove(MODEL_FILE)
            return {"status": "success", "message": "✅ Model dihapus."}
        return {"status": "not_found", "message": "⚠️ Model belum ada."}
    except Exception as e:
        return {"status": "error", "message": f"❌ Gagal hapus model: {e}"}

@app.get("/lokal/show", response_class=PlainTextResponse)
async def show_training_data():
    if not os.path.exists(DATA_FILE):
        return "❌ Belum ada data training."

    lines = []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line.strip())
            input_text = item.get("input", "[kosong]")
            output_text = item.get("output", "[kosong]")
            lines.append(f"📝 Input: {input_text}\n📤 Output: {output_text}\n")
    return "\n".join(lines)


