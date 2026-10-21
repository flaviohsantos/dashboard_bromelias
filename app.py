import streamlit as st
import pandas as pd
import os

st.title("Dashboard Bromélias")
st.write("Pesquisador: Flávio Santos")

if not os.path.exists("campo.xlsx") or not os.path.exists("lab.xlsx"):
    st.error("Arquivos não encontrados.")
    st.stop()

# Leitura simples dos arquivos
df_campo = pd.read_excel("campo.xlsx", sheet_name=0)
df_visitas = pd.read_excel("campo.xlsx", sheet_name="rep_visitas")
df_lab = pd.read_excel("lab.xlsx", sheet_name=0)
df_especies = pd.read_excel("lab.xlsx", sheet_name=1)

# Cruza pela data para não dar erro de ID
df_visitas["Data da visita"] = pd.to_datetime(df_visitas["Data da visita"], errors="coerce")
df_lab["Data do processamento"] = pd.to_datetime(df_lab["Data do processamento"], errors="coerce")

# Agrupa dados
df_visitas = df_visitas.sort_values("Data da visita")
df_lab = df_lab.sort_values("Data do processamento")

df_merge = pd.merge_asof(
    df_visitas, df_lab, 
    left_on="Data da visita", right_on="Data do processamento", 
    direction="nearest", tolerance=pd.Timedelta(days=15)
)

# Junta com espécies
df_especies["Data do processamento"] = df_merge["Data do processamento"].iloc[0] if not df_merge.empty else None
df_especies_final = pd.merge(df_especies, df_lab[["Data do processamento", "_id"]], on="_id", how="left")

# Mostra os dados na tela para conferir
st.subheader("Dados do Laboratório Carregados")
st.dataframe(df_especies_final)

st.subheader("Visitas e Datas")
st.dataframe(df_visitas[["id_bromelia_visita", "Data da visita"]])
