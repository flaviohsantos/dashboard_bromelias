import streamlit as st
import requests
import os

st.title("🔍 Diagnóstico da API do Kobo")

def _get_secret(key, default=""):
    try: return st.secrets[key]
    except: return os.environ.get(key, default)

base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

# Baixa os dados do campo
url_campo = f"{base_url}/api/v2/assets/{uid_campo}/data/"
headers = {"Authorization": f"Token {token}"}
r_campo = requests.get(url_campo, headers=headers).json()

# Baixa os dados do lab
url_lab = f"{base_url}/api/v2/assets/{uid_lab}/data/"
r_lab = requests.get(url_lab, headers=headers).json()

st.markdown("### 1. O que a API do CAMPO está enviando?")
if r_campo.get("results"):
    st.json(r_campo["results"][0])
else:
    st.warning("Nenhum dado de campo encontrado.")

st.markdown("---")

st.markdown("### 2. O que a API do LABORATÓRIO está enviando?")
if r_lab.get("results"):
    st.json(r_lab["results"][0])
else:
    st.warning("Nenhum dado de laboratório encontrado.")
