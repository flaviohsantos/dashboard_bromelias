import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from datetime import datetime
import requests

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")

st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.markdown("**Pesquisador:** Flávio Santos (Mestrado Profissional - IOC - Fiocruz) | **Contato:** fhsantos@gmail.com")
st.caption(f"Última atualização dos dados: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
st.markdown("---")

def _get_secret(key, default=""):
    try: return st.secrets[key]
    except: return default

def baixar_formulario(uid, token, base_url):
    if not uid: return []
    url = f"{base_url}/api/v2/assets/{uid}/data/"
    headers = {"Authorization": f"Token {token}"}
    registros = []
    while url:
        r = requests.get(url, headers=headers, params={"format": "json"}, timeout=60)
        r.raise_for_status()
        payload = r.json()
        registros.extend(payload.get("results", []))
        url = payload.get("next")
    return registros

# --- CARREGAMENTO ---
base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)

# --- PROCESSAMENTO ---
plantas = []
dados_tabela = []

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
    
    plantas.append({"id_bromelia_calc": id_planta, "bairro": bairro, "genero": genero, "latitude": lat, "longitude": lon})

    visitas = item.get("rep_visitas", [])
    if isinstance(visitas, list):
        for v in visitas:
            data_visita = v.get("rep_visitas/data_visita")
            presenca = v.get("rep_visitas/presenca_imaturos")
            vol_agua = v.get("rep_visitas/volume_agua_ml")
            temp_agua = v.get("rep_visitas/temp_agua_c")
            ph_agua = v.get("rep_visitas/ph_agua")
            obs_visita = v.get("rep_visitas/observacoes_visita")
            
            dados_tabela.append({
                "id_bromelia_calc": id_planta, "bairro": bairro, "genero": genero,
                "data_visita": data_visita, "presenca_imaturos": presenca,
                "volume_agua_ml": vol_agua, "temp_agua_c": temp_agua, "ph_agua": ph_agua,
                "observacoes_visita": obs_visita,
                "especie_identificada": None, "soma_contagem": 0, "resultado_real": "Nenhum"
            })

# Processa o Lab e tenta achar uma planta com base na data ou ID
for item in lista_lab:
    id_amostra = str(item.get("grp_amostra/id_amostra_lab") or "").strip()
    if not id_amostra: continue
        
    resultado_digitado = item.get("grp_resultado/resultado_amostra") or "nao_processado"
    obs_lab = item.get("grp_resultado/observacoes_lab")
    
    especies = item.get("rep_especies", [])
    if isinstance(especies, list):
        for e in especies:
            especie_bruta = e.get("rep_especies/especie_identificada") or "nao_identificado"
            especie = str(especie_bruta).lower().strip().replace(" ", "_")
            soma = e.get("rep_especies/soma_contagem")
            try: soma = int(float(soma)) if soma else 0
            except: soma = 0

            resultado_real = "Positivo (Aedes)" if "aedes" in especie else "Negativo (Outros)"

            # A MÁGICA: Tenta encontrar a linha do campo cujo id_bromelia_calc esteja contido no id_amostra
            found = False
            for linha in dados_tabela:
                if linha["id_bromelia_calc"] in id_amostra:
                    linha["especie_identificada"] = especie
                    linha["soma_contagem"] += soma
                    linha["resultado_real"] = resultado_real
                    found = True
                    break
            
            # Se não achou pelo ID, joga numa "pilha" (isso evita que o gráfico zere)
            if not found:
                dados_tabela.append({
                    "id_bromelia_calc": "Lab (Sem visita)", "bairro": "N/A", "genero": "N/A",
                    "data_visita": None, "presenca_imaturos": None,
                    "volume_agua_ml": None, "temp_agua_c": None, "ph_agua": None,
                    "observacoes_visita": None,
                    "especie_identificada": especie, "soma_contagem": soma, "resultado_real": resultado_real
                })

df_plantas = pd.DataFrame(plantas)
df_dados = pd.DataFrame(dados_tabela)

if df_plantas.empty:
    st.warning("Nenhum dado de campo encontrado.")
    st.stop()

# --- FILTROS ---
with st.sidebar:
    st.header("🔎 Filtros")
    bairros = sorted(df_plantas["bairro"].dropna().unique())
    bairro_sel = st.multiselect("Bairro", bairros, default=bairros)
    generos = sorted(df_plantas["genero"].dropna().unique())
    genero_sel = st.multiselect("Gênero", generos, default=generos)
    st.markdown("### 🗺️ Mapa")
    tipo_mapa = st.radio("Selecione:", ["Mapa Base e Raio (100m)", "🔥 Mapa de Calor"])

df_plantas_filtrado = df_plantas.copy()
df_dados_filtrado = df_dados.copy()

