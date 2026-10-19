import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from kobo_api import _get_secret, baixar_formulario, preparar_dados_completos

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")

# Cabeçalho simples
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.write("**Pesquisador:** Flávio Santos (IOC - Fiocruz) | **Contato:** fhsantos@gmail.com")
st.divider()

# Carregar Dados
base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)
    df_plantas, df_dados = preparar_dados_completos(lista_campo, lista_lab)

if df_plantas.empty:
    st.error("Nenhum dado encontrado.")
    st.stop()

# --- CÁLCULOS BÁSICOS ---
# Força os números a serem números
df_dados["soma_contagem"] = pd.to_numeric(df_dados["soma_contagem"], errors="coerce").fillna(0)

n_plantas = df_plantas["id_bromelia_calc"].nunique()
n_visitas = df_dados["data_visita"].notna().sum()
n_amostras = df_dados["id_amostra_calc"].nunique()

amostras_com_aedes = df_dados[df_dados["especie_identificada"].astype(str).str.contains("aedes", case=False, na=False)]
amostras_positivas = amostras_com_aedes["id_amostra_calc"].nunique()
positividade = (amostras_positivas / n_amostras * 100) if n_amostras > 0 else 0
total_especimes = df_dados["soma_contagem"].sum()

# --- KPIs NO TOPO ---
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Plantas", n_plantas)
c2.metric("Visitas", n_visitas)
c3.metric("Amostras", n_amostras)
c4.metric("Positividade (Aedes)", f"{positividade:.1f}%")
c5.metric("Espécimes (Lab)", int(total_especimes))

st.divider()

# --- GRÁFICO DE ESPÉCIES ---
st.subheader("🦟 Frequência de Espécies")
df_especies = df_dados.groupby("especie_identificada").agg(Total=("soma_contagem", "sum")).reset_index()
df_especies["especie_identificada"] = df_especies["especie_identificada"].fillna("Não informado").astype(str).str.replace("_", " ").str.capitalize()
df_especies = df_especies[df_especies["Total"] > 0]

if not df_especies.empty:
    fig_esp = px.bar(df_especies, x="especie_identificada", y="Total", text="Total", color="especie_identificada")
    fig_esp.update_layout(showlegend=False, xaxis_title="", yaxis_title="Quantidade de Larvas")
    st.plotly_chart(fig_esp, use_container_width=True)
else:
    st.info("Nenhuma larva registrada no laboratório.")

st.divider()

# --- MICROCLIMA ---
st.subheader("💧 Resumo do Microclima e Ambiente")
df_dados["ph_agua"] = pd.to_numeric(df_dados["ph_agua"], errors="coerce")
df_dados["temp_agua_c"] = pd.to_numeric(df_dados["temp_agua_c"], errors="coerce")
df_dados["volume_agua_ml"] = pd.to_numeric(df_dados["volume_agua_ml"], errors="coerce")

m1, m2, m3 = st.columns(3)
m1.metric("pH Médio", f"{df_dados['ph_agua'].mean():.2f}" if not df_dados['ph_agua'].isna().all() else "—")
m2.metric("Temperatura Média", f"{df_dados['temp_agua_c'].mean():.1f} °C" if not df_dados['temp_agua_c'].isna().all() else "—")
m3.metric("Volume Médio", f"{df_dados['volume_agua_ml'].mean():.0f} mL" if not df_dados['volume_agua_ml'].isna().all() else "—")

st.divider()

# --- MAPAS (Básico) ---
st.subheader("🗺️ Mapa de Risco (Básico)")
df_mapa = df_plantas.dropna(subset=["latitude", "longitude"])
if not df_mapa.empty:
    m = folium.Map(location=[-22.9661, -42.0272], zoom_start=14, tiles="OpenStreetMap")
    for _, row in df_mapa.iterrows():
        cor = "red" if row["id_bromelia_calc"] in amostras_com_aedes["id_bromelia_calc"].values else "blue"
        folium.Marker(
            location=[row["latitude"], row["longitude"]], 
            icon=folium.Icon(color=cor, icon="info-sign"), 
            popup=f"<b>{row['id_bromelia_calc']}</b>"
        ).add_to(m)
    st_folium(m, width=None, height=400, key="mapa_simples")

# --- RODAPÉ ---
st.divider()
st.caption("Dashboard desenvolvido por Flávio Santos | PPG-VCV / IOC - Fiocruz | Contato: fhsantos@gmail.com")