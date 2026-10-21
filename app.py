import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from kobo_api import _get_secret, baixar_formulario, preparar_dados_completos
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption(f"Pesquisador: Flávio Santos (IOC - Fiocruz) | Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")

# --- CARREGAMENTO VIA API ---
base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados direto do Kobo..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)
    df_plantas, df_dados = preparar_dados_completos(lista_campo, lista_lab)

if df_plantas.empty:
    st.warning("Nenhum dado encontrado no Kobo.")
    st.stop()

# --- CRUZAMENTO FINAL ---
df_final = pd.merge(df_plantas, df_dados, on="id_bromelia", how="left")

# Limpa a lista de espécies e calcula a positividade
def check_aedes(especies_list):
    if not isinstance(especies_list, list): return False
    return any("aedes" in str(e).lower() for e in especies_list)

df_final["positivo"] = df_final["especie"].apply(check_aedes)
df_final["especie_str"] = df_final["especie"].apply(lambda x: ', '.join(x) if isinstance(x, list) and x else "Não informado")
df_final["especie_str"] = df_final["especie_str"].str.replace("_", " ").str.capitalize()

# --- MÉTRICAS ---
n_plantas = df_final["id_bromelia"].nunique()
total_especimes = df_final["qtd_larvas"].sum()
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
            folium.Marker(location=[row["lat"], row["lon"]], icon=folium.Icon(color="red", icon="info-sign"), popup=f"<b>{row['id_bromelia']}</b><br>POSITIVO ({row['especie_str']})").add_to(m)
        else:
            folium.Marker(location=[row["lat"], row["lon"]], icon=folium.Icon(color="blue", icon="info-sign"), popup=f"<b>{row['id_bromelia']}</b><br>Negativo ({row['especie_str']})").add_to(m)
    st_folium(m, width=None, height=500, key="mapa")
else:
    st.info("Sem coordenadas para o mapa.")

# --- GRÁFICO DE ESPÉCIES ---
st.markdown("---")
st.markdown("### 🦟 Frequência de Espécies")

# Explode a lista de espécies para o gráfico
especies_expandidas = df_final.explode("especie")
if not especies_expandidas.empty:
    df_chart = especies_expandidas.groupby("especie").agg({"qtd_larvas": "sum"}).reset_index()
    df_chart["especie"] = df_chart["especie"].str.replace("_", " ").str.capitalize()
    
    if df_chart["qtd_larvas"].sum() > 0:
        fig = px.bar(df_chart, x="especie", y="qtd_larvas", text="qtd_larvas", color="especie")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Larvas")
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("#### 📋 Totais")
        st.dataframe(df_chart.rename(columns={"especie": "Espécie", "qtd_larvas": "Larvas"}), hide_index=True)
    else:
        st.info("Nenhuma larva registrada.")

st.markdown("---")
st.caption("Dashboard desenvolvido por Flávio Santos | PPG-VCV / IOC - Fiocruz | Contato: fhsantos@gmail.com")
