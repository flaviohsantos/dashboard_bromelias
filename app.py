# -*- coding: utf-8 -*-
"""Dashboard — Bromélias Ornamentais Urbanas e Culicídeos."""
import difflib
import hmac
import os
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium

# set_page_config precisa ser o primeiro comando Streamlit
st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")

FUSO = ZoneInfo("America/Sao_Paulo")
AGORA = datetime.now(FUSO)
HOJE = pd.Timestamp(AGORA.date())
URL_FORMULARIO_LAB = "https://ee.kobotoolbox.org/AtOwQDsP"

# Critério de positividade: aplicado ao nome normalizado da espécie (ex.: "aedes_aegypti")
CRITERIOS = {
    "Aedes aegypti": lambda s: "aegypti" in s,
    "Aedes albopictus": lambda s: "albopictus" in s,
    "Qualquer Aedes": lambda s: "aedes" in s or "aegypti" in s or "albopictus" in s,
}
STATUS_CORES = {"Positivo": "#E63946", "Negativo": "#2E86AB", "Sem análise": "#9E9E9E"}
STATUS_ICONES = {"Positivo": "red", "Negativo": "blue", "Sem análise": "gray"}


# --- FUNÇÕES AUXILIARES ---
def _get_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)


def check_password():
    senha = _get_secret("SENHA_ACESSO")
    if not senha:
        st.error("Senha de acesso não configurada (SENHA_ACESSO). Acesso bloqueado.")
        return False

    def password_entered():
        digitada = st.session_state.get("password", "")
        st.session_state["password_correct"] = hmac.compare_digest(
            str(digitada).encode("utf-8"), str(senha).encode("utf-8")
        )
        st.session_state.pop("password", None)

    if st.session_state.get("password_correct"):
        return True
    st.text_input("Digite a senha de acesso ao Dashboard:", type="password",
                  on_change=password_entered, key="password")
    if st.session_state.get("password_correct") is False:
        st.error("😕 Senha incorreta. Tente novamente.")
    return False


@st.cache_data(ttl=300, show_spinner=False)
def baixar_formulario(uid, token, base_url):
    if not uid:
        return []
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
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().replace("_", " ").strip().split())


def numero_inteiro(valor):
    if valor is None or str(valor).strip() == "":
        return 0
    try:
        return max(0, int(float(str(valor).strip().replace(",", "."))))
    except (ValueError, TypeError):
        return 0


def normalizar_codigo(valor):
    """Padroniza códigos de amostra: sem espaços, maiúsculas, traços unificados."""
    return re.sub(r"\s+", "", str(valor)).upper().replace("–", "-").replace("—", "-")


def para_numero(serie):
    return pd.to_numeric(serie.astype(str).str.replace(",", ".", regex=False), errors="coerce")


def plantas_positivas_por_criterio(df_lab, df_amostras):
    """Nº de plantas positivas para cada critério (independe da seleção na barra lateral)."""
    out = {}
    for nome, fn in CRITERIOS.items():
        if df_lab.empty:
            out[nome] = 0
            continue
        mask = df_lab["especie"].apply(fn).astype(bool)
        cods = df_lab.loc[mask, "codigo_amostra"].unique()
        out[nome] = int(df_amostras.loc[df_amostras["codigo_amostra"].isin(cods), "id_bromelia"].nunique())
    return out


# --- ACESSO ---
if not check_password():
    st.stop()

st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")
if st.sidebar.button("🔄 Atualizar dados agora"):
    st.cache_data.clear()
    st.rerun()
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption(f"Pesquisador: Flávio Santos (IOC - Fiocruz) | Atualizado em: {AGORA.strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")

# --- CARREGAMENTO ---
base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados do Kobo..."):
    try:
        lista_campo = baixar_formulario(uid_campo, token, base_url)
        lista_lab = baixar_formulario(uid_lab, token, base_url)
    except requests.RequestException as exc:
        st.error(f"Falha ao baixar dados do Kobo: {exc}")
        st.stop()

if not lista_campo:
    st.warning("Nenhum dado encontrado.")
    st.stop()

