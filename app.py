import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from kobo_api import _get_secret, baixar_formulario, preparar_dados_completos

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption("Monitoramento mensal e análise laboratorial | Arraial do Cabo-RJ")

# 1. Carregar dados
base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

if not token or not uid_campo:
    st.error("⚠️ Configure KOBO_TOKEN e UID_CAMPO em .streamlit/secrets.toml")
    st.stop()

with st.spinner("Baixando dados..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)
    df_plantas, df_dados = preparar_dados_completos(lista_campo, lista_lab)

if df_plantas.empty:
    st.warning("Nenhum dado encontrado.")
    st.stop()

# 2. Filtros
st.sidebar.header("🔎 Filtros")

# Filtro de Bairro
bairros = sorted(df_plantas["bairro"].dropna().unique())
bairro_sel = st.sidebar.multiselect("Bairro", bairros, default=bairros)

# Filtro de Gênero
generos = sorted(df_plantas["genero"].dropna().unique())
genero_sel = st.sidebar.multiselect("Gênero da bromélia", generos, default=generos)

# Filtro de Data
data_padrao_inicio = pd.Timestamp.today().date() - pd.Timedelta(days=30)
data_padrao_fim = pd.Timestamp.today().date()
periodo_sel = st.sidebar.date_input("Período (Data da Visita)", value=(data_padrao_inicio, data_padrao_fim))

# 3. Aplicar filtros
df_plantas_filtrado = df_plantas.copy()
df_dados_filtrado = df_dados.copy()

if bairro_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["bairro"].isin(bairro_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["bairro"].isin(bairro_sel)]

if genero_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["genero"].isin(genero_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["genero"].isin(genero_sel)]

# Filtro de data protegido
if len(periodo_sel) == 2 and not df_dados_filtrado.empty and "data_visita" in df_dados_filtrado.columns:
    # Força a conversão para data
    df_dados_filtrado["data_visita"] = pd.to_datetime(df_dados_filtrado["data_visita"], errors="coerce")
    
    # Filtra usando .dt.date para garantir a comparação correta
    df_dados_filtrado = df_dados_filtrado[
        (df_dados_filtrado["data_visita"].dt.date >= periodo_sel[0]) & 
        (df_dados_filtrado["data_visita"].dt.date <= periodo_sel[1])
    ]

# 4. KPIs
st.markdown("### 📊 Indicadores-chave")
c1, c2, c3, c4, c5 = st.columns(5)

n_plantas = df_plantas_filtrado["id_bromelia_calc"].nunique()
n_visitas = df_dados_filtrado["data_visita"].notna().sum() if "data_visita" in df_dados_filtrado.columns else 0
n_amostras = df_dados_filtrado["id_amostra_calc"].notna().sum() if "id_amostra_calc" in df_dados_filtrado.columns else 0

total_presenca = df_dados_filtrado["presenca_imaturos"].notna().sum() if "presenca_imaturos" in df_dados_filtrado.columns else 0
positivos = (df_dados_filtrado["presenca_imaturos"] == "presenca").sum() if "presenca_imaturos" in df_dados_filtrado.columns else 0
positividade = (positivos / total_presenca * 100) if total_presenca > 0 else 0

total_especimes = pd.to_numeric(df_dados_filtrado["soma_contagem"], errors="coerce").sum() if "soma_contagem" in df_dados_filtrado.columns else 0

c1.metric("Plantas", n_plantas)
c2.metric("Visitas", n_visitas)
c3.metric("Amostras", n_amostras)
c4.metric("Positividade", f"{positividade:.1f}%")
c5.metric("Espécimes (Lab)", int(total_especimes))

# 5. Mapa
st.markdown("### 🗺️ Mapa das plantas monitoradas")
df_mapa = df_plantas_filtrado.dropna(subset=["latitude", "longitude"])
if not df_mapa.empty:
    m = folium.Map(location=[-22.9661, -42.0272], zoom_start=13, tiles="OpenStreetMap")
    for _, row in df_mapa.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]], radius=7, color="blue", fill=True, fill_color="blue", fill_opacity=0.7,
            popup=f"<b>{row['id_bromelia_calc']}</b><br>Gênero: {row['genero']}<br>Bairro: {row['bairro']}"
        ).add_to(m)
    st_folium(m, width=None, height=500)
else:
    st.info("Nenhuma planta encontrada com os filtros selecionados.")

# 6. Série temporal
st.markdown("### 📈 Série temporal de coletas")
if "data_visita" in df_dados_filtrado.columns and not df_dados_filtrado.empty:
    df_serie = df_dados_filtrado.dropna(subset=["data_visita"]).copy()
    if not df_serie.empty:
        df_serie["mes"] = df_serie["data_visita"].dt.to_period("M").astype(str)
        contagem = df_serie.groupby("mes").agg(visitas=("data_visita", "count"), amostras=("id_amostra_calc", "count")).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=contagem["mes"], y=contagem["visitas"], name="Visitas", marker_color="#2E86AB"))
        fig.add_trace(go.Bar(x=contagem["mes"], y=contagem["amostras"], name="Amostras", marker_color="#E63946"))
        fig.update_layout(barmode="group", height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem visitas no período.")

# 7. Gráficos
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("#### 🌱 Plantas por gênero")
    if not df_plantas_filtrado.empty:
        cont = df_plantas_filtrado["genero"].value_counts().reset_index()
        cont.columns = ["genero", "quantidade"]
        st.plotly_chart(px.pie(cont, names="genero", values="quantidade", hole=0.4), use_container_width=True)

with col_b:
    st.markdown("#### 🏘️ Plantas por bairro")
    if not df_plantas_filtrado.empty:
        cont = df_plantas_filtrado["bairro"].value_counts().reset_index()
        cont.columns = ["bairro", "quantidade"]
        st.plotly_chart(px.bar(cont, x="quantidade", y="bairro", orientation="h", color="quantidade"), use_container_width=True)

# 8. Tabela
st.markdown("### 📋 Tabela consolidada")
colunas_uteis = ["id_bromelia_calc", "bairro", "genero", "data_visita", "presenca_imaturos", "id_amostra_calc", "especie_identificada", "resultado_amostra"]
colunas_existentes = [c for c in colunas_uteis if c in df_dados_filtrado.columns]
if not df_dados_filtrado.empty and colunas_existentes:
    st.dataframe(df_dados_filtrado[colunas_existentes], use_container_width=True, height=400)
else:
    st.info("Nenhum dado para exibir na tabela.")