import os
import unicodedata
from datetime import datetime

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption(f"Pesquisador: Flávio Santos (IOC - Fiocruz) | Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")

# --- FUNÇÕES AUXILIARES ---
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

def normalizar_texto(valor):
    if valor is None: return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().replace("_", " ").strip().split())

def normalizar_codigo(valor):
    if valor is None: return None
    if isinstance(valor, float) and valor.is_integer(): valor = int(valor)
    return str(valor).strip() or None

def numero_inteiro(valor):
    if valor is None or str(valor).strip() == "": return 0
    try: return max(0, int(float(str(valor).strip().replace(",", "."))))
    except: return 0

# --- CARREGAMENTO ---
base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados do Kobo..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)

if not lista_campo:
    st.warning("Nenhum dado encontrado.")
    st.stop()

# --- PROCESSAMENTO ---
plantas = []
visitas_list = []
amostras = []

for indice, item in enumerate(lista_campo):
    id_planta = item.get("grp_cadastro/id_bromelia_calc") or f"SEM-ID-{indice}"
    bairro = item.get("grp_cadastro/bairro") or "N/I"
    genero = item.get("grp_cadastro/genero") or "N/I"
    
    geo = item.get("grp_cadastro/geolocalizacao", "")
    lat, lon = None, None
    if isinstance(geo, str) and " " in geo:
        try:
            p = geo.split()
            lat, lon = float(p[0]), float(p[1])
        except: pass
        
    plantas.append({"id_bromelia": id_planta, "bairro": bairro, "genero": genero, "lat": lat, "lon": lon})

    visitas = item.get("rep_visitas", [])
    if isinstance(visitas, list):
        for v in visitas:
            data_v = v.get("rep_visitas/data_visita")
            ph = v.get("rep_visitas/ph_agua")
            temp = v.get("rep_visitas/temp_agua_c")
            vol = v.get("rep_visitas/volume_agua_ml")
            obs = v.get("rep_visitas/observacoes_visita")
            
            visitas_list.append({
                "id_bromelia": id_planta, "data_visita": data_v,
                "ph": ph, "temp": temp, "vol": vol, "obs": obs
            })

            ams = v.get("rep_visitas/rep_amostras", [])
            if isinstance(ams, list):
                for a in ams:
                    cod = a.get("rep_visitas/rep_amostras/codigo_amostra")
                    if cod:
                        amostras.append({"id_bromelia": id_planta, "codigo_amostra": str(cod).strip()})

lab_especies = []
for item in lista_lab:
    cod_lab = item.get("grp_amostra/codigo_amostra")
    if not cod_lab: continue
    
    for e in item.get("rep_especies", []):
        especie = e.get("rep_especies/especie_identificada") or "nao_identificado"
        qtd_l = numero_inteiro(e.get("rep_especies/qtd_larvas"))
        qtd_p = numero_inteiro(e.get("rep_especies/qtd_pupas"))
        
        lab_especies.append({
            "codigo_amostra": str(cod_lab).strip(),
            "especie": normalizar_texto(especie).replace(" ", "_"),
            "qtd_especimes": qtd_l + qtd_p
        })

df_plantas = pd.DataFrame(plantas).drop_duplicates(subset=["id_bromelia"])
df_visitas = pd.DataFrame(visitas_list)
df_amostras = pd.DataFrame(amostras).drop_duplicates(subset=["codigo_amostra"])
df_lab = pd.DataFrame(lab_especies)

if not df_amostras.empty and not df_lab.empty:
    df_merge = pd.merge(df_amostras, df_lab, on="codigo_amostra", how="left")
    df_por_planta = df_merge.groupby("id_bromelia").agg({
        "especie": lambda x: list(x.dropna().unique()),
        "qtd_especimes": "sum"
    }).reset_index()
    df_final = pd.merge(df_plantas, df_por_planta, on="id_bromelia", how="left")
else:
    df_final = df_plantas.copy()
    df_final["especie"] = [[] for _ in range(len(df_final))]
    df_final["qtd_especimes"] = 0

