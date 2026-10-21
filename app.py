import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Bromélias", layout="wide")
st.title("🌿 Dashboard Bromélias - Modo de Segurança")

if not os.path.exists("campo.xlsx") or not os.path.exists("lab.xlsx"):
    st.error("Arquivos não encontrados.")
    st.stop()

# Mostra o que tem dentro dos arquivos, sem tentar cruzar nada
try:
    st.write("### Dados do Campo (Campo.xlsx)")
    df_campo = pd.read_excel("campo.xlsx", sheet_name=0)
    st.write(f"O arquivo de campo tem {len(df_campo)} linhas e {len(df_campo.columns)} colunas.")
    st.dataframe(df_campo.head()) # Mostra as primeiras linhas

    st.write("### Dados do Laboratório (Lab.xlsx)")
    df_lab = pd.read_excel("lab.xlsx", sheet_name=0)
    st.write(f"O arquivo de laboratório tem {len(df_lab)} linhas e {len(df_lab.columns)} colunas.")
    st.dataframe(df_lab.head())

except Exception as e:
    st.error(f"Erro ao ler: {e}")
