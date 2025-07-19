from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from model_trainer import train_model, predict_input, extract_text_from_url
from supabase_config import download_model_from_supabase, save_chat_to_supabase, get_memory
from openai import OpenAI
from sympy import sympify
from sympy.core.sympify import SympifyError
from dotenv import load_dotenv
import os, uuid

# Load env
load_dotenv()

# Setup OpenAI client langsung
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

MODEL_FILE = "models/model.pkl"

@app.on_event("startup")
def startup_event():
    if not os.path.exists(MODEL_FILE):
        try:
            download_model_from_supabase(MODEL_FILE)
        except Exception as e:
            print(f"[Startup Error] Gagal unduh model: {e}")

# Middleware untuk assign user_id
@app.middleware("http")
async def assign_user_id(request: Request, call_next):
    user_id = request.cookies.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
        response = await call_next(request)
        response.set_cookie("user_id", user_id)
        return response
    else:
        return await call_next(request)

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

        # Simpan ke Supabase jika ada user_id
        if user_id:
            save_chat_to_supabase(user_input, reply, user_id)

        # Latih model lokal
        train_model(user_input, reply)

        return {"reply": reply}

    except Exception as e:
        return {"reply": f"❌ Gagal: {e}"}

# Hitung ekspresi matematika jika bisa
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
            "response": hasil_matematika,
            "last_input": input_text
        })

    result = predict_input(input_text)
    return templates.TemplateResponse("lokal.html", {
        "request": request,
        "response": result,
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

@app.get("/download-model")
async def download_model():
    return FileResponse(MODEL_FILE, filename="model.pkl")

@app.get("/hapus-data")
def hapus_data():
    try:
        if os.path.exists("data/training_data.jsonl"):
            os.remove("data/training_data.jsonl")
            return {"status": "success", "message": "✅ Data training dihapus."}
        return {"status": "not_found", "message": "⚠️ File data tidak ditemukan."}
    except Exception as e:
        return {"status": "error", "message": f"❌ Gagal hapus data: {e}"}

@app.get("/hapus-model")
def hapus_model():
    try:
        if os.path.exists("models/model.pkl"):
            os.remove("models/model.pkl")
            return {"status": "success", "message": "✅ Model dihapus."}
        return {"status": "not_found", "message": "⚠️ Model belum ada."}
    except Exception as e:
        return {"status": "error", "message": f"❌ Gagal hapus model: {e}"}
