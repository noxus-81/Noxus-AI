import streamlit as st
import os
import json
import glob
import io
import base64
import subprocess
import urllib.parse
import tempfile
import sqlite3
import bcrypt
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image
from duckduckgo_search import DDGS

st.set_page_config(page_title="Noxus AI", page_icon="🌌", layout="wide")

# ═══════════════════════════════════════════════════════════
#  BASE DE DONNÉES UTILISATEURS
# ═══════════════════════════════════════════════════════════
DB_NAME = "users.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password_hash TEXT)''')
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        hashed = bcrypt.hashpw("noxus2026".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        c.execute("INSERT INTO users VALUES (?, ?)", ("noxus", hashed))
    conn.commit()
    conn.close()

def verify_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and bcrypt.checkpw(password.encode('utf-8'), row[0].encode('utf-8')):
        return True
    return False

def register_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        return False, "Nom d'utilisateur déjà pris."
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    c.execute("INSERT INTO users VALUES (?, ?)", (username, hashed))
    conn.commit()
    conn.close()
    return True, "Compte créé avec succès !"

init_db()

# ═══════════════════════════════════════════════════════════
#  PAGE DE CONNEXION
# ═══════════════════════════════════════════════════════════
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center; color: #0078D4;'>🌌 Noxus AI — Connexion</h2>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Se connecter", "Créer un compte"])
    with tab1:
        with st.form("login_form"):
            user_input = st.text_input("Identifiant")
            pass_input = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Se connecter"):
                if verify_user(user_input, pass_input):
                    st.session_state.authenticated = True
                    st.session_state.username = user_input
                    st.rerun()
                else:
                    st.error("Identifiant ou mot de passe incorrect.")
    with tab2:
        with st.form("register_form"):
            new_user = st.text_input("Nouvel Identifiant")
            new_pass = st.text_input("Nouveau mot de passe", type="password")
            if st.form_submit_button("S'inscrire"):
                if new_user and new_pass:
                    ok, msg = register_user(new_user, new_pass)
                    st.success(msg) if ok else st.error(msg)
                else:
                    st.warning("Veuillez remplir tous les champs.")
    st.stop()

# ═══════════════════════════════════════════════════════════
#  APPLICATION PRINCIPALE
# ═══════════════════════════════════════════════════════════
CHATS_DIR = "chats"
if not os.path.exists(CHATS_DIR):
    os.makedirs(CHATS_DIR)

load_dotenv()
openrouter_key = os.getenv("OPENROUTER_API_KEY")
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=openrouter_key
) if openrouter_key else None

MODEL_TEXT   = "meta-llama/llama-3.3-70b-instruct"
MODEL_VISION = "qwen/qwen3-vl-32b-instruct"

SYSTEM_INSTRUCTION = """Tu es Noxus AI, une intelligence artificielle ultra-avancée et autonome créée par Noxus.

PERSONNALITÉ : Tu es précis, efficace, bienveillant et légèrement enthousiaste. Tu utilises des emojis avec modération.

MATHÉMATIQUES ET CALCULS (TRÈS IMPORTANT) :
Tu n'es pas bon en calcul mental. Dès que tu dois effectuer un calcul mathématique (multiplication, addition, pourcentage, etc.), NE DONNE JAMAIS LE RÉSULTAT TOI-MÊME.
Écris EXACTEMENT la balise `[CALCUL: <ton expression mathématique>]`. L'interface calculera et affichera le résultat à l'utilisateur à ta place.
Exemple d'utilisation : 
User: "Combien fait 18540 x 28900 ?"
Toi: "Le résultat de la multiplication est [CALCUL: 18540 * 28900]."

GESTION DES IMAGES :
Lorsque l'utilisateur te demande de générer, créer ou dessiner une image, tu dois créer un "prompt" EN ANGLAIS digne des meilleurs artistes Midjourney. 
Génère UNIQUEMENT cette balise dans ta réponse :
[IMAGE: <ton prompt hyper détaillé en anglais ici>]

RÈGLES POUR LE PROMPT IMAGE :
- Sois extrêmement descriptif et visuel.
- Ajoute toujours ces mots-clés à la fin : "photorealistic, 8k resolution, highly detailed, masterpiece, sharp focus, cinematic lighting, hyperrealistic, f/1.8, Unreal Engine 5 render".
- Ne dis JAMAIS que tu ne peux pas générer d'images.

RECHERCHE WEB :
Quand les résultats de recherche sont fournis dans le contexte, utilise-les pour enrichir ta réponse.

EXÉCUTION DE CODE :
Quand tu génères du code Python à exécuter, entoure-le avec la balise :
[EXECUTE_PYTHON]
# code
[/EXECUTE_PYTHON]
"""

