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

# --- FUNÇÃO CAÇADORA DE COLUNAS ---
def achar_coluna(df, *termos):
    for col in df.columns:
        if all(t in str(col).lower() for t in termos):
            return col
    return None

@st.cache_data
def carregar_dados():
    try:
        df_campo = pd.read_excel(ARQUIVO_CAMPO, sheet_name=0)
        df_visitas = pd.read_excel(ARQUIVO_CAMPO, sheet_name="rep_visitas")
        df_amostras = pd.read_excel(ARQUIVO_CAMPO, sheet_name="rep_amostras")
        df_lab = pd.read_excel(ARQUIVO_LAB, sheet_name=0)
        df_especies = pd.read_excel(ARQUIVO_LAB, sheet_name=1)
        return df_campo, df_visitas, df_amostras, df_lab, df_especies
    except Exception as e:
        st.error(f"Erro ao ler as abas: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_campo, df_visitas, df_amostras, df_lab, df_especies = carregar_dados()

if df_campo.empty or df_lab.empty or df_especies.empty:
    st.stop()

# --- TRATAMENTO DOS DADOS ---
# 1. Plantas
col_id_planta = achar_coluna(df_campo, "código único da planta") or achar_coluna(df_campo, "id_bromelia")
if not col_id_planta:
    st.error(f"Não achei a coluna de ID da planta. Colunas: {list(df_campo.columns)}")
    st.stop()

df_plantas = pd.DataFrame({
    "id_bromelia": df_campo[col_id_planta],
    "bairro": df_campo[achar_coluna(df_campo, "bairro")] if achar_coluna(df_campo, "bairro") else "N/I",
    "genero": df_campo[achar_coluna(df_campo, "gênero")] if achar_coluna(df_campo, "gênero") else "N/I",
    "lat": pd.to_numeric(df_campo[achar_coluna(df_campo, "latitude")], errors="coerce") if achar_coluna(df_campo, "latitude") else None,
    "lon": pd.to_numeric(df_campo[achar_coluna(df_campo, "longitude")], errors="coerce") if achar_coluna(df_campo, "longitude") else None
})

# 2. Amostras (Campo) -> Caça a coluna de ID da amostra
col_amostra_campo = achar_coluna(df_amostras, "id_amostra") or achar_coluna(df_amostras, "código da amostra")
if not col_amostra_campo:
    st.error(f"Não achei a coluna de ID da amostra no campo. Colunas: {list(df_amostras.columns)}")
    st.stop()

df_amostras_tratado = pd.DataFrame({
    "id_bromelia_visita": df_visitas["id_bromelia_visita"],
    "id_amostra_campo": df_amostras[col_amostra_campo].astype(str).str.strip()
})

# 3. Laboratório -> Caça a coluna de ID da amostra
col_amostra_lab = achar_coluna(df_lab, "código da amostra") or achar_coluna(df_lab, "id_amostra")
if not col_amostra_lab:
    st.error(f"Não achei a coluna de ID da amostra no lab. Colunas: {list(df_lab.columns)}")
    st.stop()

df_lab_tratado = pd.DataFrame({
    "id_amostra_lab": df_lab[col_amostra_lab].astype(str).str.strip(),
    "submission_id": df_lab["_id"].astype(str)
})

# 4. Espécies
col_especie = achar_coluna(df_especies, "espécie identificada")
col_contagem = achar_coluna(df_especies, "soma_contagem")
col_submission = achar_coluna(df_especies, "_submission__id")

if not col_especie or not col_contagem:
    st.error(f"Não achei as colunas de espécie/contagem. Colunas: {list(df_especies.columns)}")
    st.stop()

df_especies_tratado = pd.DataFrame({
    "especie": df_especies[col_especie].astype(str).str.lower().str.strip(),
    "contagem": pd.to_numeric(df_especies[col_contagem], errors="coerce").fillna(0),
    "submission_id": df_especies[col_submission].astype(str) if col_submission else None
})

# Junta espécies com o lab
df_lab_completo = pd.merge(df_lab_tratado, df_especies_tratado, on="submission_id", how="left")

# --- CRUZAMENTO (Pelo ID da amostra) ---
df_merge = pd.merge(
    df_amostras_tratado,
    df_lab_completo,
    left_on="id_amostra_campo",
    right_on="id_amostra_lab",
    how="left"
)

# Agrupa por planta (id_bromelia_visita)
df_por_planta = df_merge.groupby("id_bromelia_visita").agg({
    "especie": lambda x: ', '.join(x.dropna().unique()),
    "contagem": "sum"
}).reset_index()

# Junta com as plantas
df_final = pd.merge(df_plantas, df_por_planta, left_on="id_bromelia", right_on="id_bromelia_visita", how="left")

# --- REGRA DO AEDES ---
df_final["especie"] = df_final["especie"].fillna("Não informado").astype(str)
df_final["especie"] = df_final["especie"].str.replace("_", " ").str.capitalize()
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