# --- PROCESSAMENTO ---
plantas, visitas_list, amostras = [], [], []

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
        except ValueError:
            pass

    plantas.append({"id_bromelia": id_planta, "bairro": bairro, "genero": genero,
                    "tipologia": tipologia, "lat": lat, "lon": lon})

    visitas = item.get("rep_visitas", [])
    if not isinstance(visitas, list):
        continue
    for n_visita, v in enumerate(visitas):
        id_visita = f"{indice}-{n_visita}"
        data_v = v.get("rep_visitas/data_visita")
        visitas_list.append({
            "id_visita": id_visita, "id_bromelia": id_planta, "data_visita": data_v,
            "ph": v.get("rep_visitas/ph_agua"),
            "temp": v.get("rep_visitas/temp_agua_c"),
            "vol": v.get("rep_visitas/volume_agua_ml"),
        })
        ams = v.get("rep_visitas/rep_amostras", [])
        if isinstance(ams, list):
            for a in ams:
                cod = a.get("rep_visitas/rep_amostras/codigo_amostra")
                if cod and str(cod).strip():
                    # A data da coleta fica junto da amostra (não é inferida depois pela planta)
                    amostras.append({"id_visita": id_visita, "id_bromelia": id_planta,
                                     "codigo_amostra": normalizar_codigo(cod), "data_visita": data_v})

codigos_lab = set()   # amostras com formulário de laboratório preenchido (mesmo sem larvas)
lab_especies = []
for item in lista_lab:
    cod_lab = item.get("grp_amostra/codigo_amostra")
    if not cod_lab or not str(cod_lab).strip():
        continue
    cod_lab = normalizar_codigo(cod_lab)
    codigos_lab.add(cod_lab)
    for e in item.get("rep_especies", []) or []:
        especie = e.get("rep_especies/especie_identificada") or "nao_identificado"
        qtd = numero_inteiro(e.get("rep_especies/qtd_larvas")) + numero_inteiro(e.get("rep_especies/qtd_pupas"))
        lab_especies.append({"codigo_amostra": cod_lab,
                             "especie": normalizar_texto(especie).replace(" ", "_"),
                             "qtd_especimes": qtd})

df_plantas = pd.DataFrame(plantas, columns=["id_bromelia", "bairro", "genero", "tipologia", "lat", "lon"]
                          ).drop_duplicates(subset=["id_bromelia"])
df_visitas = pd.DataFrame(visitas_list, columns=["id_visita", "id_bromelia", "data_visita", "ph", "temp", "vol"])
df_amostras = pd.DataFrame(amostras, columns=["id_visita", "id_bromelia", "codigo_amostra", "data_visita"]
                           ).drop_duplicates(subset=["codigo_amostra"])
df_lab = pd.DataFrame(lab_especies, columns=["codigo_amostra", "especie", "qtd_especimes"])

df_visitas["data_visita"] = pd.to_datetime(df_visitas["data_visita"], errors="coerce")
df_amostras["data_visita"] = pd.to_datetime(df_amostras["data_visita"], errors="coerce")
for col in ["ph", "temp", "vol"]:
    df_visitas[col] = para_numero(df_visitas[col])

# Códigos do laboratório que não existem em nenhuma coleta (provável erro de digitação)
df_amostras_todas = df_amostras.copy()
codigos_lab_orfaos = sorted(codigos_lab - set(df_amostras["codigo_amostra"]))

# --- BARRA LATERAL: CRITÉRIO E FILTRO DE DATA ---
st.sidebar.header("🦟 Critério de positividade")
criterio_nome = st.sidebar.selectbox("Espécie-alvo", list(CRITERIOS), index=0,
                                     help="Define o que conta como planta positiva em todo o painel.")
criterio_fn = CRITERIOS[criterio_nome]

st.sidebar.markdown("---")
st.sidebar.header("🔎 Filtro de Data")
periodo_sel = None
datas_validas = df_visitas["data_visita"].dropna()
if not datas_validas.empty:
    data_min, data_max = datas_validas.min().date(), datas_validas.max().date()
    periodo_sel = st.sidebar.date_input("Período da Visita", value=(data_min, data_max),
                                        min_value=data_min, max_value=data_max)

