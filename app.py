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
from folium.plugins import HeatMap
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")
# Atualiza a página a cada 5 minutos (300.000 milissegundos)
st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")
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
    tipologia = item.get("grp_cadastro/tipologia_imovel") or "N/I"
    
    geo = item.get("grp_cadastro/geolocalizacao", "")
    lat, lon = None, None
    if isinstance(geo, str) and " " in geo:
        try:
            p = geo.split()
            lat, lon = float(p[0]), float(p[1])
        except: pass
        
    plantas.append({
        "id_bromelia": id_planta, "bairro": bairro, "genero": genero, 
        "tipologia": tipologia, "lat": lat, "lon": lon
    })

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

# --- PROCESSAMENTO DO LABORATÓRIO (O PULO DO GATO) ---
lab_especies = []
for item in lista_lab:
    cod_lab = item.get("grp_amostra/codigo_amostra")
    if not cod_lab: continue
    
    # AQUI está a mágica: ele itera sobre a lista de espécies que o Kobo envia
    especies_amostra = item.get("rep_especies", [])
    if isinstance(especies_amostra, list):
        for e in especies_amostra:
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
# LAYOUT DO DASHBOARD
# ==========================================

# 1. PAINEL EXECUTIVO
st.markdown("### 📊 Painel Executivo")
n_plantas = df_final["id_bromelia"].nunique()
total_especimes = df_final["qtd_especimes"].sum()
plantas_positivas = df_final[df_final["positivo"]]["id_bromelia"].nunique()
positividade = (plantas_positivas / n_plantas * 100) if n_plantas > 0 else 0

bairro_alerta = "Nenhum"
if not df_final.empty:
    df_risco = df_final.groupby("bairro").agg(total=("id_bromelia", "count"), positivas=("positivo", "sum")).reset_index()
    df_risco["% risco"] = (df_risco["positivas"] / df_risco["total"] * 100)
    if not df_risco.empty and df_risco["% risco"].max() > 0:
        top = df_risco.sort_values(by="% risco", ascending=False).iloc[0]
        bairro_alerta = f"{top['bairro'].capitalize()} ({top['% risco']:.0f}%)"

col_kpis, col_alerta = st.columns([2, 1])
with col_kpis:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Plantas", n_plantas)
    c2.metric("Espécimes (Lab)", int(total_especimes))
    c3.metric("Plantas Positivas", plantas_positivas)
    c4.metric("Positividade Geral", f"{positividade:.1f}%")

with col_alerta:
    if positividade < 15: bg, txt, icone, msg = "#D6EAF8", "#2E86AB", "✅", "Risco Baixo."
    elif positividade < 40: bg, txt, icone, msg = "#FDEBD0", "#F4A261", "⚠️", f"Risco Médio. Atenção ao bairro {bairro_alerta}."
    else: bg, txt, icone, msg = "#FADBD8", "#E63946", "🚨", f"Risco Alto. Ação urgente no bairro {bairro_alerta}."
    st.markdown(f"""<div style="background-color: {bg}; padding: 15px; border-radius: 10px; border-left: 5px solid {txt}; height: 100%;">
        <h4 style="color: {txt}; margin-top: 0;">{icone} Status: {'ALTO' if positividade >= 40 else 'MÉDIO' if positividade >= 15 else 'BAIXO'}</h4>
        <p style="color: #333; margin-bottom: 0; font-size: 14px;">{msg}</p></div>""", unsafe_allow_html=True)

st.markdown("---")

# 2. MÉDIAS DA ÁGUA
st.markdown("### 💧 Médias da Água")
if not df_visitas.empty:
    df_visitas["ph"] = pd.to_numeric(df_visitas["ph"], errors="coerce")
    df_visitas["temp"] = pd.to_numeric(df_visitas["temp"], errors="coerce")
    df_visitas["vol"] = pd.to_numeric(df_visitas["vol"], errors="coerce")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("pH Médio", f"{df_visitas['ph'].mean():.1f}" if not df_visitas['ph'].isna().all() else "—")
    m2.metric("Temperatura Média", f"{df_visitas['temp'].mean():.1f} °C" if not df_visitas['temp'].isna().all() else "—")
    m3.metric("Volume Médio", f"{df_visitas['vol'].mean():.0f} mL" if not df_visitas['vol'].isna().all() else "—")

st.markdown("---")

