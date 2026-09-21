import streamlit as st
import os
from dotenv import load_dotenv
from google import genai
from openai import OpenAI

# Charge le fichier .env
load_dotenv()

# Configuration Streamlit
st.set_page_config(page_title="Noxus AI", page_icon="🤖", layout="wide")

# Clés API
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GROQ_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

# Initialisation des clients
gemini_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None
groq_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_KEY) if GROQ_KEY else None
openrouter_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_KEY) if OPENROUTER_KEY else None

# Barre latérale (Sidebar) : Choix du modèle et état des API
with st.sidebar:
    st.title("⚙️ Configuration Noxus AI")
    
    # Choix du mode / fournisseur
    mode_selection = st.selectbox(
        "Mode d'IA / Fournisseur :",
        ["Automatique (Fallback)", "Gemini 2.5 Flash", "Groq (Llama 3.3)", "OpenRouter (Gratuit)"]
    )
    
    st.markdown("---")
    st.subheader("📊 État des clés API")
    
    # Indicateurs d'état des clés
    st.write("🟢 **Gemini :**" if GEMINI_KEY and len(GEMINI_KEY) > 10 else "🔴 **Gemini :** Clé manquante/invalide")
    st.write("🟢 **Groq :**" if GROQ_KEY and len(GROQ_KEY) > 10 else "⚪ **Groq :** Non configuré")
    st.write("🟢 **OpenRouter :**" if OPENROUTER_KEY and len(OPENROUTER_KEY) > 10 else "⚪ **OpenRouter :** Non configuré")

# Fonction d'appel unique avec gestion d'erreurs et basculement
def generer_reponse(prompt, mode):
    # 1. Forcer Gemini ou Mode Auto
    if mode in ["Automatique (Fallback)", "Gemini 2.5 Flash"] and gemini_client:
        try:
            res = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return res.text, "Gemini 2.5 Flash"
        except Exception as e:
            if mode == "Gemini 2.5 Flash":
                return f"❌ Erreur Gemini : {e}", "Erreur"
            st.warning("⚠️ Gemini a échoué/limite atteinte. Passage à Groq...")

    # 2. Forcer Groq ou Secours Auto
    if mode in ["Automatique (Fallback)", "Groq (Llama 3.3)"] and groq_client:
        try:
            res = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content, "Groq (Llama 3.3)"
        except Exception as e:
            if mode == "Groq (Llama 3.3)":
                return f"❌ Erreur Groq : {e}", "Erreur"
            st.warning("⚠️ Groq a échoué. Passage à OpenRouter...")

    # 3. Forcer OpenRouter ou Secours Auto
    if mode in ["Automatique (Fallback)", "OpenRouter (Gratuit)"] and openrouter_client:
        try:
            res = openrouter_client.chat.completions.create(
                model="openrouter/free",
                messages=[{"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content, "OpenRouter (Gratuit)"
        except Exception as e:
            return f"❌ Erreur OpenRouter : {e}", "Erreur"

    return "❌ Aucune API n'est disponible ou configurée correctement.", "Erreur"

# Interface Chat Streamlit
st.title("🤖 IA Noxus")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Affichage des messages passés
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "provider" in msg:
            st.caption(f"Propulsé par : {msg['provider']}")

# Saisie utilisateur
if user_prompt := st.chat_input("Décrivez ce qu'il faut construire avec Noxus AI..."):
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        with st.spinner("Réflexion en cours..."):
            reponse, provider = generer_reponse(user_prompt, mode_selection)
            st.markdown(reponse)
            st.caption(f"Propulsé par : {provider}")
            st.session_state.messages.append({"role": "assistant", "content": reponse, "provider": provider})