if periodo_sel and len(periodo_sel) == 2:
    ini = pd.Timestamp(periodo_sel[0])
    fim = pd.Timestamp(periodo_sel[1]) + pd.Timedelta(days=1)
    df_visitas = df_visitas[(df_visitas["data_visita"] >= ini) & (df_visitas["data_visita"] < fim)]
    # Amostras filtradas pela data da PRÓPRIA coleta (e não pela planta)
    df_amostras = df_amostras[(df_amostras["data_visita"] >= ini) & (df_amostras["data_visita"] < fim)]
    df_plantas = df_plantas[df_plantas["id_bromelia"].isin(df_visitas["id_bromelia"].unique())]

df_lab = df_lab[df_lab["codigo_amostra"].isin(df_amostras["codigo_amostra"])].copy()

# --- RESULTADO POR AMOSTRA ---
df_lab["alvo"] = df_lab["especie"].apply(criterio_fn).astype(bool)
df_lab["qtd_alvo"] = df_lab["qtd_especimes"].where(df_lab["alvo"], 0)

if df_lab.empty:
    df_res_lab = pd.DataFrame(columns=["codigo_amostra", "qtd_total", "qtd_alvo", "positiva"])
else:
    df_res_lab = df_lab.groupby("codigo_amostra").agg(
        qtd_total=("qtd_especimes", "sum"), qtd_alvo=("qtd_alvo", "sum"), positiva=("alvo", "any")
    ).reset_index()

df_am = df_amostras.merge(df_res_lab, on="codigo_amostra", how="left")
df_am["analisada"] = df_am["codigo_amostra"].isin(codigos_lab)
df_am["positiva"] = df_am["positiva"].eq(True)
df_am["qtd_total"] = pd.to_numeric(df_am["qtd_total"], errors="coerce").fillna(0)
df_am["qtd_alvo"] = pd.to_numeric(df_am["qtd_alvo"], errors="coerce").fillna(0)

# --- RESULTADO POR PLANTA ---
if df_am.empty:
    df_pl = pd.DataFrame(columns=["id_bromelia", "amostras", "analisadas", "positivas", "qtd_total", "qtd_alvo"])
else:
    df_pl = df_am.groupby("id_bromelia").agg(
        amostras=("codigo_amostra", "count"), analisadas=("analisada", "sum"),
        positivas=("positiva", "sum"), qtd_total=("qtd_total", "sum"), qtd_alvo=("qtd_alvo", "sum")
    ).reset_index()

df_final = df_plantas.merge(df_pl, on="id_bromelia", how="left")
for col in ["amostras", "analisadas", "positivas", "qtd_total", "qtd_alvo"]:
    df_final[col] = pd.to_numeric(df_final[col], errors="coerce").fillna(0)
df_final["analisada"] = df_final["analisadas"] > 0
df_final["positivo"] = df_final["positivas"] > 0
df_final["status"] = "Sem análise"
df_final.loc[df_final["analisada"], "status"] = "Negativo"
df_final.loc[df_final["positivo"], "status"] = "Positivo"

if df_final.empty:
    st.warning("Nenhuma planta com visita no período selecionado.")
    st.stop()

# Positividade: plantas positivas ÷ plantas COM amostra analisada
df_analisadas = df_final[df_final["analisada"]]
n_plantas = len(df_final)
n_analisadas = len(df_analisadas)
plantas_positivas = int(df_analisadas["positivo"].sum())
positividade = (plantas_positivas / n_analisadas * 100) if n_analisadas else 0.0
total_especimes = int(df_final["qtd_total"].sum())

df_rank = df_final.groupby("bairro").agg(
    Plantas=("id_bromelia", "count"), Analisadas=("analisada", "sum"), Positivas=("positivo", "sum")
).reset_index()
df_rank["% Risco"] = (df_rank["Positivas"] / df_rank["Analisadas"].where(df_rank["Analisadas"] > 0) * 100).round(1)