# 3. MAPAS E TERMÔMETRO
st.markdown("### 🗺️ Mapas de Risco e Termômetro")
df_mapa = df_final.dropna(subset=["lat", "lon"])
if not df_mapa.empty:
    centro_lat = df_mapa["lat"].mean()
    centro_lon = df_mapa["lon"].mean()
    tab1, tab2, tab3, tab4 = st.tabs(["📍 Mapa Base", "🔥 Mapa de Calor", "🌐 Clusters", "🏘️ Risco por Bairro"])
    
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
            fig_termo = go.Figure(go.Indicator(mode="gauge+number", value=positividade, number={'suffix': "%"}, title={'text': st_risco}, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': cor}, 'steps': [{'range': [0, 15], 'color': '#D6EAF8'}, {'range': [15, 40], 'color': '#FDEBD0'}, {'range': [40, 100], 'color': '#FADBD8'}]}))
            fig_termo.update_layout(height=350, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_termo, use_container_width=True)
            
       # --- ABA 2: MAPA DE CALOR ---
    with tab2:
        st.markdown("#### 🔥 Mapa de Calor (Intensidade de Focos)")
        
        # Filtra apenas as plantas positivas
        df_calor = df_mapa[df_mapa["positivo"]]
        
        if not df_calor.empty:
            # Cria o mapa usando o Plotly (não trava a rolagem)
            # Aumentei o radius para a mancha ficar maior e mais visível
            fig_mapa_calor = px.density_mapbox(
                df_calor, 
                lat="lat", 
                lon="lon", 
                z="qtd_especimes", 
                radius=60, # Aumentado de 40 para 60
                center=dict(lat=centro_lat, lon=centro_lon),
                zoom=13, # Zoom um pouco mais aberto
                mapbox_style="open-street-map",
                color_continuous_scale="Inferno" 
            )
            
            # Adiciona os pinos vermelhos por cima do calor
            for _, row in df_calor.iterrows():
                fig_mapa_calor.add_scattermapbox(
                    lat=[row["lat"]],
                    lon=[row["lon"]],
                    mode="markers",
                    marker=dict(size=12, color="#E63946"),
                    name="Aedes",
                    showlegend=False,
                    hovertext=f"Planta: {row['id_bromelia']}",
                    hoverinfo="text"
                )

            fig_mapa_calor.update_layout(
                margin=dict(l=0, r=0, t=0, b=0), 
                height=450,
                coloraxis_showscale=False 
            )
            st.plotly_chart(fig_mapa_calor, use_container_width=True)
            st.info("As manchas indicam a concentração de focos. Os pinos vermelhos mostram a localização exata de cada planta positiva.")
        else:
            st.info("✅ Nenhuma planta positiva para gerar o mapa de calor no momento.")
            
    with tab3:
        df_agrupado = df_mapa.groupby(["lat", "lon", "positivo"]).size().reset_index(name="quantidade")
        if not df_agrupado.empty:
            fig_cluster = px.scatter_mapbox(df_agrupado, lat="lat", lon="lon", size="quantidade", color="positivo", color_discrete_map={True: "#E63946", False: "#2E86AB"}, center=dict(lat=centro_lat, lon=centro_lon), zoom=15, mapbox_style="open-street-map", size_max=40)
            fig_cluster.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=450, legend_title_text="Status")
            st.plotly_chart(fig_cluster, use_container_width=True)
            
    with tab4:
        df_bairro = df_mapa.groupby("bairro").agg(lat=("lat", "mean"), lon=("lon", "mean"), plantas=("id_bromelia", "count")).reset_index()
        df_positivas = df_mapa[df_mapa["positivo"]].groupby("bairro").agg(positivas=("id_bromelia", "count")).reset_index()
        df_bairro = pd.merge(df_bairro, df_positivas, on="bairro", how="left").fillna(0)
        df_bairro["% risco"] = (df_bairro["positivas"] / df_bairro["plantas"] * 100).round(1)
        if not df_bairro.empty:
            fig_bairro = px.scatter_mapbox(df_bairro, lat="lat", lon="lon", size="plantas", color="% risco", color_continuous_scale=["#2E86AB", "#F4A261", "#E63946"], hover_name="bairro", center=dict(lat=centro_lat, lon=centro_lon), zoom=13, mapbox_style="open-street-map", size_max=50)
            fig_bairro.update_layout(height=450, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_bairro, use_container_width=True)

# 4. SÉRIE TEMPORAL
st.markdown("---")
st.markdown("### 📈 Série Temporal de Coletas")
if not df_visitas.empty and "data_visita" in df_visitas.columns:
    df_serie = df_visitas.copy()
    df_serie["data_visita"] = pd.to_datetime(df_serie["data_visita"], errors="coerce")
    df_serie["mes"] = df_serie["data_visita"].dt.to_period("M").astype(str)
    contagem = df_serie.groupby("mes").agg(visitas=("data_visita", "count")).reset_index()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=contagem["mes"], y=contagem["visitas"], name="Visitas", marker_color="#2E86AB"))
    fig.update_layout(barmode="group", height=350, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# 5. ESPÉCIES E ECOLOGIA
st.markdown("---")
col_esp, col_eco = st.columns([2, 1])
with col_esp:
    st.markdown("### 🦟 Frequência de Espécies")
    if not df_lab.empty:
        df_chart = df_lab.groupby("especie").agg({"qtd_especimes": "sum"}).reset_index()
        df_chart["especie"] = df_chart["especie"].str.replace("_", " ").str.capitalize()
        st.plotly_chart(px.bar(df_chart, x="especie", y="qtd_especimes", text="qtd_especimes", color="especie"), use_container_width=True)

with col_eco:
    st.markdown("### 🔬 pH vs Presença de Larvas")
    if not df_visitas.empty and not df_visitas['ph'].isna().all():
        st.plotly_chart(px.box(df_visitas, y="ph", points="all", color_discrete_sequence=["#E63946"]), use_container_width=True)

# 6. TIPOLOGIA
st.markdown("---")
st.markdown("### 🏠 Análise por Tipologia de Imóvel")
if not df_final.empty and "tipologia" in df_final.columns:
    df_tipo_agrupado = df_final.groupby("tipologia").agg(Total_Plantas=("id_bromelia", "count"), Positivas=("positivo", "sum")).reset_index()
    df_tipo_agrupado["% Positividade"] = (df_tipo_agrupado["Positivas"] / df_tipo_agrupado["Total_Plantas"] * 100).round(1)
    df_plot = pd.melt(df_tipo_agrupado, id_vars=["tipologia"], value_vars=["Positivas", "Total_Plantas"], var_name="Status", value_name="Quantidade")
    fig_tipo = px.bar(df_plot, x="tipologia", y="Quantidade", color="Status", barmode="group", text="Quantidade", color_discrete_map={"Positivas": "#E63946", "Total_Plantas": "#2E86AB"})
    for i, row in df_tipo_agrupado.iterrows():
        fig_tipo.add_annotation(x=row["tipologia"], y=row["Total_Plantas"] + 0.5, text=f"{row['% Positividade']}%", showarrow=False, font=dict(color="#E63946", size=14))
    fig_tipo.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig_tipo, use_container_width=True)