df_final["positivo"] = df_final["especie"].apply(lambda x: any("aedes" in str(e) for e in x) if isinstance(x, list) else False)
df_final["especie_str"] = df_final["especie"].apply(lambda x: ', '.join(x) if isinstance(x, list) and x else "Não informado").str.replace("_", " ").str.capitalize()
df_final["qtd_especimes"] = pd.to_numeric(df_final["qtd_especimes"], errors="coerce").fillna(0)

# ==========================================
# LAYOUT
# ==========================================

# 1. INDICADORES
n_plantas = df_final["id_bromelia"].nunique()
total_especimes = df_final["qtd_especimes"].sum()
plantas_positivas = df_final[df_final["positivo"]]["id_bromelia"].nunique()
positividade = (plantas_positivas / n_plantas * 100) if n_plantas > 0 else 0

st.markdown("### 📊 Indicadores")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Plantas", n_plantas)
c2.metric("Espécimes (Lab)", int(total_especimes))
c3.metric("Plantas Positivas", plantas_positivas)
c4.metric("Positividade", f"{positividade:.1f}%")

st.markdown("---")

# 2. MÉDIAS DA ÁGUA (NOVO LOCAL: LOGO ABAIXO DOS INDICADORES)
st.markdown("### 💧 Médias da Água")
if not df_visitas.empty:
    df_visitas["ph"] = pd.to_numeric(df_visitas["ph"], errors="coerce")
    df_visitas["temp"] = pd.to_numeric(df_visitas["temp"], errors="coerce")
    df_visitas["vol"] = pd.to_numeric(df_visitas["vol"], errors="coerce")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("pH Médio", f"{df_visitas['ph'].mean():.1f}" if not df_visitas['ph'].isna().all() else "—")
    m2.metric("Temperatura Média", f"{df_visitas['temp'].mean():.1f} °C" if not df_visitas['temp'].isna().all() else "—")
    m3.metric("Volume Médio", f"{df_visitas['vol'].mean():.0f} mL" if not df_visitas['vol'].isna().all() else "—")
else:
    st.info("Sem dados de água.")

st.markdown("---")

# 3. MAPAS E TERMÔMETRO
st.markdown("### 🗺️ Mapas de Risco e Termômetro")
df_mapa = df_final.dropna(subset=["lat", "lon"])

if not df_mapa.empty:
    centro_lat = df_mapa["lat"].mean()
    centro_lon = df_mapa["lon"].mean()
    
    tab1, tab2 = st.tabs(["📍 Mapa Base e Raio (100m)", "🔥 Mapa de Calor (Apenas Focos)"])
    
    with tab1:
        col_mapa, col_termo = st.columns([3, 1])
        
        with col_mapa:
            m1 = folium.Map(location=[centro_lat, centro_lon], zoom_start=16, tiles="OpenStreetMap")
            for _, row in df_mapa.iterrows():
                if row["positivo"]:
                    folium.Circle(location=[row["lat"], row["lon"]], radius=100, color="#E63946", fill=True, fill_opacity=0.2, weight=2).add_to(m1)
                    folium.Marker(location=[row["lat"], row["lon"]], icon=folium.Icon(color="red", icon="info-sign"), popup=f"<b>{row['id_bromelia']}</b><br>POSITIVO").add_to(m1)
                else:
                    folium.Marker(location=[row["lat"], row["lon"]], icon=folium.Icon(color="blue", icon="info-sign"), popup=f"<b>{row['id_bromelia']}</b><br>Negativo").add_to(m1)
            st_folium(m1, width=None, height=450, key="mapa1")
            
        with col_termo:
            st.markdown("#### 🌡️ Termômetro")
            if positividade < 15: cor, st_risco = "#2E86AB", "BAIXO"
            elif positividade < 40: cor, st_risco = "#F4A261", "MÉDIO"
            else: cor, st_risco = "#E63946", "ALTO"
            
            fig_termo = go.Figure(go.Indicator(
                mode="gauge+number", value=positividade, number={'suffix': "%"},
                title={'text': st_risco},
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': cor},
                       'steps': [{'range': [0, 15], 'color': '#D6EAF8'}, {'range': [15, 40], 'color': '#FDEBD0'}, {'range': [40, 100], 'color': '#FADBD8'}]}
            ))
            fig_termo.update_layout(height=350, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_termo, use_container_width=True)
            
        # --- ABA 2: MAPA DE CALOR ---
    with tab2:
        st.markdown("#### 🔥 Mapa de Calor (Focos Positivos)")
        
        # Filtra apenas as plantas positivas
        df_calor = df_mapa[df_mapa["positivo"]]
        
        if not df_calor.empty:
            # Usa o Plotly para desenhar o mapa de calor (não trava a rolagem)
            fig_mapa_calor = px.density_mapbox(
                df_calor, 
                lat="lat", 
                lon="lon", 
                z="qtd_especimes", # Intensidade do calor baseada na qtd de larvas
                radius=40,
                center=dict(lat=centro_lat, lon=centro_lon),
                zoom=15,
                mapbox_style="open-street-map", # Fundo claro e gratuito
                color_continuous_scale="Inferno" # Escala de cores do fogo
            )
            fig_mapa_calor.update_layout(
                margin=dict(l=0, r=0, t=0, b=0), 
                height=450,
                coloraxis_showscale=False # Esconde a barra de cores lateral
            )
            st.plotly_chart(fig_mapa_calor, use_container_width=True)
        else:
            st.info("✅ Nenhuma planta positiva para gerar o mapa de calor no momento.")