bairro_alerta = "Nenhum"
df_top = df_rank.dropna(subset=["% Risco"])
df_top = df_top[df_top["% Risco"] > 0].sort_values("% Risco", ascending=False)
if not df_top.empty:
    t = df_top.iloc[0]
    bairro_alerta = f"{str(t['bairro']).capitalize()} ({int(t['Positivas'])}/{int(t['Analisadas'])} plantas)"

if n_analisadas == 0:
    nivel, bg, cor, icone, msg = "SEM DADOS", "#EEEEEE", "#666666", "ℹ️", "Nenhuma planta com amostra analisada no período."
elif positividade < 15:
    nivel, bg, cor, icone, msg = "BAIXO", "#D6EAF8", "#2E86AB", "✅", "Risco Baixo."
elif positividade < 40:
    nivel, bg, cor, icone, msg = "MÉDIO", "#FDEBD0", "#F4A261", "⚠️", f"Risco Médio. Atenção ao bairro {bairro_alerta}."
else:
    nivel, bg, cor, icone, msg = "ALTO", "#FADBD8", "#E63946", "🚨", f"Risco Alto. Ação urgente no bairro {bairro_alerta}."

# 1. PAINEL EXECUTIVO
st.markdown("### 📊 Painel Executivo")
col_kpis, col_alerta = st.columns([3, 2])
with col_kpis:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Plantas", n_plantas)
    c2.metric("Analisadas", n_analisadas)
    c3.metric("Positivas", plantas_positivas)
    c4.metric("Positividade", f"{positividade:.1f}%")
    c5.metric("Espécimes (Lab)", total_especimes)
    st.caption(f"Positividade = plantas com {criterio_nome} ÷ plantas com amostra analisada. "
               f"Plantas sem análise: {n_plantas - n_analisadas}.")
    por_criterio = plantas_positivas_por_criterio(df_lab, df_amostras)
    st.caption("Plantas positivas por espécie (período): " + " · ".join(f"{k}: {v}" for k, v in por_criterio.items()))

with col_alerta:
    st.markdown(f"""<div style="background-color: {bg}; padding: 15px; border-radius: 10px; border-left: 5px solid {cor}; height: 100%;">
        <h4 style="color: {cor}; margin-top: 0;">{icone} Status: {nivel}</h4>
        <p style="color: #333; margin-bottom: 0; font-size: 14px;">{msg}</p></div>""", unsafe_allow_html=True)

st.markdown("---")

# 2. MÉDIAS DA ÁGUA
st.markdown("### 💧 Médias da Água")
if not df_visitas.empty:
    m1, m2, m3 = st.columns(3)
    m1.metric("pH Médio", f"{df_visitas['ph'].mean():.1f}" if df_visitas["ph"].notna().any() else "—")
    m2.metric("Temperatura Média", f"{df_visitas['temp'].mean():.1f} °C" if df_visitas["temp"].notna().any() else "—")
    m3.metric("Volume Médio", f"{df_visitas['vol'].mean():.0f} mL" if df_visitas["vol"].notna().any() else "—")

st.markdown("---")