# 7. TABELAS FINAIS
st.markdown("---")
st.markdown("### 📊 Tabelas de Totais e Estatísticas")
col_tab1, col_tab2 = st.columns(2)

with col_tab1:
    st.markdown("#### 🦟 Totais por Espécie")
    if not df_lab.empty:
        df_esp = df_lab.groupby("especie").agg(Total=("qtd_especimes", "sum")).reset_index()
        df_esp["especie"] = df_esp["especie"].str.replace("_", " ").str.capitalize()
        total = df_esp["Total"].sum()
        df_esp["%"] = (df_esp["Total"] / total * 100).round(1).astype(str) + "%"
        st.dataframe(df_esp.rename(columns={"especie": "Espécie", "Total": "Larvas+Pupas"}), hide_index=True, use_container_width=True)

with col_tab2:
    st.markdown("#### 📈 Estatísticas da Água")
    if not df_visitas.empty:
        vars = {"pH": df_visitas["ph"], "Temp": df_visitas["temp"], "Volume": df_visitas["vol"]}
        stats = []
        for nome, serie in vars.items():
            dados = serie.dropna()
            if not dados.empty:
                stats.append({"Variável": nome, "N": len(dados), "Média": round(dados.mean(), 2), "Mediana": round(dados.median(), 2), "Desvio Padrão": round(dados.std(), 2)})
        st.dataframe(pd.DataFrame(stats), hide_index=True, use_container_width=True)

