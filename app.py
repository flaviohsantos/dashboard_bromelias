import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from datetime import datetime
import requests

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")

st.title("🌿 Dashboard — Diagnóstico do Laboratório")

# --- FUNÇÕES ---
def _get_secret(key, default=""):
    try: return st.secrets[key]
    except: return default

def baixar_formulario(uid, token, base_url):
    if not uid: return []
    url = f"{base_url}/api/v2/assets/{uid}/data/"
    headers = {"Authorization": f"Token {token}"}
    registros = []
    while url:
        r = requests.get(url, headers=headers, params={"format": "json"}, timeout=60)
        r.raise_for_status()
        payload = r.json()
        registros.extend(payload.get("results", []))
        url = payload.get("next")
    return registros

base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados do Laboratório..."):
    lista_lab = baixar_formulario(uid_lab, token, base_url)

st.write(f"O Kobo retornou **{len(lista_lab)}** registros de laboratório.")

if len(lista_lab) > 0:
    st.markdown("### Aqui está o que o Kobo está enviando (Primeiro Registro):")
    # O st.json mostra a estrutura de forma bonita
    st.json(lista_lab[0])
    
    st.markdown("### Aqui estão os nomes das colunas (Chaves):")
    st.write(list(lista_lab[0].keys()))
else:
    st.error("Nenhum dado de laboratório chegou.")