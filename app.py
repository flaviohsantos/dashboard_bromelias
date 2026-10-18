import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

from kobo_api import carregar_dados, preparar_campo, preparar_lab, cruzar_campo_lab

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption("Monitoramento mensal e análise laboratorial | Arraial do Cabo-RJ")

# Carregar dados
df_campo_raw, df_lab_raw = carregar_dados()
df_campo = preparar_campo(df_campo_raw)
df_lab = preparar_lab(df_lab_raw)
df = cruzar_campo_lab(df_campo, df_lab)

if df_campo.empty:
    st.warning("Nenhum dado encontrado no KoboToolbox. Verifique se há envios de teste.")
    st.stop()

# Filtros
st.sidebar.header("🔎 Filtros")

col_bairro = "grp_cadastro/bairro"
col_genero = "grp_cadastro/genero"
col_data = "rep_visitas/data_visita"

# 1. Filtro de Bairro
if col_bairro in df_campo.columns:
    bairros = sorted(df_campo[col_bairro].dropna().unique())
    bairro_sel = st.sidebar.multiselect("Bairro", bairros, default=bairros)
else:
    bairro_sel = []

# 2. Filtro de Gênero
if col_genero in df_campo.columns:
    generos = sorted(df_campo[col_genero].dropna().unique())
    genero_sel = st.sidebar.multiselect("Gênero da bromélia", generos, default=generos)
else:
    genero_sel = []

# 3. Filtro de Data (Calendário)
if col_data in df_campo.columns:
    # Converte a coluna para data (datetime) e remove os nulos
    df_campo[col_data] = pd.to_datetime(df_campo[col_data], errors="coerce")
    datas_validas = df_campo[col_data].dropna()
    
    if not datas_validas.empty:
        data_min = datas_validas.min().date()
        data_max = datas_validas.max().date()
        
        # Cria o seletor de intervalo de datas na barra lateral
        periodo_sel = st.sidebar.date_input(
            "Período (Data da Visita)",
            value=(data_min, data_max),
            min_value=data_min,
            max_value=data_max
        )
    else:
        periodo_sel = None
else:
    periodo_sel = None

# Aplica os filtros
df_filtrado = df.copy()

if bairro_sel and col_bairro in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado[col_bairro].isin(bairro_sel)]
    
if genero_sel and col_genero in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado[col_genero].isin(genero_sel)]

# Aplica o filtro de data (se o usuário selecionou um período válido)
if periodo_sel and len(periodo_sel) == 2 and col_data in df_filtrado.columns:
    data_ini, data_fim = periodo_sel
    df_filtrado[col_data] = pd.to_datetime(df_filtrado[col_data], errors="coerce")
    # Filtra as linhas onde a data está dentro do intervalo
    df_filtrado = df_filtrado[
        (df_filtrado[col_data].dt.date >= data_ini) & 
        (df_filtrado[col_data].dt.date <= data_fim)
    ]

# KPIs
st.markdown("### 📊 Indicadores-chave")
c1, c2, c3, c4, c5 = st.columns(5)

# KPIs (atualizados para usar df_filtrado)
n_plantas = df_filtrado["grp_cadastro/id_bromelia_calc"].nunique() if "grp_cadastro/id_bromelia_calc" in df_filtrado.columns else 0
n_visitas = df_filtrado["rep_visitas/data_visita"].notna().sum() if "rep_visitas/data_visita" in df_filtrado.columns else 0
n_amostras = df_filtrado["rep_amostras/id_amostra_calc"].notna().sum() if "rep_amostras/id_amostra_calc" in df_filtrado.columns else 0

col_pres = "rep_amostras/presenca_imaturos"
if col_pres in df_filtrado.columns:
    total = df_filtrado[col_pres].notna().sum()
    positivos = (df_filtrado[col_pres] == "presenca").sum()
    positividade = (positivos / total * 100) if total > 0 else 0
else:
    positividade = 0

col_soma = "rep_especies/soma_contagem"
total_especimes = pd.to_numeric(df_filtrado[col_soma], errors="coerce").sum() if col_soma in df_filtrado.columns else 0

c1.metric("Plantas", n_plantas)
c2.metric("Visitas", n_visitas)
c3.metric("Amostras", n_amostras)
c4.metric("Positividade", f"{positividade:.1f}%")
c5.metric("Espécimes (Lab)", int(total_especimes))

# Mapa
st.markdown("### 🗺️ Mapa das plantas monitoradas")
if "latitude" in df_campo.columns and "longitude" in df_campo.columns:
    df_mapa = df_campo.dropna(subset=["latitude", "longitude"]).copy()
    if not df_mapa.empty:
       # Coordenadas de Arraial do Cabo-RJ
        centro_arraial = [-22.9661, -42.0272]
        m = folium.Map(location=centro_arraial, zoom_start=13, tiles="OpenStreetMap")
        for _, row in df_mapa.iterrows():
            cor = "red" if row.get(col_pres) == "presenca" else "blue"
            popup = f"<b>{row.get('grp_cadastro/id_bromelia_calc', '—')}</b><br>Gênero: {row.get(col_genero, '—')}<br>Bairro: {row.get(col_bairro, '—')}"
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]], radius=7, color=cor, fill=True, fill_color=cor, fill_opacity=0.7, popup=popup
            ).add_to(m)
        st_folium(m, width=None, height=500)
    else:
        st.info("Nenhuma coordenada válida encontrada.")
else:
    st.info("Coluna de geolocalização não encontrada.")

# Série temporal
st.markdown("### 📈 Série temporal de coletas")
col_data = "rep_visitas/data_visita"
if col_data in df_campo.columns:
    df_serie = df_campo[[col_data, "rep_amostras/id_amostra_calc"]].dropna(subset=[col_data]).copy()
    df_serie[col_data] = pd.to_datetime(df_serie[col_data], errors="coerce")
    df_serie["mes"] = df_serie[col_data].dt.to_period("M").astype(str)
    contagem = df_serie.groupby("mes").agg(visitas=(col_data, "count"), amostras=("rep_amostras/id_amostra_calc", "nunique")).reset_index()
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=contagem["mes"], y=contagem["visitas"], name="Visitas", marker_color="#2E86AB"))
    fig.add_trace(go.Bar(x=contagem["mes"], y=contagem["amostras"], name="Amostras", marker_color="#E63946"))
    fig.update_layout(barmode="group", height=400)
    st.plotly_chart(fig, use_container_width=True)

# Gráficos
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("#### 🌱 Plantas por gênero")
    if col_genero in df_campo.columns:
        cont = df_campo[col_genero].value_counts().reset_index()
        cont.columns = ["genero", "quantidade"]
        st.plotly_chart(px.pie(cont, names="genero", values="quantidade", hole=0.4), use_container_width=True)

with col_b:
    st.markdown("#### 🏘️ Plantas por bairro")
    if col_bairro in df_campo.columns:
        cont = df_campo[col_bairro].value_counts().reset_index()
        cont.columns = ["bairro", "quantidade"]
        st.plotly_chart(px.bar(cont, x="quantidade", y="bairro", orientation="h", color="quantidade"), use_container_width=True)

# Tabela
st.markdown("### 📋 Tabela consolidada")
st.dataframe(df_filtrado, use_container_width=True, height=500)