# 8. SAZONALIDADE E RANKING
st.markdown("---")
st.markdown("### 📈 Análise de Sazonalidade e Ranking de Bairros")
col_saz, col_rank = st.columns([2, 1])
with col_saz:
    st.markdown("#### Positividade de Aedes por Mês")
    if not df_visitas.empty and not df_final.empty:
        df_saz = df_visitas.copy()
        df_saz["data_visita"] = pd.to_datetime(df_saz["data_visita"], errors="coerce")
        df_saz["mes"] = df_saz["data_visita"].dt.to_period("M").astype(str)
        df_saz = pd.merge(df_saz, df_final[["id_bromelia", "positivo"]], on="id_bromelia", how="left")
        df_saz = df_saz.groupby("mes").agg(Total=("id_bromelia", "nunique"), Positivas=("positivo", "sum")).reset_index()
        df_saz["%"] = (df_saz["Positivas"] / df_saz["Total"] * 100).round(1)
        st.plotly_chart(px.line(df_saz, x="mes", y="%", markers=True, title="Variação da Positividade ao Longo do Tempo"), use_container_width=True)

with col_rank:
    st.markdown("#### 🏘️ Ranking de Bairros (Maior Risco)")
    if not df_final.empty:
        df_rank = df_final.groupby("bairro").agg(Total=("id_bromelia", "count"), Positivas=("positivo", "sum")).reset_index()
        df_rank["%"] = (df_rank["Positivas"] / df_rank["Total"] * 100).round(1)
        st.dataframe(df_rank.sort_values(by="%", ascending=False).rename(columns={"bairro": "Bairro", "Total": "Plantas", "Positivas": "Positivas", "%": "% Risco"}), hide_index=True, use_container_width=True)

# 9. ESTATÍSTICA DESCRITIVA
st.markdown("---")
st.markdown("### 📈 Estatística Descritiva (Variáveis Ambientais)")
if not df_visitas.empty:
    df_visitas["ph"] = pd.to_numeric(df_visitas["ph"], errors="coerce")
    df_visitas["temp"] = pd.to_numeric(df_visitas["temp"], errors="coerce")
    df_visitas["vol"] = pd.to_numeric(df_visitas["vol"], errors="coerce")
    stats = []
    variaveis = {"pH da Água": df_visitas["ph"], "Temperatura (°C)": df_visitas["temp"], "Volume (mL)": df_visitas["vol"]}
    for nome, serie in variaveis.items():
        dados = serie.dropna()
        if not dados.empty:
            stats.append({"Variável": nome, "N": len(dados), "Média": round(dados.mean(), 2), "Mediana": round(dados.median(), 2), "Desvio Padrão": round(dados.std(), 2), "Mínimo": round(dados.min(), 2), "Máximo": round(dados.max(), 2)})
    if stats:
        st.dataframe(pd.DataFrame(stats), hide_index=True, use_container_width=True)

# 10. CORRELAÇÃO ECOLÓGICA
st.markdown("---")
st.markdown("### 🔬 Correlação Ecológica: Água vs. Presença de Larvas")
if not df_visitas.empty and not df_final.empty:
    df_eco = pd.merge(df_visitas, df_final[["id_bromelia", "positivo"]], on="id_bromelia", how="left")
    df_eco["Status"] = df_eco["positivo"].apply(lambda x: "Com Aedes" if x else "Sem Aedes")
    df_eco["ph"] = pd.to_numeric(df_eco["ph"], errors="coerce")
    df_eco["temp"] = pd.to_numeric(df_eco["temp"], errors="coerce")
    df_eco["vol"] = pd.to_numeric(df_eco["vol"], errors="coerce")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### 🧪 pH")
        st.plotly_chart(px.box(df_eco.dropna(subset=["ph"]), x="Status", y="ph", color="Status", color_discrete_map={"Com Aedes": "#E63946", "Sem Aedes": "#2E86AB"}), use_container_width=True)
    with c2:
        st.markdown("#### 🌡️ Temperatura")
        st.plotly_chart(px.box(df_eco.dropna(subset=["temp"]), x="Status", y="temp", color="Status", color_discrete_map={"Com Aedes": "#E63946", "Sem Aedes": "#2E86AB"}), use_container_width=True)
    with c3:
        st.markdown("#### 💧 Volume")
        st.plotly_chart(px.box(df_eco.dropna(subset=["vol"]), x="Status", y="vol", color="Status", color_discrete_map={"Com Aedes": "#E63946", "Sem Aedes": "#2E86AB"}), use_container_width=True)

