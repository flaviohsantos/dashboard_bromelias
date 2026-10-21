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
        # Lê a PRIMEIRA aba (índice 0) como sendo o cadastro da planta
        df_campo = pd.read_excel(ARQUIVO_CAMPO, sheet_name=0)
        # Lê as abas de visitas e amostras pelo nome (que geralmente não mudam)
        df_visitas = pd.read_excel(ARQUIVO_CAMPO, sheet_name="rep_visitas")
        
        # Lê o laboratório
        df_lab = pd.read_excel(ARQUIVO_LAB, sheet_name=0)
        df_especies = pd.read_excel(ARQUIVO_LAB, sheet_name=1)
        
        return df_campo, df_visitas, df_lab, df_especies
    except Exception as e:
        st.error(f"Erro ao ler as abas: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_campo, df_visitas, df_lab, df_especies = carregar_dados()

if df_campo.empty or df_lab.empty or df_especies.empty:
    st.stop()

# --- TRATAMENTO DOS DADOS (Cruzamento por Data) ---
# 1. Plantas
df_plantas = pd.DataFrame({
    "id_bromelia": df_campo["id_bromelia_calc"],
    "bairro": df_campo["Bairro"],
    "genero": df_campo["Gênero da bromélia"],
    "lat": pd.to_numeric(df_campo["_Geolocalização da planta_latitude"], errors="coerce"),
    "lon": pd.to_numeric(df_campo["_Geolocalização da planta_longitude"], errors="coerce")
})

# 2. Visitas (com data)
df_visitas_tratado = pd.DataFrame({
    "id_bromelia": df_visitas["id_bromelia_visita"],
    "data_visita": pd.to_datetime(df_visitas["Data da visita"], errors="coerce", dayfirst=True)
})

# 3. Laboratório (com data de processamento)
df_lab_tratado = pd.DataFrame({
    "data_processamento": pd.to_datetime(df_lab["Data do processamento"], errors="coerce", dayfirst=True),
    "submission_id": df_lab["_id"].astype(str)
})

# 4. Espécies
df_especies_tratado = pd.DataFrame({
    "especie": df_especies["Espécie identificada"].astype(str).str.lower().str.strip(),
    "contagem": pd.to_numeric(df_especies["soma_contagem"], errors="coerce").fillna(0),
    "submission_id": df_especies["_submission__id"].astype(str)
})

# Junta espécies com a data de processamento
df_especies_com_data = pd.merge(df_especies_tratado, df_lab_tratado, on="submission_id", how="left")

# Agrupa as espécies por data
df_lab_agrupado = df_especies_com_data.groupby("data_processamento").agg({
    "especie": lambda x: ', '.join(x.unique()),
    "contagem": "sum"
}).reset_index()

# --- O CRUZAMENTO PELA DATA (merge_asof) ---
df_visitas_tratado = df_visitas_tratado.sort_values("data_visita")
df_lab_agrupado = df_lab_agrupado.sort_values("data_processamento")

df_visitas_com_lab = pd.merge_asof(
    df_visitas_tratado,
    df_lab_agrupado,
    left_on="data_visita",
    right_on="data_processamento",
    direction="nearest",
    tolerance=pd.Timedelta(days=15)
)

# Agrupa as espécies por planta
df_visitas_por_planta = df_visitas_com_lab.groupby("id_bromelia").agg({
    "especie": lambda x: ', '.join(x.dropna().unique()),
    "contagem": "sum"
}).reset_index()

# Junta com as plantas
df_final = pd.merge(df_plantas, df_visitas_por_planta, on="id_bromelia", how="left")

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

# --- MAPAS (COM ZOOM INTELIGENTE) ---
st.markdown("### 🗺️ Mapa de Risco (Raio de 100m)")
df_mapa = df_final.dropna(subset=["lat", "lon"])

if not df_mapa.empty:
    centro_lat = df_mapa["lat"].mean()
    centro_lon = df_mapa["lon"].mean()
    
    m = folium.Map(location=[centro_lat, centro_lon], zoom_start=16, tiles="OpenStreetMap")
    
    ids_positivos = df_final[tem_aedes]["id_bromelia"].unique()
    
    for _, row in df_mapa.iterrows():
        if row["id_bromelia"] in ids_positivos:
            folium.Circle(
                location=[row["lat"], row["lon"]], 
                radius=100, 
                color="#E63946", 
                fill=True, 
                fill_color="#E63946", 
                fill_opacity=0.2, 
                weight=2,
                popup="Raio 100m (Aedes)"
            ).add_to(m)
            folium.Marker(
                location=[row["lat"], row["lon"]], 
                icon=folium.Icon(color="red", icon="info-sign"), 
                popup=f"<b>{row['id_bromelia']}</b><br>POSITIVO"
            ).add_to(m)
        else:
            folium.Marker(
                location=[row["lat"], row["lon"]], 
                icon=folium.Icon(color="blue", icon="info-sign"), 
                popup=f"<b>{row['id_bromelia']}</b><br>Negativo"
            ).add_to(m)
            
    st_folium(m, width=None, height=500, key="mapa")
else:
    st.info("Sem coordenadas para o mapa.")

# --- GRÁFICO DE ESPÉCIES ---
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