import requests
import re

def generate_and_crop_image(prompt_english: str) -> str:
    encoded = urllib.parse.quote(prompt_english.strip())
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&model=flux&nologo=true"
    try:
        response = requests.get(url, timeout=30)
        img = Image.open(io.BytesIO(response.content))
        width, height = img.size
        # Rognage des 40 pixels du bas pour supprimer le filigrane
        img_cropped = img.crop((0, 0, width, height - 40))
        
        buf = io.BytesIO()
        img_cropped.save(buf, format="JPEG")
        image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{image_b64}"
    except Exception as e:
        return url

@st.cache_resource(show_spinner="🎙️ Chargement du modèle vocal...")
def load_whisper():
    from faster_whisper import WhisperModel
    try:
        return WhisperModel("small", device="cuda", compute_type="float16")
    except Exception:
        return WhisperModel("small", device="cpu", compute_type="int8")

def transcribe_audio(audio_bytes: bytes) -> str:
    try:
        whisper = load_whisper()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        segments, _ = whisper.transcribe(tmp_path, language="fr", beam_size=5)
        os.unlink(tmp_path)
        return " ".join(seg.text for seg in segments).strip()
    except Exception as e:
        return f"[Erreur transcription: {e}]"

def web_search(query: str, max_results: int = 4) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results: return "Aucun résultat trouvé."
        return "Résultats Web :\n" + "\n\n".join(f"**{r['title']}**\n{r['body']}\nSource : {r['href']}" for r in results)
    except Exception as e:
        return f"[Erreur recherche: {e}]"

def needs_web_search(prompt: str) -> bool:
    keywords = ["aujourd'hui", "actuellement", "récent", "2024", "2025", "2026", "prix", "météo", "actualité"]
    return any(k in prompt.lower() for k in keywords)

def execute_python(code: str) -> str:
    try:
        result = subprocess.run(["python", "-c", code], capture_output=True, text=True, timeout=30)
        return (result.stdout or result.stderr or "Exécuté sans sortie.")[:3000]
    except Exception as e:
        return f"Erreur : {e}"

if "messages" not in st.session_state: st.session_state.messages = []
if "current_chat_id" not in st.session_state: st.session_state.current_chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
if "pending_code" not in st.session_state: st.session_state.pending_code = None

def save_chat():
    if not st.session_state.messages: return
    saveable = []
    for msg in st.session_state.messages:
        texts = [p for p in msg["content"] if isinstance(p, str)]
        if texts: saveable.append({"role": msg["role"], "content": texts})
    if not saveable: return
    title = saveable[0]["content"][0][:30] + "..."
    with open(os.path.join(CHATS_DIR, f"{st.session_state.current_chat_id}.json"), "w", encoding="utf-8") as f:
        json.dump({"title": title, "messages": saveable, "user": st.session_state.username}, f, ensure_ascii=False, indent=2)

def delete_chat(chat_id: str):
    path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    if os.path.exists(path): os.remove(path)
    if st.session_state.current_chat_id == chat_id:
        st.session_state.messages = []
        st.session_state.current_chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")