# 11. DISPERSÃO DE ESPÉCIES
st.markdown("---")
st.markdown("### 🌿 Relação entre Gênero da Bromélia e Espécies de Mosquitos")
if not df_lab.empty and not df_final.empty and "genero" in df_final.columns:
    df_genero = df_final[["id_bromelia", "genero"]].drop_duplicates()
    df_amostras_genero = pd.merge(df_amostras, df_genero, on="id_bromelia", how="left")
    df_dispersao = pd.merge(df_amostras_genero, df_lab, on="codigo_amostra", how="inner")
    
    if not df_dispersao.empty:
        df_chart = df_dispersao.groupby(["genero", "especie"]).agg({"qtd_especimes": "sum"}).reset_index()
        df_chart["genero"] = df_chart["genero"].str.replace("_", " ").str.capitalize()
        df_chart["especie"] = df_chart["especie"].str.replace("_", " ").str.capitalize()
        
        fig_disp = px.bar(df_chart, x="genero", y="qtd_especimes", color="especie", barmode="group", text="qtd_especimes", labels={"genero": "Gênero da Bromélia", "qtd_especimes": "Espécimes", "especie": "Espécie de Mosquito"})
        fig_disp.update_layout(height=450, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_disp, use_container_width=True)

# 13. AMOSTRAS PENDENTES DE ANÁLISE
st.markdown("---")
st.markdown("### ⏳ Amostras Pendentes de Análise (Coletadas mas não Processadas)")

# ⚠️ SUBSTITUA ESTE LINK PELO LINK DO SEU FORMULÁRIO DE LABORATÓRIO NO KOBO
URL_FORMULARIO_LAB = "https://ee.kobotoolbox.org/AtOwQDsP"

if not df_amostras.empty:
    # 1. Junta as amostras com as datas de visita
    df_pendentes = pd.merge(df_amostras, df_visitas[["id_bromelia", "data_visita"]], on="id_bromelia", how="left")
    
    # 2. Verifica quais amostras já têm resultado no lab
    codigos_com_resultado = df_lab["codigo_amostra"].unique() if not df_lab.empty else []
    df_pendentes["Analisada"] = df_pendentes["codigo_amostra"].isin(codigos_com_resultado)
    
    # 3. Filtra apenas as que NÃO foram analisadas
    df_apenas_pendentes = df_pendentes[~df_pendentes["Analisada"]].copy()
    
    if not df_apenas_pendentes.empty:
        # Calcula os dias de espera
        df_apenas_pendentes["data_visita"] = pd.to_datetime(df_apenas_pendentes["data_visita"], errors="coerce")
        df_apenas_pendentes["Dias de Espera"] = (datetime.now() - df_apenas_pendentes["data_visita"]).dt.days
        
        # Remove duplicatas
        df_apenas_pendentes = df_apenas_pendentes.drop_duplicates(subset=["codigo_amostra"])
        
        # Prepara a tabela
        df_exibicao = df_apenas_pendentes[["codigo_amostra", "id_bromelia", "data_visita", "Dias de Espera"]].copy()
        df_exibicao["data_visita"] = df_exibicao["data_visita"].dt.strftime('%d/%m/%Y')
        
        # Cria a coluna com o link do formulário
        df_exibicao["Ação"] = URL_FORMULARIO_LAB
        
        # Renomeia as colunas
        df_exibicao = df_exibicao.rename(columns={
            "codigo_amostra": "Código da Amostra",
            "id_bromelia": "Planta",
            "data_visita": "Data da Coleta",
            "Dias de Espera": "Dias de Espera",
            "Ação": "Ação"
        })
        
        # Ordena pelos mais antigos
        df_exibicao = df_exibicao.sort_values(by="Dias de Espera", ascending=False)
        
        # Mostra a tabela com o link clicável
        st.dataframe(
            df_exibicao[["Código da Amostra", "Planta", "Data da Coleta", "Dias de Espera", "Ação"]],
            hide_index=True,
            use_container_width=True,
            column_config={
                "Ação": st.column_config.LinkColumn(
                    "Ação",
                    display_text="🔬 Analisar"
                )
            }
        )
        
        # Alerta de atraso
        if df_exibicao["Dias de Espera"].max() > 30:
            st.warning(f"⚠️ Existem amostras com mais de 30 dias de espera! A mais antiga está aguardando há {df_exibicao['Dias de Espera'].max()} dias.")
        else:
            st.info("✅ Todas as amostras pendentes foram coletadas há menos de 30 dias.")
            
        # Botão de download
        csv_pendentes = df_exibicao.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Lista de Pendências (CSV)",
            data=csv_pendentes,
            file_name='amostras_pendentes.csv',
            mime='text/csv',
        )
    else:
        st.success("🎉 Todas as amostras coletadas já foram analisadas no laboratório!")
else:
    st.info("Ainda não há amostras coletadas para verificar.")

st.markdown("---")
st.caption("Dashboard desenvolvido por Flávio Santos | PPG-VCV / IOC - Fiocruz | Contato: fhsantos@gmail.com")