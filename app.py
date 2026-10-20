import streamlit as st
import pandas as pd

st.title("🔍 Diagnóstico da Aba de Visitas")

try:
    # Lê todas as abas do arquivo de campo
    abas = pd.read_excel("campo.xlsx", sheet_name=None)
    
    st.write(f"O arquivo tem {len(abas)} abas.")
    
    for nome_aba, df in abas.items():
        st.write(f"### Aba: '{nome_aba}'")
        st.write(f"Colunas: {list(df.columns)}")
        st.write("---")
        
except Exception as e:
    st.error(f"Erro: {e}")