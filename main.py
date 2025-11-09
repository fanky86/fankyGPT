import os, uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import OpenAI
from fastapi.middleware.cors import CORSMiddleware
from supabase_config import SUPABASE
from supabase_config import save_chat_to_supabase, get_memory
from fastapi import APIRouter

admin_router = APIRouter()
load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY")
)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def assign_user_id(request: Request, call_next):
    user_id = request.cookies.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
        response = await call_next(request)
        response.set_cookie("user_id", user_id)
        return response
    return await call_next(request)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user_id = request.cookies.get("user_id")
    chat_history = get_memory(user_id) if user_id else []
    return templates.TemplateResponse("index.html", {
        "request": request,
        "messages": chat_history
    })

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

        return {"reply": reply}
    except Exception as e:
        return {"reply": f"❌ Gagal: {e}"}