def ask_provider_stream(history, image_b64: str = None):
    if not openrouter_client:
        yield "❌ Clé `OPENROUTER_API_KEY` manquante."
        return
    model = MODEL_VISION if image_b64 else MODEL_TEXT
    api_messages = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    for msg in history[:-1]:
        txt = " ".join([p for p in msg["content"] if isinstance(p, str)])
        if txt: api_messages.append({"role": msg["role"], "content": txt})
    
    last_txt = " ".join([p for p in history[-1]["content"] if isinstance(p, str)])
    if image_b64 and model == MODEL_VISION:
        api_messages.append({"role": "user", "content": [
            {"type": "text", "text": last_txt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
        ]})
    else:
        if last_txt: api_messages.append({"role": "user", "content": last_txt})

    try:
        stream = openrouter_client.chat.completions.create(model=model, messages=api_messages, stream=True, max_tokens=4096)
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta: yield delta
    except Exception as e:
        yield f"❌ **Erreur :** {str(e)}"

# ═══════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("<div style='font-size: 1.8rem; font-weight: bold; margin-bottom: 5px; color: #A0A0A0;'>Noxus AI</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size: 0.85rem; color: #0078D4; margin-bottom: 15px;'>👤 <b>{st.session_state.username}</b></div>", unsafe_allow_html=True)
    if st.button("🚪 Déconnexion"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()

    st.markdown("---")
    theme_mode   = st.radio("Apparence", ["🌙 Sombre", "☀️ Clair"], horizontal=True)
    accent_color = st.color_picker("Couleur", "#0078D4")

    if st.button("➕ Nouvelle Conversation"):
        st.session_state.messages = []
        st.session_state.current_chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.pending_code = None
        st.rerun()

    st.markdown("<div style='font-size: 0.8rem; color: #888; margin-top: 20px; margin-bottom: 8px;'>Historique</div>", unsafe_allow_html=True)
    for cf in sorted(glob.glob(os.path.join(CHATS_DIR, "*.json")), reverse=True):
        chat_id = os.path.basename(cf).replace(".json", "")
        try:
            with open(cf, "r", encoding="utf-8") as f: title = json.load(f).get("title", chat_id)
        except Exception: title = chat_id
        col_title, col_del = st.columns([5, 1])
        with col_title:
            if st.button(f"💬 {title}", key=f"load_{chat_id}"):
                with open(cf, "r", encoding="utf-8") as f:
                    st.session_state.messages = json.load(f).get("messages", [])
                st.session_state.current_chat_id = chat_id
                st.rerun()
        with col_del:
            if st.button("🗑️", key=f"del_{chat_id}"):
                delete_chat(chat_id)
                st.rerun()

    st.markdown("""
        <div style='position: fixed; bottom: 15px; left: 15px; font-size: 0.85rem; color: #888; font-weight: bold;'>
            ✨ Créée par Noxus
        </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
#  CSS DYNAMIQUE (STYLE GEMINI)
# ═══════════════════════════════════════════════════════════
is_dark      = "Sombre" in theme_mode
bg_color     = "#0E0E0E" if is_dark else "#F5F5F7"
sidebar_bg   = "#161616" if is_dark else "#EBEBEB"
text_color   = "#E0E0E0" if is_dark else "#1A1A1A"
border_color = "#2A2A2A" if is_dark else "#D0D0D0"
user_bg      = "#1E1E1E" if is_dark else "#FFFFFF"

st.markdown(f"""
<style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    [data-testid="stSidebar"] {{ background-color: {sidebar_bg}; border-right: 1px solid {border_color}; }}
    p, h1, h2, h3, h4, li, span {{ color: {text_color} !important; font-family: 'Segoe UI', system-ui, sans-serif; }}
    .stButton>button {{ width: 100%; background-color: transparent !important; color: {text_color} !important; border: none; text-align: left; padding: 8px 12px; border-radius: 6px; font-size: 0.9em; }}
    .stButton>button:hover {{ background-color: {border_color} !important; color: {accent_color} !important; }}
    .stChatMessage {{ background-color: transparent; padding: 10px 0; border: none; }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{ background-color: {user_bg}; border-radius: 10px; padding: 15px; margin: 10px 0; border-left: 3px solid {accent_color}; }}
    [data-testid="chatAvatarIcon-user"] {{ background-color: #555 !important; }}
    [data-testid="chatAvatarIcon-assistant"] {{ background-color: {accent_color} !important; }}
    
    /* STYLE GEMINI POUR LA BARRE DE SAISIE */
    .stChatInputContainer {{ 
        background-color: {user_bg} !important; 
        border: 1px solid {border_color} !important; 
        border-radius: 30px !important; /* Pilule arrondie */
        padding: 5px 15px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }}
    .stChatInputContainer:focus-within {{
        border: 1px solid {accent_color} !important;
    }}
    .stChatFloatingInputContainer {{ 
        background-image: linear-gradient(to top, {bg_color} 80%, transparent); 
        padding-bottom: 30px; 
    }}
    [key*="del_"] button {{ padding: 4px 8px !important; font-size: 0.8em !important; }}
    header {{ visibility: hidden; }}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
#  AFFICHAGE DU CHAT
# ═══════════════════════════════════════════════════════════
chat_title = "Nouvelle Conversation"
if st.session_state.messages:
    first_text = [p for p in st.session_state.messages[0]["content"] if isinstance(p, str)]
    if first_text: chat_title = first_text[0][:40] + "..."
st.markdown(f"<div style='font-size: 1.1rem; font-weight: 600; color: {accent_color}; padding-bottom: 15px; border-bottom: 1px solid {border_color}; margin-bottom: 20px; margin-top: -30px;'>{chat_title}</div>", unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        for part in msg["content"]:
            if isinstance(part, str): st.markdown(part)
            else: st.image(part, width=400)

if st.session_state.pending_code:
    code_to_run = st.session_state.pending_code
    st.warning("⚡ L'IA souhaite exécuter ce code Python :")
    st.code(code_to_run, language="python")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("✅ Exécuter", type="primary"):
            with st.spinner("Exécution..."):
                output = execute_python(code_to_run)
            st.success("**Résultat :**"); st.code(output)
            st.session_state.pending_code = None
    with col_no:
        if st.button("❌ Refuser"):
            st.session_state.pending_code = None; st.rerun()

# ═══════════════════════════════════════════════════════════
#  BARRE DE SAISIE UNIFIÉE NATIVE STREAMLIT
# ═══════════════════════════════════════════════════════════
prompt = st.chat_input(
    "Discutez avec Noxus AI...",
    accept_file=True,
    accept_audio=True
)

if prompt:
    text_content = prompt.text or ""
    image_b64 = None
    img_pil = None
    
    # 🎙️ Gestion Audio
    if hasattr(prompt, "audio") and prompt.audio:
        with st.spinner("🎙️ Transcription..."):
            result = transcribe_audio(prompt.audio.read())
            if result and not result.startswith("[Erreur"):
                st.toast(f"🎙️ Transcrit : {result}", icon="✅")
                text_content = (text_content + " " + result).strip()
            elif result.startswith("[Erreur"):
                st.warning(result)

    if not text_content and not (hasattr(prompt, "files") and prompt.files):
        st.stop()

    # 📸 Gestion Image
    if hasattr(prompt, "files") and prompt.files:
        img_pil = Image.open(prompt.files[0])
        buf = io.BytesIO()
        img_pil.save(buf, format="JPEG")
        image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    search_context = ""
    if text_content and needs_web_search(text_content):
        with st.spinner("🔍 Recherche web..."):
            search_context = web_search(text_content)
        full_prompt = f"{text_content}\n\n---\n{search_context}"
    else:
        full_prompt = text_content

    user_content = [full_prompt] if full_prompt else []
    if img_pil: user_content.append(img_pil)

    st.session_state.messages.append({"role": "user", "content": [text_content] if text_content else []})

    with st.chat_message("user"):
        if text_content: st.markdown(text_content)
        if img_pil: st.image(img_pil, width=200)

    with st.chat_message("assistant"):
        reply_placeholder = st.empty()
        full_reply = ""
        history_for_api = st.session_state.messages[:-1] 
        if user_content: history_for_api.append({"role": "user", "content": [full_prompt]})

        for token in ask_provider_stream(history_for_api, image_b64):
            full_reply += token
            reply_placeholder.markdown(full_reply + "▌")
        reply_placeholder.markdown(full_reply)

    # Remplacement des balises de calcul par le résultat réel
    def replacer(match):
        try: return str(eval(match.group(1), {'__builtins__': None}))
        except Exception: return match.group(0)
    
    final_reply = re.sub(r'\[CALCUL:\s*(.*?)\s*\]', replacer, full_reply)

    if "[IMAGE:" in final_reply:
        start = final_reply.find("[IMAGE:") + 7
        end = final_reply.find("]", start)
        if end != -1:
            img_b64 = generate_and_crop_image(final_reply[start:end])
            final_reply = f"Voici l'image :\n\n![Image générée]({img_b64})"

    # Si le texte a été modifié (calcul ou image), on met à jour l'affichage
    if final_reply != full_reply:
        with st.chat_message("assistant"): st.markdown(final_reply)

    if "[EXECUTE_PYTHON]" in final_reply:
        start = final_reply.find("[EXECUTE_PYTHON]") + 16
        end = final_reply.find("[/EXECUTE_PYTHON]", start)
        if end != -1:
            st.session_state.pending_code = final_reply[start:end].strip()
            st.rerun()

    st.session_state.messages.append({"role": "assistant", "content": [final_reply]})
    save_chat()