# 3. AMOSTRAS PENDENTES
st.markdown("### ⏳ Amostras Pendentes de Análise (Coletadas mas não Processadas)")
if not df_am.empty:
    df_pend = df_am[~df_am["analisada"]].copy()
    if not df_pend.empty:
        df_pend["Dias de Espera"] = (HOJE - df_pend["data_visita"]).dt.days.astype("Int64")
        df_exibicao = df_pend[["codigo_amostra", "id_bromelia", "data_visita", "Dias de Espera"]].copy()
        df_exibicao["data_visita"] = df_exibicao["data_visita"].dt.strftime("%d/%m/%Y")
        df_exibicao["Ação"] = URL_FORMULARIO_LAB
        df_exibicao = df_exibicao.rename(columns={"codigo_amostra": "Código da Amostra", "id_bromelia": "Planta",
                                                  "data_visita": "Data da Coleta"})
        df_exibicao = df_exibicao.sort_values(by="Dias de Espera", ascending=False)
        st.dataframe(df_exibicao[["Código da Amostra", "Planta", "Data da Coleta", "Dias de Espera", "Ação"]],
                     hide_index=True, use_container_width=True,
                     column_config={"Ação": st.column_config.LinkColumn("Ação", display_text="🔬 Analisar")})
        dias_max = df_exibicao["Dias de Espera"].max()
        if pd.notna(dias_max) and dias_max > 30:
            st.warning(f"⚠️ Existem amostras com mais de 30 dias de espera! A mais antiga está aguardando há {int(dias_max)} dias.")
        else:
            st.info("✅ Todas as amostras pendentes foram coletadas há menos de 30 dias.")
        st.download_button(label="📥 Baixar Lista de Pendências (CSV)",
                           data=df_exibicao.to_csv(index=False).encode("utf-8"),
                           file_name="amostras_pendentes.csv", mime="text/csv")
    else:
        st.success("🎉 Todas as amostras coletadas já foram analisadas no laboratório!")
else:
    st.info("Ainda não há amostras coletadas para verificar.")

if codigos_lab_orfaos:
    with st.expander(f"⚠️ {len(codigos_lab_orfaos)} código(s) do laboratório sem coleta correspondente"):
        codigos_campo = sorted(set(df_amostras_todas["codigo_amostra"]))
        for cod in codigos_lab_orfaos:
            prox = difflib.get_close_matches(cod, codigos_campo, n=1, cutoff=0.6)
            st.write(f"**{cod}** → código parecido no campo: {prox[0] if prox else 'nenhum'}")

st.markdown("---")

# 4. MAPAS E TERMÔMETRO
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
                    folium.Circle(location=[row["lat"], row["lon"]], radius=100, color=STATUS_CORES["Positivo"],
                                  fill=True, fill_opacity=0.2, weight=2).add_to(m1)
                folium.Marker(location=[row["lat"], row["lon"]],
                              icon=folium.Icon(color=STATUS_ICONES[row["status"]], icon="info-sign"),
                              popup=f"<b>{row['id_bromelia']}</b><br>{row['status'].upper()}").add_to(m1)
            st_folium(m1, width=None, height=450, key="mapa1")
        with col_termo:
            st.markdown("#### 🌡️ Termômetro")
            fig_termo = go.Figure(go.Indicator(
                mode="gauge+number", value=positividade, number={"suffix": "%"}, title={"text": nivel},
                gauge={"axis": {"range": [0, 100]}, "bar": {"color": cor},
                       "steps": [{"range": [0, 15], "color": "#D6EAF8"},
                                 {"range": [15, 40], "color": "#FDEBD0"},
                                 {"range": [40, 100], "color": "#FADBD8"}]}))
            fig_termo.update_layout(height=350, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(fig_termo, use_container_width=True)

    with tab2:
        st.markdown(f"#### 🔥 Mapa de Calor ({criterio_nome}: larvas + pupas)")
        df_calor = df_mapa[df_mapa["positivo"]]
        if not df_calor.empty:
            fig_mapa_calor = px.density_mapbox(
                df_calor, lat="lat", lon="lon", z="qtd_alvo", radius=60,
                center=dict(lat=centro_lat, lon=centro_lon), zoom=13,
                mapbox_style="open-street-map", color_continuous_scale="Inferno")
            fig_mapa_calor.add_scattermapbox(
                lat=df_calor["lat"], lon=df_calor["lon"], mode="markers",
                marker=dict(size=12, color="#E63946"), showlegend=False,
                hovertext=df_calor["id_bromelia"], hoverinfo="text")
            fig_mapa_calor.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=450, coloraxis_showscale=False)
            st.plotly_chart(fig_mapa_calor, use_container_width=True)
        else:
            st.info(f"✅ Nenhuma planta positiva para {criterio_nome} no período.")

    with tab3:
        df_agrupado = df_mapa.groupby(["lat", "lon", "status"]).size().reset_index(name="quantidade")
        fig_cluster = px.scatter_mapbox(
            df_agrupado, lat="lat", lon="lon", size="quantidade", color="status",
            color_discrete_map=STATUS_CORES, center=dict(lat=centro_lat, lon=centro_lon),
            zoom=15, mapbox_style="open-street-map", size_max=40)
        fig_cluster.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=450, legend_title_text="Status")
        st.plotly_chart(fig_cluster, use_container_width=True)

    with tab4:
        df_bairro = df_mapa.groupby("bairro").agg(
            lat=("lat", "mean"), lon=("lon", "mean"), plantas=("id_bromelia", "count"),
            analisadas=("analisada", "sum"), positivas=("positivo", "sum")).reset_index()
        df_bairro["% risco"] = (df_bairro["positivas"] / df_bairro["analisadas"].where(df_bairro["analisadas"] > 0)
                                * 100).round(1).fillna(0)
        fig_bairro = px.scatter_mapbox(
            df_bairro, lat="lat", lon="lon", size="plantas", color="% risco",
            color_continuous_scale=["#2E86AB", "#F4A261", "#E63946"], hover_name="bairro",
            hover_data=["analisadas", "positivas"], center=dict(lat=centro_lat, lon=centro_lon),
            zoom=13, mapbox_style="open-street-map", size_max=50)
        fig_bairro.update_layout(height=450, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_bairro, use_container_width=True)

