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

# --- CABEÇALHO ---
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.markdown("**Pesquisador:** Flávio Santos (Mestrado Profissional - IOC - Fiocruz) | **Contato:** fhsantos@gmail.com")
st.caption(f"Última atualização dos dados: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
st.markdown("---")

# --- FUNÇÕES ---
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

def preparar_dados(lista_campo, lista_lab):
    # 1. Processa o CAMPO
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
                
                amostras = v.get("rep_visitas/rep_amostras", [])
                if isinstance(amostras, list) and len(amostras) > 0:
                    for a in amostras:
                        id_amostra = a.get("rep_visitas/rep_amostras/id_amostra_calc") or a.get("id_amostra_calc")
                        id_amostra = str(id_amostra).strip() if id_amostra else None
                        dados_tabela.append({
                            "id_bromelia_calc": id_planta, "bairro": bairro, "genero": genero,
                            "data_visita": data_visita, "presenca_imaturos": presenca,
                            "id_amostra_calc": id_amostra,
                            "volume_agua_ml": vol_agua, "temp_agua_c": temp_agua, "ph_agua": ph_agua,
                            "observacoes_visita": obs_visita
                        })
                else:
                    dados_tabela.append({
                        "id_bromelia_calc": id_planta, "bairro": bairro, "genero": genero,
                        "data_visita": data_visita, "presenca_imaturos": presenca,
                        "id_amostra_calc": None,
                        "volume_agua_ml": vol_agua, "temp_agua_c": temp_agua, "ph_agua": ph_agua,
                        "observacoes_visita": obs_visita
                    })

    # 2. Processa o LABORATÓRIO
    lab_especies = []
    for item in lista_lab:
        id_amostra = item.get("grp_amostra/id_amostra_lab")
        id_amostra = str(id_amostra).strip() if id_amostra else None
        if not id_amostra: continue
        
        # Extrai o código da planta do ID da amostra (tudo antes do último hífen)
        # Ex: "BRO-2610172134-32" vira "BRO-2610172134"
        id_planta_do_lab = id_amostra.rsplit('-', 1)[0] if '-' in id_amostra else id_amostra
            
        resultado_digitado = item.get("grp_resultado/resultado_amostra") or "nao_processado"
        obs_lab = item.get("grp_resultado/observacoes_lab")
        
        especies = item.get("rep_especies", [])
        if isinstance(especies, list):
            for e in especies:
                especie_bruta = e.get("rep_especies/especie_identificada") or "nao_identificado"
                especie_formatada = str(especie_bruta).lower().strip().replace(" ", "_")
                
                soma = e.get("rep_especies/soma_contagem")
                try: soma = int(float(soma)) if soma else 0
                except: soma = 0

                resultado_real = "Positivo (Aedes)" if "aedes" in especie_formatada else "Negativo (Outros)"

                lab_especies.append({
                    "id_planta_lab": id_planta_do_lab, # Chave para cruzar com a planta
                    "id_amostra_calc": id_amostra,     # Mantém o ID original para referência
                    "especie_identificada": especie_formatada,
                    "soma_contagem": soma, 
                    "resultado_digitado": resultado_digitado,
                    "resultado_real": resultado_real, 
                    "observacoes_lab": obs_lab
                })
    
    df_plantas = pd.DataFrame(plantas)
    df_dados = pd.DataFrame(dados_tabela) if dados_tabela else pd.DataFrame(columns=["id_bromelia_calc", "bairro", "genero", "data_visita", "presenca_imaturos", "id_amostra_calc", "volume_agua_ml", "temp_agua_c", "ph_agua", "observacoes_visita"])
    df_lab = pd.DataFrame(lab_especies) if lab_especies else pd.DataFrame(columns=["id_planta_lab", "id_amostra_calc", "especie_identificada", "soma_contagem", "resultado_digitado", "resultado_real", "observacoes_lab"])

    # 3. Cruzamento Inteligente (Pela Planta, não pela Amostra)
    if not df_dados.empty and not df_lab.empty:
        # Para não duplicar as linhas, agrupamos as espécies por planta
        df_lab_agrupado = df_lab.groupby("id_planta_lab").agg({
            "especie_identificada": lambda x: ', '.join(x.unique()),
            "soma_contagem": "sum",
            "resultado_digitado": "first",
            "resultado_real": "first",
            "observacoes_lab": "first"
        }).reset_index()
        
        df_final = pd.merge(df_dados, df_lab_agrupado, left_on="id_bromelia_calc", right_on="id_planta_lab", how="left")
    else:
        df_final = df_dados.copy()
        for col in ["especie_identificada", "soma_contagem", "resultado_digitado", "resultado_real", "observacoes_lab"]:
            df_final[col] = None

    return df_plantas, df_final

# --- CARREGAMENTO ---
base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)
    df_plantas, df_dados = preparar_dados(lista_campo, lista_lab)

