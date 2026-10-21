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
        df_campo = pd.read_excel(ARQUIVO_CAMPO, sheet_name="Pesquisa Bromélias Ornamenta...")
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

# --- FUNÇÃO CAÇADORA DE COLUNAS ---
def encontrar_coluna(df, termo):
    # Procura a coluna cujo nome contenha o termo (ignora maiúsculas/minúsculas)
    for col in df.columns:
        if termo.lower() in str(col).lower():
            return col
    return None

# --- TRATAMENTO DOS DADOS ---
# 1. Plantas
col_id_planta = encontrar_coluna(df_campo, "id_bromelia_calc") or encontrar_coluna(df_campo, "código único")
col_bairro = encontrar_coluna(df_campo, "bairro")
col_genero = encontrar_coluna(df_campo, "gênero da bromélia")
col_lat = encontrar_coluna(df_campo, "latitude")
col_lon = encontrar_coluna(df_campo, "longitude")

df_plantas = pd.DataFrame({
    "id_bromelia": df_campo[col_id_planta],
    "bairro": df_campo[col_bairro],
    "genero": df_campo[col_genero],
    "lat": pd.to_numeric(df_campo[col_lat], errors="coerce"),
    "lon": pd.to_numeric(df_campo[col_lon], errors="coerce")
})

# 2. Amostras (Campo)
col_id_visita_amostra = encontrar_coluna(df_amostras, "id_amostra_calc") or encontrar_coluna(df_amostras, "código da amostra")
col_id_visita = encontrar_coluna(df_visitas, "id_bromelia_visita")

df_amostras_tratado = pd.DataFrame({
    "id_bromelia_visita": df_visitas[col_id_visita],
    "codigo_amostra": df_amostras[col_id_visita_amostra].astype(str).str.strip()
})

# 3. Laboratório
col_codigo_lab = encontrar_coluna(df_lab, "código da amostra")
col_especie = encontrar_coluna(df_especies, "espécie identificada")
col_contagem = encontrar_coluna(df_especies, "soma_contagem")

df_lab_tratado = pd.DataFrame({
    "codigo_amostra": df_lab[col_codigo_lab].astype(str).str.strip(),
    "submission_id": df_lab["_id"].astype(str)
})

df_especies_tratado = pd.DataFrame({
    "especie": df_especies[col_especie].astype(str).str.lower().str.strip(),
    "contagem": pd.to_numeric(df_especies[col_contagem], errors="coerce").fillna(0),
    "submission_id": df_especies["_submission__id"].astype(str)
})

df_especies_com_amostra = pd.merge(df_especies_tratado, df_lab_tratado, on="submission_id", how="left")

df_lab_agrupado = df_especies_com_amostra.groupby("codigo_amostra").agg({
    "especie": lambda x: ', '.join(x.unique()),
    "contagem": "sum"
}).reset_index()

# 4. Cruza campo com lab
df_visitas_com_lab = pd.merge(
    df_amostras_tratado,
    df_lab_agrupado,
    on="codigo_amostra",
    how="left"
)

df_visitas_por_planta = df_visitas_com_lab.groupby("id_bromelia_visita").agg({
    "especie": lambda x: ', '.join(x.dropna().unique()),
    "contagem": "sum"
}).reset_index()

# Junta com as plantas
df_final = pd.merge(df_plantas, df_visitas_por_planta, left_on="id_bromelia", right_on="id_bromelia_visita", how="left")

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
    
    for _, row in df_mapa.iterrows():
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