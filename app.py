import streamlit as st
import pandas as pd
import os

st.title("🔍 Diagnóstico no GitHub")

if os.path.exists("campo.xlsx"):
    st.success("✅ O arquivo 'campo.xlsx' ESTÁ no GitHub!")
    df = pd.read_excel("campo.xlsx")
    st.write(f"Colunas: {list(df.columns)}")
    st.write(f"Linhas: {len(df)}")
else:
    st.error("❌ O arquivo 'campo.xlsx' NÃO está no GitHub.")

st.markdown("---")

if os.path.exists("lab.xlsx"):
    st.success("✅ O arquivo 'lab.xlsx' ESTÁ no GitHub!")
    df = pd.read_excel("lab.xlsx")
    st.write(f"Colunas: {list(df.columns)}")
else:
    st.error("❌ O arquivo 'lab.xlsx' NÃO está no GitHub.")