if df_plantas.empty:
    st.warning("Nenhum dado encontrado.")
    st.stop()

# --- TRATAMENTO ---
df_dados["resultado_digitado"] = df_dados["resultado_digitado"].astype(str).str.lower().str.strip().replace(["nan", "none", ""], "nao_processado")
df_dados["soma_contagem"] = pd.to_numeric(df_dados["soma_contagem"], errors="coerce").fillna(0)

# --- MENU LATERAL ---
with st.sidebar:
    st.header("🔎 Filtros")
    bairros = sorted(df_plantas["bairro"].dropna().unique())
    bairro_sel = st.multiselect("Bairro", bairros, default=bairros)
    generos = sorted(df_plantas["genero"].dropna().unique())
    genero_sel = st.multiselect("Gênero", generos, default=generos)
    
    st.markdown("---")
    st.markdown("### 🗺️ Mapa")
    tipo_mapa = st.radio("Selecione:", ["Mapa Base e Raio (100m)", "🔥 Mapa de Calor"])

# Aplicando filtros
df_plantas_filtrado = df_plantas.copy()
df_dados_filtrado = df_dados.copy()

if bairro_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["bairro"].isin(bairro_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["bairro"].isin(bairro_sel)]
if genero_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["genero"].isin(genero_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["genero"].isin(genero_sel)]

df_dados_filtrado["especie_display"] = df_dados_filtrado["especie_identificada"].apply(
    lambda x: f"{str(x).replace('_', ' ').capitalize()}" if pd.notna(x) and str(x).lower() != "nan" else "Não informado"
)

n_plantas = df_plantas_filtrado["id_bromelia_calc"].nunique()
n_visitas = df_dados_filtrado["data_visita"].notna().sum()
n_amostras = df_dados_filtrado["id_amostra_calc"].nunique()

amostras_com_aedes = df_dados_filtrado[df_dados_filtrado["especie_identificada"].astype(str).str.lower().str.contains("aedes")]
amostras_positivas = amostras_com_aedes["id_bromelia_calc"].nunique() # Conta a planta, não a amostra
positividade = (amostras_positivas / n_plantas * 100) if n_plantas > 0 else 0
total_especimes = df_dados_filtrado["soma_contagem"].sum()

# --- KPIs ---
st.markdown("### 📊 Indicadores")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Plantas", n_plantas)
c2.metric("Visitas", n_visitas)
c3.metric("Amostras", n_amostras)
c4.metric("Espécimes (Lab)", int(total_especimes))

st.markdown("---")

# --- MAPAS ---
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

# --- ESPÉCIES ---
st.markdown("---")
st.markdown("### 🦟 Espécies")
df_esp = df_dados_filtrado.groupby("especie_display").agg(Total=("soma_contagem", "sum")).reset_index()
if not df_esp.empty and df_esp["Total"].sum() > 0:
    st.plotly_chart(px.bar(df_esp, x="especie_display", y="Total", color="especie_display", text="Total"), width='stretch')
    st.dataframe(df_esp.rename(columns={"especie_display": "Espécie", "Total": "Larvas"}), hide_index=True)
else:
    st.info("Nenhuma larva registrada.")

# --- NOTAS ---
st.markdown("---")
st.markdown("### 📝 Notas de Campo")
df_obs = df_dados_filtrado.dropna(subset=["observacoes_visita"])
df_obs = df_obs[df_obs["observacoes_visita"].astype(str).str.lower() != "nan"]
if not df_obs.empty:
    for _, r in df_obs.iterrows():
        st.info(f"**{r['id_bromelia_calc']}**: {r['observacoes_visita']}")
else:
    st.success("Sem notas de campo.")

# --- RODAPÉ ---
st.markdown("---")
st.caption("Dashboard desenvolvido por Flávio Santos | PPG-VCV / IOC - Fiocruz | Contato: fhsantos@gmail.com")