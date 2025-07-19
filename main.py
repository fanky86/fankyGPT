from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from model_trainer import predict_input, train_model
from supabase_config import (
    download_model_from_supabase,
    save_chat_to_supabase,
    get_memory,
)
import os
from uuid import uuid4

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ⬇️ Model path yang digunakan untuk Supabase dan lokal
MODEL_PATH = "model/model.pkl"


# ✅ Unduh model dari Supabase saat server dimulai
@app.on_event("startup")
def load_model():
    download_model_from_supabase(MODEL_PATH)


# ✅ Halaman utama FankyGPT
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user_id = request.cookies.get("user_id") or str(uuid4())
    messages = get_memory(user_id)
    response = templates.TemplateResponse("index.html", {
        "request": request,
        "messages": messages
    })
    response.set_cookie(key="user_id", value=user_id)
    return response


# ✅ POST ke ChatGPT API + latih model lokal
@app.post("/chat-gpt", response_class=HTMLResponse)
async def chat_gpt(request: Request, message: str = Form(...)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/", status_code=302)

    try:
        from openai import OpenAI
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Kamu adalah asisten cerdas bernama FankyGPT."},
                {"role": "user", "content": message}
            ]
        )

        reply = response.choices[0].message.content.strip()

        # Simpan ke Supabase dan latih model lokal
        save_chat_to_supabase(message, reply, user_id)
        train_model(message, reply)

        messages = get_memory(user_id)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "messages": messages
        })

    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "messages": [],
            "error": f"Gagal menghubungi ChatGPT: {e}"
        })


# ✅ API endpoint: chat json
@app.post("/chat-gpt-json")
async def chat_gpt_json(request: Request):
    form = await request.form()
    user_input = form.get("message")
    user_id = request.cookies.get("user_id")

    if not user_id:
        return JSONResponse(content={"reply": "❌ User ID tidak ditemukan."}, status_code=400)

    try:
        from openai import OpenAI
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Kamu adalah asisten cerdas bernama FankyGPT."},
                {"role": "user", "content": user_input}
            ]
        )

        reply = response.choices[0].message.content.strip()
        save_chat_to_supabase(user_input, reply, user_id)
        train_model(user_input, reply)

        return JSONResponse(content={"reply": reply})

    except Exception as e:
        return JSONResponse(content={"reply": f"Gagal: {e}"}, status_code=500)


# ✅ Halaman untuk model lokal
@app.get("/lokal", response_class=HTMLResponse)
async def lokal_ui(request: Request):
    return templates.TemplateResponse("lokal.html", {"request": request})


# ✅ Prediksi dengan model lokal
@app.post("/lokal/predict")
async def lokal_predict(request: Request):
    form = await request.form()
    input_text = form.get("input_text")
    prediction = predict_input(input_text)
    return templates.TemplateResponse("lokal.html", {
        "request": request,
        "last_input": input_text,
        "response": prediction
    })


# ✅ Latih model lokal secara manual
@app.post("/lokal/train")
async def lokal_train(request: Request):
    form = await request.form()
    input_text = form.get("input_text")
    output_text = form.get("output_text")
    train_model(input_text, output_text)
    return RedirectResponse("/lokal", status_code=302)


# ✅ Latih dari URL (fitur opsional)
@app.post("/lokal/train-url")
async def train_from_url(request: Request):
    form = await request.form()
    url = form.get("url")
    # Tambahkan logika jika ada
    return templates.TemplateResponse("lokal.html", {
        "request": request,
        "url": url,
        "response": "🚧 Belum tersedia."
    })


# ✅ Preview artikel URL
@app.post("/lokal/preview-url")
async def preview_url(request: Request):
    form = await request.form()
    url = form.get("url")
    return templates.TemplateResponse("lokal.html", {
        "request": request,
        "url": url,
        "response": "🔍 Pratinjau fitur belum tersedia."
    })


# ✅ Reset: hapus data latih (opsional)
@app.get("/hapus-data")
async def hapus_data():
    if os.path.exists("model/data.json"):
        os.remove("model/data.json")
    return RedirectResponse("/lokal", status_code=302)


# ✅ Reset: hapus model lokal
@app.get("/hapus-model")
async def hapus_model():
    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)
    return RedirectResponse("/lokal", status_code=302)


# ✅ Unduh model (opsional)
@app.get("/download-model")
async def download_model():
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            return HTMLResponse(content=f.read(), media_type="application/octet-stream")
    return JSONResponse(content={"error": "Model tidak ditemukan"}, status_code=404)
