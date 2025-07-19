from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from model_trainer import train_model, predict_input, extract_text_from_url
from supabase_config import get_chat_history, download_model_from_supabase, save_chat_to_supabase
from openai import OpenAI
from sympy import sympify
from sympy.core.sympify import SympifyError
import os, re, uuid

load_dotenv()

# Init OpenRouter Client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("❌ OPENAI_API_KEY belum di-set di environment!")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

MODEL_FILE = "models/model.pkl"

# 📦 Download model saat startup jika belum ada
@app.on_event("startup")
def startup_event():
    if not os.path.exists(MODEL_FILE):
        try:
            download_model_from_supabase(MODEL_FILE)
        except Exception as e:
            print(f"[Startup Error] Gagal unduh model: {e}")

# 🏠 Halaman utama (chat)
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
        response = templates.TemplateResponse("index.html", {
            "request": request,
            "messages": []
        })
        response.set_cookie("user_id", user_id, max_age=60*60*24*365)
        return response

    messages = get_chat_history(user_id)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "messages": messages
    })

# 🌐 Halaman lokal (manual predict dan training)
@app.get("/lokal", response_class=HTMLResponse)
def lokal_page(request: Request):
    return templates.TemplateResponse("lokal.html", {"request": request})

# 🔁 Chat biasa (dengan reload HTML)
@app.post("/chat-gpt", response_class=HTMLResponse)
async def chat_gpt(request: Request):
    form = await request.form()
    user_input = form.get("message")
    user_id = request.cookies.get("user_id")

    if not user_id:
        return HTMLResponse("<p style='color:red;'>User ID tidak ditemukan.</p>")

    try:
        response = client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Kamu adalah asisten cerdas bernama FankyGPT."},
                {"role": "user", "content": user_input}
            ]
        )
        reply = response.choices[0].message.content.strip()
        save_chat_to_supabase(user_input, reply, user_id)
        messages = get_chat_history(user_id)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "messages": messages
        })

    except Exception as e:
        return HTMLResponse(f"<p style='color:red;'>Gagal menghubungi ChatGPT: {e}</p>")

# ⚡ Chat cepat (untuk animasi & fetch JSON)
@app.post("/chat-gpt-json")
async def chat_gpt_json(request: Request):
    form = await request.form()
    user_input = form.get("message")
    user_id = request.cookies.get("user_id")

    if not user_id:
        return JSONResponse(content={"reply": "❌ User ID tidak ditemukan."}, status_code=400)

    try:
        response = client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Kamu adalah asisten cerdas bernama FankyGPT."},
                {"role": "user", "content": user_input}
            ]
        )
        reply = response.choices[0].message.content.strip()
        save_chat_to_supabase(user_input, reply, user_id)
        return JSONResponse(content={"reply": reply})

    except Exception as e:
        return JSONResponse(content={"reply": f"Gagal menghubungi ChatGPT: {e}"}, status_code=500)

# 🧠 Fungsi hitung ekspresi matematika
def hitung_ekspresi(text):
    try:
        hasil = sympify(text).evalf()
        if hasil == int(hasil):
            return str(int(hasil))
        return str(hasil)
    except (SympifyError, Exception):
        return None

# 🔍 Prediksi lokal
@app.post("/lokal/predict")
async def predict_local(request: Request, input_text: str = Form(...)):
    hasil_matematika = hitung_ekspresi(input_text)
    if hasil_matematika:
        return templates.TemplateResponse("lokal.html", {
            "request": request,
            "response": hasil_matematika,
            "last_input": input_text
        })
    result = predict_input(input_text)
    return templates.TemplateResponse("lokal.html", {
        "request": request,
        "response": result,
        "last_input": input_text
    })

# 🧠 Latih model manual
@app.post("/lokal/train")
async def train_local(request: Request, input_text: str = Form(...), output_text: str = Form(...)):
    train_model(input_text, output_text)
    return RedirectResponse("/lokal", status_code=302)

# 🌐 Latih dari URL
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

# 👁️ Preview URL
@app.post("/lokal/preview-url", response_class=HTMLResponse)
async def preview_url_local(request: Request):
    data = await request.form()
    url = data.get("url")
    if not url:
        return HTMLResponse("<p style='color:red;'>URL tidak boleh kosong</p>")
    text = extract_text_from_url(url)
    preview = f"<h3>📄 Teks dari URL:</h3><pre>{text}</pre>"
    return HTMLResponse(preview)

# ⬇️ Unduh model
@app.get("/download-model")
async def download_model():
    return FileResponse(MODEL_FILE, filename="model.pkl")

# 🧹 Hapus data training
@app.get("/hapus-data")
def hapus_data():
    try:
        if os.path.exists("data/training_data.jsonl"):
            os.remove("data/training_data.jsonl")
            return {"status": "success", "message": "✅ Data training dihapus."}
        return {"status": "not_found", "message": "⚠️ File data tidak ditemukan."}
    except Exception as e:
        return {"status": "error", "message": f"❌ Gagal hapus data: {e}"}

# 🧹 Hapus model
@app.get("/hapus-model")
def hapus_model():
    try:
        if os.path.exists("models/model.pkl"):
            os.remove("models/model.pkl")
            return {"status": "success", "message": "✅ Model dihapus."}
        return {"status": "not_found", "message": "⚠️ Model belum ada."}
    except Exception as e:
        return {"status": "error", "message": f"❌ Gagal hapus model: {e}"}
