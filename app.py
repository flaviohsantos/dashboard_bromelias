import streamlit as st
import pandas as pd
import os

st.title("Dashboard Bromélias - Teste de Leitura")

if not os.path.exists("campo.xlsx") or not os.path.exists("lab.xlsx"):
    st.error("Arquivos não encontrados.")
    st.stop()

try:
    df_campo = pd.read_excel("campo.xlsx", sheet_name=0)
    st.success(f"✅ Arquivo campo.xlsx lido! {len(df_campo)} linhas.")
except Exception as e:
    st.error(f"Erro no campo: {e}")

try:
    df_lab = pd.read_excel("lab.xlsx", sheet_name=0)
    st.success(f"✅ Arquivo lab.xlsx lido! {len(df_lab)} linhas.")
except Exception as e:
    st.error(f"Erro no lab: {e}")