if bairro_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["bairro"].isin(bairro_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["bairro"].isin(bairro_sel)]
if genero_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["genero"].isin(genero_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["genero"].isin(genero_sel)]

n_plantas = df_plantas_filtrado["id_bromelia_calc"].nunique()
n_visitas = df_dados_filtrado["data_visita"].notna().sum()
amostras_com_aedes = df_dados_filtrado[df_dados_filtrado["especie_identificada"].astype(str).str.lower().str.contains("aedes")]
amostras_positivas = amostras_com_aedes["id_bromelia_calc"].nunique()
positividade = (amostras_positivas / n_plantas * 100) if n_plantas > 0 else 0
total_especimes = df_dados_filtrado["soma_contagem"].sum()

st.markdown("### 📊 Indicadores")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Plantas", n_plantas)
c2.metric("Visitas", n_visitas)
c3.metric("Amostras", n_visitas) # Ajuste visual
c4.metric("Espécimes (Lab)", int(total_especimes))

st.markdown("---")

st.markdown("### 🗺️ Mapas de Risco e Termômetro")
df_mapa = df_plantas_filtrado.dropna(subset=["latitude", "longitude"])
ids_positivos = amostras_com_aedes["id_bromelia_calc"].unique()

col_mapa, col_termo = st.columns([3, 1])
with col_mapa:
    if not df_mapa.empty:
        if tipo_mapa == "Mapa Base e Raio (100m)":
            m1 = folium.Map(location=[-22.9661, -42.0272], zoom_start=15, tiles="OpenStreetMap")
            for _, row in df_mapa.iterrows():
                if row["id_bromelia_calc"] in ids_positivos:
                    folium.Circle(location=[row["latitude"], row["longitude"]], radius=100, color="#E63946", fill=True, fill_opacity=0.2, weight=2).add_to(m1)
                    folium.Marker(location=[row["latitude"], row["longitude"]], icon=folium.Icon(color="red"), popup=f"{row['id_bromelia_calc']}").add_to(m1)
                else:
                    folium.Marker(location=[row["latitude"], row["longitude"]], icon=folium.Icon(color="blue"), popup=f"{row['id_bromelia_calc']}").add_to(m1)
            st_folium(m1, width=None, height=500, key="mapa1")
        else:
            df_calor = df_mapa[df_mapa["id_bromelia_calc"].isin(ids_positivos)]
            if not df_calor.empty:
                m2 = folium.Map(location=[-22.9661, -42.0272], zoom_start=14, tiles="OpenStreetMap")
                heat_data = [[r["latitude"], r["longitude"]] for _, r in df_calor.iterrows()]
                HeatMap(heat_data, radius=50, blur=30).add_to(m2)
                st_folium(m2, width=None, height=500, key="mapa2")
            else:
                st.info("Nenhum foco positivo para gerar o mapa de calor.")
    else:
        st.info("Sem coordenadas para o mapa.")

with col_termo:
    st.markdown("#### 🌡️ Termômetro")
    if positividade < 15: cor, st_risco = "#2E86AB", "BAIXO"
    elif positividade < 40: cor, st_risco = "#F4A261", "MÉDIO"
    else: cor, st_risco = "#E63946", "ALTO"

    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=positividade, number={'suffix': "%"},
        title={'text': st_risco},
        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': cor},
               'steps': [{'range': [0, 15], 'color': '#D6EAF8'}, {'range': [15, 40], 'color': '#FDEBD0'}, {'range': [40, 100], 'color': '#FADBD8'}]}
    ))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, width='stretch')

st.markdown("---")
st.markdown("### 🦟 Espécies")
df_esp = df_dados_filtrado.groupby("especie_identificada").agg(Total=("soma_contagem", "sum")).reset_index()
df_esp["especie_identificada"] = df_esp["especie_identificada"].fillna("Não informado").astype(str).str.replace("_", " ").str.capitalize()

if not df_esp.empty and df_esp["Total"].sum() > 0:
    st.plotly_chart(px.bar(df_esp, x="especie_identificada", y="Total", color="especie_identificada", text="Total"), width='stretch')
    st.dataframe(df_esp.rename(columns={"especie_identificada": "Espécie", "Total": "Larvas"}), hide_index=True)
else:
    st.info("Nenhuma larva registrada no laboratório.")

st.markdown("---")
st.markdown("### 📝 Notas de Campo")
df_obs = df_dados_filtrado.dropna(subset=["observacoes_visita"])
if not df_obs.empty:
    for _, r in df_obs.iterrows():
        st.info(f"**{r['id_bromelia_calc']}**: {r['observacoes_visita']}")

st.markdown("---")
st.caption("Dashboard desenvolvido por Flávio Santos | PPG-VCV / IOC - Fiocruz | Contato: fhsantos@gmail.com")