# 5. SÉRIE TEMPORAL
st.markdown("---")
st.markdown("### 📈 Série Temporal de Coletas")
df_serie = df_visitas.dropna(subset=["data_visita"]).copy()
if not df_serie.empty:
    df_serie["mes"] = df_serie["data_visita"].dt.to_period("M").astype(str)
    contagem = df_serie.groupby("mes").agg(visitas=("id_visita", "count")).reset_index()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=contagem["mes"], y=contagem["visitas"], name="Visitas", marker_color="#2E86AB"))
    fig.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

# 6. ESPÉCIES E ECOLOGIA
st.markdown("---")
col_esp, col_eco = st.columns([2, 1])
with col_esp:
    st.markdown("### 🦟 Frequência de Espécies")
    if not df_lab.empty:
        df_chart = df_lab.groupby("especie").agg(qtd_especimes=("qtd_especimes", "sum")).reset_index()
        df_chart["especie"] = df_chart["especie"].str.replace("_", " ").str.capitalize()
        st.plotly_chart(px.bar(df_chart, x="especie", y="qtd_especimes", text="qtd_especimes", color="especie"),
                        use_container_width=True)
with col_eco:
    st.markdown(f"### 🔬 pH × presença de {criterio_nome}")
    # Positividade por VISITA: positiva se alguma amostra analisada daquela visita for positiva
    df_vis_res = df_am[df_am["analisada"]].groupby("id_visita").agg(positiva=("positiva", "any")).reset_index()
    df_ph = df_visitas.merge(df_vis_res, on="id_visita", how="inner").dropna(subset=["ph"])
    if not df_ph.empty:
        df_ph["Resultado"] = df_ph["positiva"].map({True: "Positiva", False: "Negativa"})
        st.plotly_chart(px.box(df_ph, x="Resultado", y="ph", points="all", color="Resultado",
                               color_discrete_map={"Positiva": "#E63946", "Negativa": "#2E86AB"}),
                        use_container_width=True)
    else:
        st.info("Sem visitas com pH e amostra analisada.")

# 7. TIPOLOGIA
st.markdown("---")
st.markdown("### 🏠 Análise por Tipologia de Imóvel")
df_tipo = df_final.groupby("tipologia").agg(
    Analisadas=("analisada", "sum"), Positivas=("positivo", "sum")).reset_index()
df_tipo["% Positividade"] = (df_tipo["Positivas"] / df_tipo["Analisadas"].where(df_tipo["Analisadas"] > 0) * 100).round(1)
df_plot = pd.melt(df_tipo, id_vars=["tipologia"], value_vars=["Positivas", "Analisadas"],
                  var_name="Status", value_name="Quantidade")
