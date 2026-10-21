import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import os

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption("Pesquisador: Flávio Santos (IOC - Fiocruz) | fhsantos@gmail.com")
st.markdown("---")

ARQUIVO_CAMPO = "campo.xlsx"
ARQUIVO_LAB = "lab.xlsx"

if not os.path.exists(ARQUIVO_CAMPO) or not os.path.exists(ARQUIVO_LAB):
    st.error("⚠️ Arquivos 'campo.xlsx' e 'lab.xlsx' não encontrados.")
    st.stop()

@st.cache_data
def carregar_dados():
    try:
        abas_campo = pd.read_excel(ARQUIVO_CAMPO, sheet_name=None)
        df_campo = next(df for nome, df in abas_campo.items() if "pesquisa" in nome.lower())
        df_amostras = next(df for nome, df in abas_campo.items() if "amostra" in nome.lower())
        
        abas_lab = pd.read_excel(ARQUIVO_LAB, sheet_name=None)
        df_lab = list(abas_lab.values())[0]
        df_especies = list(abas_lab.values())[1]
        
        return df_campo, df_amostras, df_lab, df_especies
    except Exception as e:
        st.error(f"Erro ao ler as abas: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_campo, df_amostras, df_lab, df_especies = carregar_dados()

if df_campo.empty or df_lab.empty or df_especies.empty:
    st.stop()

# --- TRATAMENTO DOS DADOS ---
# 1. Plantas
df_plantas = pd.DataFrame({
    "id_bromelia": df_campo["Código único da planta"],
    "bairro": df_campo["Bairro"],
    "genero": df_campo["Gênero da bromélia"],
    "lat": pd.to_numeric(df_campo["_Geolocalização da planta_latitude"], errors="coerce"),
    "lon": pd.to_numeric(df_campo["_Geolocalização da planta_longitude"], errors="coerce")
})

# 2. Amostras (Campo)
df_amostras_tratado = pd.DataFrame({
    "codigo_amostra_campo": df_amostras["codigo_amostra"].astype(str).str.strip()
})

# 3. Laboratório (Cabeçalho)
col_codigo_lab = "Código da amostra (Ex: BRO-2610181726-30)"
df_lab_tratado = pd.DataFrame({
    "codigo_amostra_lab": df_lab[col_codigo_lab].astype(str).str.strip(),
    "id_envio_lab": df_lab["_id"].astype(str)
})

# 4. Laboratório (Espécies)
# A CORREÇÃO ESTÁ AQUI: usar a coluna 'soma_contagem' de cada espécie
col_especie = next((c for c in df_especies.columns if "Espécie identificada" in str(c)), None)
col_contagem = next((c for c in df_especies.columns if "soma_contagem" in str(c)), None)

df_especies_tratado = pd.DataFrame({
    "especie": df_especies[col_especie].astype(str).str.lower().str.strip(),
    "contagem": pd.to_numeric(df_especies[col_contagem], errors="coerce").fillna(0),
    "id_envio_lab": df_especies["_submission__id"].astype(str)
})

# Agrupa espécies
df_especies_agrupado = df_especies_tratado.groupby(["id_envio_lab", "especie"]).agg({
    "contagem": "sum"
}).reset_index()

df_lab_completo = pd.merge(df_lab_tratado, df_especies_agrupado, on="id_envio_lab", how="left")

# 5. Cruza Campo com Lab
df_cruzado = pd.merge(
    df_amostras_tratado,
    df_lab_completo,
    left_on="codigo_amostra_campo",
    right_on="codigo_amostra_lab",
    how="left"
)

# Extrai a planta do código da amostra
df_cruzado["id_bromelia"] = df_cruzado["codigo_amostra_campo"].astype(str).str.rsplit('-', n=1).str[0]

# Agrupa por planta e espécie
df_agrupado = df_cruzado.groupby(["id_bromelia", "especie"]).agg({
    "contagem": "sum"
}).reset_index()

# Junta com as plantas (para pegar lat/lon)
df_final = pd.merge(df_plantas, df_agrupado, on="id_bromelia", how="left")

df_final["especie"] = df_final["especie"].fillna("Não informado").astype(str).str.replace("_", " ").str.capitalize()
df_final["contagem"] = pd.to_numeric(df_final["contagem"], errors="coerce").fillna(0)

# --- MÉTRICAS ---
n_plantas = df_final["id_bromelia"].nunique()
total_especimes = df_final["contagem"].sum()
tem_aedes = df_final["especie"].str.contains("Aedes", case=False, na=False)
plantas_positivas = df_final[tem_aedes]["id_bromelia"].nunique()
positividade = (plantas_positivas / n_plantas * 100) if n_plantas > 0 else 0

st.markdown("### 📊 Indicadores")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Plantas", n_plantas)
c2.metric("Espécimes (Lab)", int(total_especimes))
c3.metric("Plantas Positivas", plantas_positivas)
c4.metric("Positividade", f"{positividade:.1f}%")

st.markdown("---")

# --- MAPAS ---
st.markdown("### 🗺️ Mapa de Risco (Raio de 100m)")
df_mapa = df_final.dropna(subset=["lat", "lon"])

if not df_mapa.empty:
    m = folium.Map(location=[-22.9661, -42.0272], zoom_start=15, tiles="OpenStreetMap")
    ids_positivos = df_final[tem_aedes]["id_bromelia"].unique()
    
    # Para o mapa, precisamos pegar uma linha única por planta
    df_mapa_unico = df_mapa.drop_duplicates(subset=["id_bromelia"])
    
    for _, row in df_mapa_unico.iterrows():
        if row["id_bromelia"] in ids_positivos:
            folium.Circle(location=[row["lat"], row["lon"]], radius=100, color="#E63946", fill=True, fill_opacity=0.2, weight=2).add_to(m)
            folium.Marker(location=[row["lat"], row["lon"]], icon=folium.Icon(color="red"), popup=f"{row['id_bromelia']}").add_to(m)
        else:
            folium.Marker(location=[row["lat"], row["lon"]], icon=folium.Icon(color="blue"), popup=f"{row['id_bromelia']}").add_to(m)
    st_folium(m, width=None, height=500, key="mapa")
else:
    st.info("Sem coordenadas para o mapa.")

# --- GRÁFICO DE ESPÉCIES ---
st.markdown("---")
st.markdown("### 🦟 Frequência de Espécies")

# Agrupa os totais por espécie (somando todas as plantas)
df_esp_chart = df_final[df_final["especie"] != "Não informado"].groupby("especie").agg(
    Total=("contagem", "sum")
).reset_index()

if not df_esp_chart.empty and df_esp_chart["Total"].sum() > 0:
    st.plotly_chart(px.bar(df_esp_chart, x="especie", y="Total", color="especie", text="Total"), use_container_width=True)
    
    st.markdown("#### 📋 Totais")
    st.dataframe(df_esp_chart.rename(columns={"especie": "Espécie", "Total": "Larvas"}), hide_index=True)
else:
    st.info("Nenhuma larva registrada.")

st.markdown("---")
st.caption("Dashboard desenvolvido por Flávio Santos | PPG-VCV / IOC - Fiocruz | Contato: fhsantos@gmail.com")