from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from model_trainer import predict_input, train_model
from supabase_config import download_model_from_supabase, save_chat_to_supabase, get_memory
import os, re

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Unduh model saat aplikasi mulai
@app.on_event("startup")
def load_model():
    download_model_from_supabase()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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
            model="openai/gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Kamu adalah asisten cerdas bernama FankyGPT."},
                {"role": "user", "content": user_input}
            ]
        )

        reply = response.choices[0].message.content.strip()

        # Simpan ke Supabase
        save_chat_to_supabase(user_input, reply, user_id)

        # Latih model lokal secara otomatis dengan input user dan respon bot
        train_model(user_input, reply)

        return JSONResponse(content={"reply": reply})

    except Exception as e:
        return JSONResponse(content={"reply": f"Gagal menghubungi ChatGPT: {e}"}, status_code=500)

@app.post("/train")
async def train(request: Request):
    data = await request.json()
    user_input = data.get("input")
    reply = data.get("output")
    train_model(user_input, reply)
    return JSONResponse(content={"message": "Model dilatih ulang."})

@app.post("/predict")
async def predict(request: Request):
    data = await request.json()
    user_input = data.get("input")
    prediction = predict_input(user_input)
    return JSONResponse(content={"prediction": prediction})
