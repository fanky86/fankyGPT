import os, json, pickle, requests, math, re
from bs4 import BeautifulSoup
from text_processor import clean_text
from supabase_config import upload_to_supabase
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB

DATA_FILE = "data/training_data.jsonl"
MODEL_FILE = "models/model.pkl"

# ──────────────── Data Management ──────────────── #
def save_training_data(input_text, output_text):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "a") as f:
        f.write(json.dumps({"input": input_text, "output": output_text}) + "\n")

def load_training_data():
    if not os.path.exists(DATA_FILE):
        return [], []
    X, y = [], []
    with open(DATA_FILE) as f:
        for line in f:
            item = json.loads(line)
            X.append(clean_text(item["input"]))
            y.append(item["output"])
    return X, y

# ──────────────── Training Model ──────────────── #
def train_model(input_text, output_text):
    save_training_data(input_text, output_text)
    X, y = load_training_data()
    vectorizer = CountVectorizer()
    X_vectorized = vectorizer.fit_transform(X)
    model = MultinomialNB()
    model.fit(X_vectorized, y)
    os.makedirs(os.path.dirname(MODEL_FILE), exist_ok=True)
    with open(MODEL_FILE, "wb") as f:
        pickle.dump((model, vectorizer), f)
    upload_to_supabase(MODEL_FILE)

# ──────────────── Prediksi dengan Model & Matematika ──────────────── #
def is_math_expression(text):
    # Deteksi apakah input adalah ekspresi matematika (hanya karakter valid)
    allowed = r'^[\d\s\+\-\*/\%\.\(\)\[\]\,eEpiqrtlogsincoatanraddeg\^]+$'
    return re.match(allowed, text.replace('**', '^')) is not None

def safe_eval_math(expr):
    try:
        expr = expr.replace("^", "**")
        return eval(expr, {"__builtins__": {}}, {
            "sqrt": math.sqrt,
            "log": math.log,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "pi": math.pi,
            "e": math.e,
            "pow": math.pow,
            "abs": abs,
            "round": round,
            "deg": math.degrees,
            "rad": math.radians
        })
    except Exception as e:
        return f"❌ Ekspresi matematika tidak valid: {e}"

def predict_input(input_text):
    try:
        if is_math_expression(input_text):
            return str(safe_eval_math(input_text))
        with open(MODEL_FILE, "rb") as f:
            model, vectorizer = pickle.load(f)
        return model.predict(vectorizer.transform([clean_text(input_text)]))[0]
    except Exception as e:
        return f"Model belum dilatih: {e}"

# ──────────────── Ekstrak Artikel dari URL ──────────────── #
def extract_text_from_url(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        text = "\n".join(paragraphs[:5])
        return f"{title}\n{text}".strip()
    except Exception as e:
        return f"[Gagal mengambil dari URL] {e}"