else:
    st.info("Sem coordenadas para o mapa.")

# 4. SÉRIE TEMPORAL
st.markdown("---")
st.markdown("### 📈 Série Temporal de Coletas")
if not df_visitas.empty and "data_visita" in df_visitas.columns:
    df_serie = df_visitas.copy()
    df_serie["data_visita"] = pd.to_datetime(df_serie["data_visita"], errors="coerce")
    df_serie["mes"] = df_serie["data_visita"].dt.to_period("M").astype(str)
    contagem = df_serie.groupby("mes").agg(
        visitas=("data_visita", "count"),
        amostras=("id_bromelia", "count")
    ).reset_index()
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=contagem["mes"], y=contagem["visitas"], name="Visitas", marker_color="#2E86AB"))
    fig.update_layout(barmode="group", height=350, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sem dados de visitas.")

# 5. ESPÉCIES E ANÁLISE DE ÁGUA
st.markdown("---")
col_esp, col_agua = st.columns([2, 1])

with col_esp:
    st.markdown("### 🦟 Frequência de Espécies")
    if not df_lab.empty:
        df_chart = df_lab.groupby("especie").agg({"qtd_especimes": "sum"}).reset_index()
        df_chart["especie"] = df_chart["especie"].str.replace("_", " ").str.capitalize()
        
        fig = px.bar(df_chart, x="especie", y="qtd_especimes", text="qtd_especimes", color="especie")
        fig.update_layout(showlegend=False, height=400, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhuma larva registrada.")

with col_agua:
    st.markdown("### 🧪 pH vs Presença de Larvas")
    if not df_visitas.empty and not df_visitas['ph'].isna().all():
        fig_ph = px.box(df_visitas, y="ph", points="all", color_discrete_sequence=["#E63946"])
        fig_ph.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10), xaxis_title="")
        st.plotly_chart(fig_ph, use_container_width=True)

# 6. NOTAS
st.markdown("---")
st.markdown("### 📝 Notas e Intercorrências de Campo")
if not df_visitas.empty:
    df_obs = df_visitas.dropna(subset=["obs"])
    df_obs = df_obs[df_obs["obs"].astype(str).str.lower() != "nan"]
    
    if not df_obs.empty:
        for _, r in df_obs.iterrows():
            data_str = pd.to_datetime(r["data_visita"]).strftime('%d/%m/%Y') if pd.notna(r["data_visita"]) else "Data N/I"
            st.info(f"**{data_str}** | Planta **{r['id_bromelia']}**: *\"{r['obs']}\"*")
    else:
        st.success("Nenhuma nota registrada.")
else:
    st.success("Nenhuma nota registrada.")

st.markdown("---")
st.caption("Dashboard desenvolvido por Flávio Santos | PPG-VCV / IOC - Fiocruz | Contato: fhsantos@gmail.com")