fig_tipo = px.bar(df_plot, x="tipologia", y="Quantidade", color="Status", barmode="group", text="Quantidade",
                  color_discrete_map={"Positivas": "#E63946", "Analisadas": "#2E86AB"})
for _, row in df_tipo.iterrows():
    pct = f"{row['% Positividade']}%" if pd.notna(row["% Positividade"]) else "—"
    fig_tipo.add_annotation(x=row["tipologia"], y=row["Analisadas"] + 0.5, text=pct, showarrow=False,
                            font=dict(color="#E63946", size=14))
fig_tipo.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig_tipo, use_container_width=True)

# 8. TABELAS FINAIS
st.markdown("---")
st.markdown("### 📊 Tabelas de Totais e Estatísticas")
col_tab1, col_tab2 = st.columns(2)
with col_tab1:
    st.markdown("#### 🦟 Totais por Espécie")
    if not df_lab.empty:
        df_esp = df_lab.groupby("especie").agg(Total=("qtd_especimes", "sum")).reset_index()
        df_esp["especie"] = df_esp["especie"].str.replace("_", " ").str.capitalize()
        df_esp["%"] = (df_esp["Total"] / df_esp["Total"].sum() * 100).round(1).astype(str) + "%"
        st.dataframe(df_esp.rename(columns={"especie": "Espécie", "Total": "Larvas+Pupas"}),
                     hide_index=True, use_container_width=True)
with col_tab2:
    st.markdown("#### 📈 Estatística Descritiva (Variáveis Ambientais)")
    if not df_visitas.empty:
        variaveis = {"pH da Água": df_visitas["ph"], "Temperatura (°C)": df_visitas["temp"],
                     "Volume (mL)": df_visitas["vol"]}
        stats = []
        for nome, serie in variaveis.items():
            dados = serie.dropna()
            if not dados.empty:
                stats.append({"Variável": nome, "N": len(dados), "Média": round(dados.mean(), 2),
                              "Mediana": round(dados.median(), 2),
                              "Desvio Padrão": round(dados.std(), 2) if len(dados) > 1 else None,
                              "Mínimo": round(dados.min(), 2), "Máximo": round(dados.max(), 2)})
        if stats:
            st.dataframe(pd.DataFrame(stats), hide_index=True, use_container_width=True)

# 9. SAZONALIDADE E RANKING
st.markdown("---")
st.markdown("### 📈 Análise de Sazonalidade e Ranking de Bairros")
col_saz, col_rank = st.columns([2, 1])
with col_saz:
    st.markdown(f"#### Positividade de {criterio_nome} por Mês")
    # Por mês da COLETA: plantas positivas ÷ plantas analisadas naquele mês
    df_an = df_am[df_am["analisada"]].dropna(subset=["data_visita"]).copy()
    if not df_an.empty:
        df_an["mes"] = df_an["data_visita"].dt.to_period("M").astype(str)
        df_saz = df_an.groupby("mes").agg(
            Plantas_analisadas=("id_bromelia", "nunique"), Amostras=("codigo_amostra", "count")).reset_index()
        pos_mes = (df_an[df_an["positiva"]].groupby("mes")["id_bromelia"].nunique()
                   .rename("Plantas_positivas").reset_index())
        df_saz = df_saz.merge(pos_mes, on="mes", how="left").fillna({"Plantas_positivas": 0})
        df_saz["%"] = (df_saz["Plantas_positivas"] / df_saz["Plantas_analisadas"] * 100).round(1)
        st.plotly_chart(px.line(df_saz, x="mes", y="%", markers=True,
                                hover_data=["Plantas_analisadas", "Plantas_positivas", "Amostras"],
                                title="% de plantas analisadas que foram positivas, por mês de coleta"),
                        use_container_width=True)
    else:
        st.info("Sem amostras analisadas no período.")
with col_rank:
    st.markdown("#### 🏘️ Ranking de Bairros (Maior Risco)")
    st.caption("% Risco = plantas positivas ÷ plantas analisadas.")
    st.dataframe(df_rank.sort_values(by="% Risco", ascending=False, na_position="last"),
                 hide_index=True, use_container_width=True)