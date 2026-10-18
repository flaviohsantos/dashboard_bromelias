import streamlit as st
import pandas as pd
from kobo_api import _get_secret, baixar_formulario

st.set_page_config(page_title="Diagnóstico", layout="wide")
st.title("🛠️ Diagnóstico do Kobo")

base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados crus..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)

st.write(f"Quantidade de registros de **Campo** encontrados: {len(lista_campo)}")
st.write(f"Quantidade de registros de **Laboratório** encontrados: {len(lista_lab)}")

st.markdown("---")
st.markdown("### 1. O que o Kobo está enviando para a **Planta** (Campo)?")
if len(lista_campo) > 0:
    st.write("Aqui estão as chaves (colunas) que chegaram no primeiro registro de campo:")
    st.json(list(lista_campo[0].keys()))
    
    st.write("Aqui está o conteúdo do primeiro registro de campo (para você ver onde estão os dados):")
    st.json(lista_campo[0])

st.markdown("---")
st.markdown("### 2. O que o Kobo está enviando para o **Laboratório**?")
if len(lista_lab) > 0:
    st.write("Aqui estão as chaves (colunas) que chegaram no primeiro registro de laboratório:")
    st.json(list(lista_lab[0].keys()))
    
    st.write("Aqui está o conteúdo do primeiro registro de laboratório:")
    st.json(lista_lab[0])