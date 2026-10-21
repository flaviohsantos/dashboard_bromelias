import streamlit as st
import pandas as pd
import plotly.express as px
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
    st.error("⚠️ Arquivos não encontrados.")
    st.stop()

@st.cache_data
def carregar_dados():
    try:
        df_campo = pd.read_excel(ARQUIVO_CAMPO, sheet_name=0)
        df_lab = pd.read_excel(ARQUIVO_LAB, sheet_name=0)
        df_especies = pd.read_excel(ARQUIVO_LAB, sheet_name=1)
        return df_campo, df_lab, df_especies
    except Exception as e:
        st.error(f"Erro: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_campo, df_lab, df_especies = carregar_dados()

if df_campo.empty or df_lab.empty or df_especies.empty:
    st.stop()

# --- TRATAMENTO (Cruzamento pelo Código Base da Planta) ---
# 1. Plantas (Pega o código único e as coordenadas)
df_plantas = pd.DataFrame({
    "id_bromelia": df_campo["Código único da planta"],
    "bairro": df_campo["Bairro"],
    "genero": df_campo["Gênero da bromélia"],
    "lat": pd.to_numeric(df_campo["_Geolocalização da planta_latitude"], errors="coerce"),
    "lon": pd.to_numeric(df_campo["_Geolocalização da planta_longitude"], errors="coerce")
})

# 2. Laboratório (Extrai a base do código da amostra)
# Ex: "BRO-2610210802-30" vira "BRO-2610210802"
df_lab["id_planta_base"] = df_lab["Código da amostra"].astype(str).str.rsplit('-', n=1).str[0]

# 3. Espécies (Pega o _submission__id para cruzar com o lab)
df_especies_tratado = pd.DataFrame({
    "especie": df_especies["Espécie identificada"].astype(str).str.lower().str.strip(),
    "contagem": pd.to_numeric(df_especies["soma_contagem"], errors="coerce").fillna(0),
    "submission_id": df_especies["_submission__id"].astype(str)
})

# Junta o laboratório com as espécies
df_lab_completo = pd.merge(
    df_lab[["_id", "id_planta_base"]].astype(str), 
    df_especies_tratado, 
    left_on="_id", right_on="submission_id", how="left"
)

# Agrupa por planta base
df_agrupado = df_lab_completo.groupby("id_planta_base").agg({
    "especie": lambda x: ', '.join(x.dropna().unique()),
    "contagem": "sum"
}).reset_index()

# Junta com as plantas
df_final = pd.merge(df_plantas, df_agrupado, left_on="id_bromelia", right_on="id_planta_base", how="left")

# Limpeza e Regra do Aedes
df_final["especie"] = df_final["especie"].fillna("Não informado").astype(str).str.replace("_", " ").str.capitalize()
df_final["contagem"] = pd.to_numeric(df_final["contagem"], errors="coerce").fillna(0)
df_final["positivo"] = df_final["especie"].str.lower().str.contains("aedes", na=False)

# --- MÉTRICAS ---
n_plantas = df_final["id_bromelia"].nunique()
total_especimes = df_final["contagem"].sum()
plantas_positivas = df_final[df_final["positivo"]]["id_bromelia"].nunique()
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
    centro_lat = df_mapa["lat"].mean()
    centro_lon = df_mapa["lon"].mean()
    m = folium.Map(location=[centro_lat, centro_lon], zoom_start=16, tiles="OpenStreetMap")
    
    for _, row in df_mapa.iterrows():
        if row["positivo"]:
            folium.Circle(location=[row["lat"], row["lon"]], radius=100, color="#E63946", fill=True, fill_color="#E63946", fill_opacity=0.2, weight=2).add_to(m)
            folium.Marker(location=[row["lat"], row["lon"]], icon=folium.Icon(color="red", icon="info-sign"), popup=f"<b>{row['id_bromelia']}</b><br>POSITIVO ({row['especie']})").add_to(m)
        else:
            folium.Marker(location=[row["lat"], row["lon"]], icon=folium.Icon(color="blue", icon="info-sign"), popup=f"<b>{row['id_bromelia']}</b><br>Negativo ({row['especie']})").add_to(m)
    st_folium(m, width=None, height=500, key="mapa")
else:
    st.info("Sem coordenadas para o mapa.")

# --- GRÁFICO ---
st.markdown("---")
st.markdown("### 🦟 Frequência de Espécies")
lista_especies = []
for _, row in df_final.iterrows():
    if row["especie"] != "Não informado":
        for esp in str(row["especie"]).split(','):
            if esp.strip():
                lista_especies.append({"Especie": esp.strip(), "Total": row["contagem"]})

if lista_especies:
    df_esp_chart = pd.DataFrame(lista_especies).groupby("Especie").sum().reset_index()
    st.plotly_chart(px.bar(df_esp_chart, x="Especie", y="Total", color="Especie", text="Total"), use_container_width=True)
    st.markdown("#### 📋 Totais")
    st.dataframe(df_esp_chart.rename(columns={"Especie": "Espécie", "Total": "Larvas"}), hide_index=True)
else:
    st.info("Nenhuma larva registrada.")

st.markdown("---")
st.caption("Dashboard desenvolvido por Flávio Santos | PPG-VCV / IOC - Fiocruz | Contato: fhsantos@gmail.com")
