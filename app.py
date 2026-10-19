import streamlit as st
import pandas as pd
from kobo_api import _get_secret, baixar_formulario

st.set_page_config(page_title="Diagnóstico", layout="wide")
st.title("🛠️ Diagnóstico do Kobo")

base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)

st.write(f"Quantidade de registros de **Campo**: {len(lista_campo)}")
st.write(f"Quantidade de registros de **Laboratório**: {len(lista_lab)}")

st.markdown("---")
st.markdown("### 1. O que o Kobo está enviando para o **Laboratório**?")
if len(lista_lab) > 0:
    st.write("**Chaves do 1º registro:**")
    st.write(list(lista_lab[0].keys()))
    st.write("**Conteúdo completo do 1º registro:**")
    st.json(lista_lab[0])
else:
    st.warning("Nenhum registro de laboratório encontrado.")