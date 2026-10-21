import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime
import requests
import os

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption(f"Pesquisador: Flávio Santos (IOC - Fiocruz) | Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")

def _get_secret(key, default=""):
    try: return st.secrets[key]
    except: return os.environ.get(key, default)

def baixar_formulario(uid, token, base_url):
    if not uid: return []
    url = f"{base_url}/api/v2/assets/{uid}/data/"
    headers = {"Authorization": f"Token {token}"}
    params = {"format": "json"}
    registros = []
    while url:
        r = requests.get(url, headers=headers, params=params, timeout=60)
        r.raise_for_status()
        payload = r.json()
        registros.extend(payload.get("results", []))
        url = payload.get("next")
        params = {}
    return registros

base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)

if not lista_campo:
    st.warning("Nenhum dado de campo encontrado.")
    st.stop()

# --- PROCESSAMENTO ---
plantas = []
amostras = []

# 1. Plantas e Amostras do Campo
for item in lista_campo:
    id_planta = item.get("grp_cadastro/id_bromelia_calc") or "Sem ID"
    bairro = item.get("grp_cadastro/bairro") or "Não informado"
    genero = item.get("grp_cadastro/genero") or "Não informado"
    
    geo = item.get("grp_cadastro/geolocalizacao")
    lat, lon = None, None
    if isinstance(geo, str) and " " in geo:
        try:
            partes = geo.split()
            lat, lon = float(partes[0]), float(partes[1])
        except: pass
        
    plantas.append({"id_bromelia": id_planta, "bairro": bairro, "genero": genero, "lat": lat, "lon": lon})

    visitas = item.get("rep_visitas", [])
    if isinstance(visitas, list):
        for v in visitas:
            ams = v.get("rep_visitas/rep_amostras", [])
            if isinstance(ams, list):
                for a in ams:
                    cod = a.get("rep_visitas/rep_amostras/codigo_amostra")
                    if cod:
                        amostras.append({"id_bromelia": id_planta, "codigo_amostra": str(cod).strip()})

# 2. Laboratório (Espécies)
lab_especies = []
for item in lista_lab:
    cod_lab = item.get("grp_amostra/codigo_amostra")
    if not cod_lab: continue
    
    especies = item.get("rep_especies", [])
    if isinstance(especies, list):
        for e in especies:
            especie = e.get("rep_especies/especie_identificada") or "nao_identificado"
            qtd = e.get("rep_especies/qtd_larvas") or 0
            
            lab_especies.append({
                "codigo_amostra": str(cod_lab).strip(),
                "especie": str(especie).lower().strip().replace(" ", "_"),
                "qtd_larvas": int(float(qtd)) if qtd else 0
            })

df_plantas = pd.DataFrame(plantas)
df_amostras = pd.DataFrame(amostras)
df_lab = pd.DataFrame(lab_especies)

# --- CRUZAMENTO ---
if not df_amostras.empty and not df_lab.empty:
    df_merge = pd.merge(df_amostras, df_lab, on="codigo_amostra", how="left")
    
    df_por_planta = df_merge.groupby("id_bromelia").agg({
        "especie": lambda x: list(x.dropna().unique()),
        "qtd_larvas": "sum"
    }).reset_index()
    
    df_final = pd.merge(df_plantas, df_por_planta, on="id_bromelia", how="left")
else:
    df_final = df_plantas.copy()
    df_final["especie"] = None
    df_final["qtd_larvas"] = 0

# --- TRATAMENTO FINAL ---
def check_aedes(especies_list):
    if not isinstance(especies_list, list): return False
    return any("aedes" in str(e).lower() for e in especies_list)

df_final["positivo"] = df_final["especie"].apply(check_aedes)
df_final["especie_str"] = df_final["especie"].apply(lambda x: ', '.join(x) if isinstance(x, list) and x else "Não informado")
df_final["especie_str"] = df_final["especie_str"].str.replace("_", " ").str.capitalize()
df_final["qtd_larvas"] = pd.to_numeric(df_final["qtd_larvas"], errors="coerce").fillna(0)

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

# --- GRÁFICO ---
st.markdown("---")
st.markdown("### 🦟 Frequência de Espécies")

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
