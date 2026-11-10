# -*- coding: utf-8 -*-
import difflib
import hmac
import os
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from folium.plugins import HeatMap
import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_folium import st_folium

# set_page_config precisa ser o primeiro comando Streamlit
st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")

FUSO = ZoneInfo("America/Sao_Paulo")
AGORA = datetime.now(FUSO)
HOJE = pd.Timestamp(AGORA.date())
URL_FORMULARIO_LAB = "https://ee.kobotoolbox.org/AtOwQDsP"
RISCO_MEDIO, RISCO_ALTO, PRAZO_VISITA_DIAS = 15, 40, 35

CRITERIOS = {
    "Aedes aegypti": lambda s: "aegypti" in s,
    "Aedes albopictus": lambda s: "albopictus" in s,
    "Qualquer Aedes": lambda s: "aedes" in s or "aegypti" in s or "albopictus" in s,
}
STATUS_CORES = {"Positivo": "#E63946", "Negativo": "#2E86AB", "Sem análise": "#9E9E9E"}
STATUS_ICONES = {"Positivo": "red", "Negativo": "blue", "Sem análise": "gray"}

def _get_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)

def check_password():
    senha = _get_secret("SENHA_ACESSO")
    if not senha:
        st.error("Senha não configurada."); return False
    def password_entered():
        st.session_state["password_correct"] = hmac.compare_digest(str(st.session_state.get("password", "")), str(senha))
        st.session_state.pop("password", None)
    if st.session_state.get("password_correct"): return True
    st.text_input("Digite a senha:", type="password", on_change=password_entered, key="password")
    if st.session_state.get("password_correct") is False: st.error("Senha incorreta.")
    return False

def baixar_formulario(uid, token, base_url):
    if not uid: return []
    url = f"{base_url}/api/v2/assets/{uid}/data/"
    headers = {"Authorization": f"Token {token}"}
    params, registros = {"format": "json"}, []
    while url:
        r = requests.get(url, headers=headers, params=params, timeout=60); r.raise_for_status()
        p = r.json(); registros.extend(p.get("results", [])); url = p.get("next"); params = {}
    return registros

def normalizar_texto(v):
    if v is None: return ""
    t = unicodedata.normalize("NFKD", str(v))
    return " ".join("".join(c for c in t if not unicodedata.combining(c)).lower().replace("_", " ").strip().split())

def numero_inteiro(v):
    try: return max(0, int(float(str(v).strip().replace(",", ".")))) if v and str(v).strip() else 0
    except: return 0

def normalizar_codigo(v): return re.sub(r"\s+", "", str(v)).upper().replace("–", "-").replace("—", "-")
def para_numero(s): return pd.to_numeric(s.astype(str).str.replace(",", ".", regex=False), errors="coerce")
def pct(num, den): return (num / den.where(den > 0) * 100).round(1)

def locais_positivos_por_criterio(df_lab, df_amostras):
    out = {}
    for nome, fn in CRITERIOS.items():
        if df_lab.empty: out[nome] = 0; continue
        mask = df_lab["especie"].apply(fn).astype(bool)
        out[nome] = int(df_amostras.loc[df_amostras["codigo_amostra"].isin(df_lab.loc[mask, "codigo_amostra"].unique()), "id_local"].nunique())
    return out

@st.cache_data(ttl=3600, show_spinner=False)
def obter_clima(lat, lon, data_visita):
    if pd.isna(lat) or pd.isna(lon) or pd.isna(data_visita): return None, None, None
    try:
        data_str = pd.to_datetime(data_visita).strftime('%Y-%m-%d')
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={data_str}&end_date={data_str}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=America%2FSao_Paulo"
        resposta = requests.get(url, timeout=10); dados = resposta.json()
        return dados["daily"]["temperature_2m_max"][0], dados["daily"]["temperature_2m_min"][0], dados["daily"]["precipitation_sum"][0]
    except: return None, None, None

ARQUIVO_SINAN = Path(__file__).parent / "coordenadas_sinan.csv"

@st.cache_data(ttl=300, show_spinner=False)
def carregar_sinan(caminho=ARQUIVO_SINAN):
    try:
        df = pd.read_csv(caminho, sep=None, engine="python", encoding="utf-8-sig", dtype=str)
        df.columns = [str(c).strip().lower() for c in df.columns]
        col_lat = next(c for c in df.columns if c.startswith("lat")); col_lon = next(c for c in df.columns if c.startswith("lon"))
        out = pd.DataFrame({"lat": pd.to_numeric(df[col_lat].str.replace(",", ".", regex=False), errors="coerce"), "lon": pd.to_numeric(df[col_lon].str.replace(",", ".", regex=False), errors="coerce")}).dropna()
        return out[out["lat"].between(-90, 90) & out["lon"].between(-180, 180)].reset_index(drop=True)
    except: return pd.DataFrame(columns=["lat", "lon"])

def mapa_sinan(df_sinan, df_locais_mapa=None, calor=False, mostrar_locais=False):
    m = folium.Map(location=[df_sinan["lat"].mean(), df_sinan["lon"].mean()], zoom_start=13, tiles="OpenStreetMap")
    if calor: HeatMap(df_sinan[["lat", "lon"]].values.tolist(), radius=25, blur=18).add_to(m)
    else:
        for i, r in df_sinan.iterrows():
            folium.CircleMarker([r["lat"], r["lon"]], radius=6, color="#7B1FA2", weight=2, fill=True, fill_color="#9C27B0", fill_opacity=0.7, tooltip=f"Notificação {i + 1}").add_to(m)
    if mostrar_locais and df_locais_mapa is not None and not df_locais_mapa.empty:
        for _, r in df_locais_mapa.iterrows():
            folium.CircleMarker([r["lat"], r["lon"]], radius=4, color=STATUS_CORES.get(r["status"], "#9E9E9E"), fill=True, fill_opacity=0.9, tooltip=f"{r['id_local']} — {r['status']}").add_to(m)
    m.fit_bounds([[df_sinan["lat"].min(), df_sinan["lon"].min()], [df_sinan["lat"].max(), df_sinan["lon"].max()]])
    return m

def render_sinan(df_locais_mapa):
    df_sinan = carregar_sinan()
    if df_sinan.empty: st.info("coordenadas_sinan.csv não encontrado."); return
    c1, c2, c3 = st.columns(3)
    c1.metric("Notificações com coordenada", len(df_sinan))
    calor = c2.checkbox("Mapa de calor", key="sinan_calor")
    locais = c3.checkbox("Mostrar locais", key="sinan_locais")
    st_folium(mapa_sinan(df_sinan, df_locais_mapa, calor, locais), width=None, height=450, key="mapa_sinan", returned_objects=[])

if not check_password(): st.stop()

@st.fragment(run_every=300)
def auto_refresh():
    st.cache_data.clear(); st.rerun()
auto_refresh()

if st.sidebar.button("🔄 Atualizar dados agora"):
    st.cache_data.clear(); st.rerun()

st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption(f"Pesquisador: Flávio Santos (IOC - Fiocruz) | Atualizado em: {AGORA.strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")

with st.spinner("Baixando dados do Kobo..."):
    try:
        c = baixar_formulario(_get_secret("UID_CAMPO"), _get_secret("KOBO_TOKEN"), _get_secret("KOBO_URL", "https://kf.kobotoolbox.org"))
        v = baixar_formulario(_get_secret("UID_VISITA"), _get_secret("KOBO_TOKEN"), _get_secret("KOBO_URL", "https://kf.kobotoolbox.org"))
        l = baixar_formulario(_get_secret("UID_LAB"), _get_secret("KOBO_TOKEN"), _get_secret("KOBO_URL", "https://kf.kobotoolbox.org"))
    except Exception as e: st.error(f"Falha no Kobo: {e}"); st.stop()

if not c: st.warning("Nenhum dado."); st.stop()

# --- PROCESSAMENTO COMPACTO ---
locais, vis_l, ams = [], [], []
for i, item in enumerate(c):
    id_l = normalizar_codigo(item.get("grp_cadastro/id_local_calc") or "") or f"SEM-{i}"
    geo = item.get("grp_cadastro/geolocalizacao", ""); lat, lon = (float(geo.split()[0]), float(geo.split()[1])) if isinstance(geo, str) and " " in geo else (None, None)
    locais.append({"id_local": id_l, "bairro": item.get("grp_cadastro/bairro") or "N/I", "tipologia": item.get("grp_cadastro/tipologia_imovel") or "N/I", "lat": lat, "lon": lon})
    for n, vis in enumerate(item.get("rep_visitas", []) if isinstance(item.get("rep_visitas"), list) else []):
        id_v = f"{i}-{n}"; d = vis.get("rep_visitas/data_visita")
        vis_l.append({"id_visita": id_v, "id_local": id_l, "data_visita": d, "n_exam": vis.get("rep_visitas/qtd_bromelias_examinadas"), "n_secas": vis.get("rep_visitas/qtd_secas"), "n_agua_sem": vis.get("rep_visitas/qtd_agua_sem_imaturos")})
        for a in vis.get("rep_visitas/rep_amostras", []):
            cod = a.get("rep_visitas/rep_amostras/codigo_amostra")
            if cod: ams.append({"id_visita": id_v, "id_local": id_l, "codigo_amostra": normalizar_codigo(cod), "data_visita": d, "ph": a.get("rep_visitas/rep_amostras/ph_agua"), "temp": a.get("rep_visitas/rep_amostras/temp_agua_c"), "vol": a.get("rep_visitas/rep_amostras/volume_agua_ml"), "genero": a.get("rep_visitas/rep_amostras/genero") or "N/I", "porte": a.get("rep_visitas/rep_amostras/porte") or "N/I"})

locais_v = {}
for i, item in enumerate(v):
    id_l = normalizar_codigo(item.get("grp_identificacao/id_bromelia_visita") or "")
    if not id_l: continue
    id_v = f"V{i}"; d = item.get("grp_dados_visita/data_visita")
    vis_l.append({"id_visita": id_v, "id_local": id_l, "data_visita": d, "n_exam": item.get("grp_dados_visita/qtd_bromelias_examinadas"), "n_secas": item.get("grp_dados_visita/qtd_secas"), "n_agua_sem": item.get("grp_dados_visita/qtd_agua_sem_imaturos")})
    try: lat, lon = float(item.get("grp_identificacao/latitude")), float(item.get("grp_identificacao/longitude"))
    except: lat, lon = None, None
    locais_v.setdefault(id_l, {"bairro": item.get("grp_identificacao/bairro") or "N/I", "lat": lat, "lon": lon})
    for a in item.get("rep_amostras") or []:
        cod = a.get("rep_amostras/codigo_amostra")
        if cod: ams.append({"id_visita": id_v, "id_local": id_l, "codigo_amostra": normalizar_codigo(cod), "data_visita": d, "ph": a.get("rep_amostras/ph_agua"), "temp": a.get("rep_amostras/temp_agua_c"), "vol": a.get("rep_amostras/volume_agua_ml"), "genero": a.get("rep_amostras/genero") or "N/I", "porte": a.get("rep_amostras/porte") or "N/I"})

df_l = pd.DataFrame(locais, columns=["id_local", "bairro", "tipologia", "lat", "lon"])
c_sem = sorted(set(locais_v) - set(df_l["id_local"]))
if c_sem: df_l = pd.concat([df_l, pd.DataFrame([{"id_local": x, "bairro": locais_v[x]["bairro"], "tipologia": "N/I", "lat": locais_v[x]["lat"], "lon": locais_v[x]["lon"]} for x in c_sem])], ignore_index=True)

ids_dup = sorted(df_l.loc[df_l["id_local"].duplicated(), "id_local"].unique())
df_am_bruto = pd.DataFrame(ams, columns=["id_visita", "id_local", "codigo_amostra", "data_visita", "ph", "temp", "vol", "genero", "porte"])
cods_dup = sorted(df_am_bruto.loc[df_am_bruto["codigo_amostra"].duplicated(), "codigo_amostra"].unique())

df_l = df_l.drop_duplicates("id_local")
df_am = df_am_bruto.drop_duplicates("codigo_amostra")
df_v = pd.DataFrame(vis_l, columns=["id_visita", "id_local", "data_visita", "n_exam", "n_secas", "n_agua_sem"])

for col in ["n_exam", "n_secas", "n_agua_sem"]: df_v[col] = df_v[col].apply(numero_inteiro).astype(int)
df_v["n_com"] = (df_v["n_exam"] - df_v["n_secas"] - df_v["n_agua_sem"]).clip(lower=0)
df_v["data_visita"] = pd.to_datetime(df_v["data_visita"], errors="coerce")
df_am["data_visita"] = pd.to_datetime(df_am["data_visita"], errors="coerce")
for col in ["ph", "temp", "vol"]: df_am[col] = para_numero(df_am[col])

# --- NOVO: Buscando dados climáticos automáticos ---
with st.spinner("Buscando histórico do clima (Open-Meteo)..."):
    df_vis_clima = df_v.merge(df_l[["id_local", "lat", "lon"]], on="id_local", how="left")
    climas = df_vis_clima.apply(lambda row: obter_clima(row.get("lat"), row.get("lon"), row.get("data_visita")), axis=1)
    df_v[["temp_max", "temp_min", "chuva_mm"]] = pd.DataFrame(climas.tolist(), index=df_v.index)

lab_dic, cods_lab_dup = {}, set()
for item in sorted(l, key=lambda x: x.get("_submission_time") or ""):
    cod = normalizar_codigo(item.get("grp_amostra/codigo_amostra", ""))
    if not cod: continue
    if cod in lab_dic: cods_lab_dup.add(cod)
    lab_dic[cod] = item

lab_esp, res_lab = [], {}
for cod, item in lab_dic.items():
    res_l = []
    for e in item.get("rep_especies", []):
        q = numero_inteiro(e.get("rep_especies/qtd_larvas")) + numero_inteiro(e.get("rep_especies/qtd_pupas")) + numero_inteiro(e.get("rep_especies/qtd_adultos"))
        r = normalizar_texto(e.get("rep_especies/resultado_amostra"))
        if r: res_l.append(r)
        lab_esp.append({"codigo_amostra": cod, "especie": normalizar_texto(e.get("rep_especies/especie_identificada") or "nao_identificado").replace(" ", "_"), "qtd_especimes": q})
    res_lab[cod] = normalizar_texto(item.get("grp_resultado/resultado_amostra")) or ("inconclusivo" if "inconclusivo" in res_l else "positivo" if "positivo" in res_l else "negativo")

df_lab = pd.DataFrame(lab_esp, columns=["codigo_amostra", "especie", "qtd_especimes"])
cods_lab = set(lab_dic)
cods_orf = sorted(cods_lab - set(df_am["codigo_amostra"]))
df_am_tod, df_v_tod, df_l_tod = df_am.copy(), df_v.copy(), df_l.copy()

# --- FILTROS E CRUZAMENTO ---
st.sidebar.header("🦟 Critério de positividade")
crit_nome = st.sidebar.selectbox("Espécie-alvo", list(CRITERIOS), index=0)
crit_fn = CRITERIOS[crit_nome]
st.sidebar.markdown("---")
st.sidebar.header("🔎 Filtro de Data")
dts = df_v["data_visita"].dropna()
if not dts.empty:
    per = st.sidebar.date_input("Período", value=(dts.min().date(), dts.max().date()), min_value=dts.min().date(), max_value=dts.max().date())
    if len(per) == 2:
        i, f = pd.Timestamp(per[0]), pd.Timestamp(per[1]) + pd.Timedelta(days=1)
        df_v = df_v[(df_v["data_visita"] >= i) & (df_v["data_visita"] < f)]
        df_am = df_am[(df_am["data_visita"] >= i) & (df_am["data_visita"] < f)]
        df_l = df_l[df_l["id_local"].isin(df_v["id_local"].unique())]

if df_l.empty: st.warning("Sem dados no período."); st.stop()
df_lab = df_lab[df_lab["codigo_amostra"].isin(df_am["codigo_amostra"])]

if not df_lab.empty:
    df_lab["alvo"] = df_lab["especie"].apply(crit_fn); df_lab["qtd_alvo"] = df_lab["qtd_especimes"].where(df_lab["alvo"], 0)
    df_res = df_lab.groupby("codigo_amostra").agg(qtd_total=("qtd_especimes", "sum"), qtd_alvo=("qtd_alvo", "sum"), positiva=("alvo", "any")).reset_index()
else: df_res = pd.DataFrame(columns=["codigo_amostra", "qtd_total", "qtd_alvo", "positiva"])

df_am = df_am.merge(df_res, on="codigo_amostra", how="left")
df_am["positiva"] = df_am["positiva"].eq(True)
df_am["analisada"] = df_am["codigo_amostra"].isin(cods_lab)
df_am["pendente"] = ~df_am["analisada"]
df_am["qtd_total"] = df_am["qtd_total"].fillna(0); df_am["qtd_alvo"] = df_am["qtd_alvo"].fillna(0)

df_vl = df_v.groupby("id_local").agg(visitas=("id_visita", "count"), n_exam=("n_exam", "sum"), n_com=("n_com", "sum"), n_agua_sem=("n_agua_sem", "sum")).reset_index()
df_al = df_am.groupby("id_local").agg(positivas=("positiva", "sum"), pendentes=("pendente", "sum"), qtd_total=("qtd_total", "sum")).reset_index() if not df_am.empty else pd.DataFrame(columns=["id_local", "positivas", "pendentes", "qtd_total"])

df_f = df_l.merge(df_vl, on="id_local", how="left").merge(df_al, on="id_local", how="left").fillna(0)
df_f["positivo"] = df_f["positivas"] > 0
df_f["resolvido"] = df_f["positivo"] | (df_f["pendentes"] == 0)
df_f["status"] = "Sem análise"; df_f.loc[df_f["resolvido"], "status"] = "Negativo"; df_f.loc[df_f["positivo"], "status"] = "Positivo"

n_loc, n_res, n_pos = len(df_f), int(df_f["resolvido"].sum()), int(df_f["positivo"].sum())
pos = (n_pos / n_res * 100) if n_res else 0
n_exam, n_com = int(df_f["n_exam"].sum()), int(df_f["n_com"].sum())
b_pos = int(df_am["positiva"].sum()); b_base = n_exam - int(df_am["pendente"].sum())
pos_b = (b_pos / b_base * 100) if b_base > 0 else 0

df_rk = df_f.groupby("bairro").agg(Com=("resolvido", "sum"), Pos=("positivo", "sum")).reset_index()
df_rk["%"] = pct(df_rk["Pos"], df_rk["Com"])
b_alert = "Nenhum"
if not df_rk.empty:
    t = df_rk[df_rk["%"] > 0].sort_values("%", ascending=False)
    if not t.empty: b_alert = f"{t.iloc[0]['bairro'].capitalize()}"

if n_res == 0: niv, bg, cor, ico, msg = "SEM DADOS", "#EEEEEE", "#666666", "ℹ️", "Sem resultados."
elif pos < RISCO_MEDIO: niv, bg, cor, ico, msg = "BAIXO", "#D6EAF8", "#2E86AB", "✅", "Risco Baixo."
elif pos < RISCO_ALTO: niv, bg, cor, ico, msg = "MÉDIO", "#FDEBD0", "#F4A261", "⚠️", f"Atenção ao bairro {b_alert}."
else: niv, bg, cor, ico, msg = "ALTO", "#FADBD8", "#E63946", "🚨", f"Ação urgente em {b_alert}."

# --- INTERFACE ---
st.markdown("### 📊 Painel Executivo")
c1, c2 = st.columns([3, 2])
with c1:
    a1, a2, a3 = st.columns(3); a1.metric("Locais", n_loc); a2.metric("Bromélias examinadas", n_exam); a3.metric("Com imaturos", n_com)
    b1, b2, b3 = st.columns(3); b1.metric("Positivas", b_pos); b2.metric("Positividade", f"{pos_b:.1f}%"); b3.metric("Locais positivos", f"{n_pos}/{n_res}")
with c2: st.markdown(f'<div style="background-color: {bg}; padding: 15px; border-radius: 10px; border-left: 5px solid {cor}; height: 100%;"><h4 style="color: {cor}; margin-top: 0;">{ico} Status: {niv}</h4><p style="color: #333; margin-bottom: 0; font-size: 14px;">{msg}</p></div>', unsafe_allow_html=True)
st.markdown("---")

# 2. MÉDIAS DA ÁGUA E CLIMA
st.markdown("### 💧 Médias da Água (bromélias com imaturos)")
if not df_am.empty:
    m1, m2, m3 = st.columns(3)
    m1.metric("pH Médio", f"{df_am['ph'].mean():.1f}" if df_am["ph"].notna().any() else "—")
    m2.metric("Temperatura da Água", f"{df_am['temp'].mean():.1f} °C" if df_am["temp"].notna().any() else "—")
    m3.metric("Volume Médio", f"{df_am['vol'].mean():.0f} mL" if df_am["vol"].notna().any() else "—")

st.markdown("**Condições Climáticas (Open-Meteo)**")
c1, c2, c3 = st.columns(3)
c1.metric("Temp. Máxima", f"{df_v['temp_max'].mean():.1f} °C" if df_v['temp_max'].notna().any() else "—")
c2.metric("Temp. Mínima", f"{df_v['temp_min'].mean():.1f} °C" if df_v['temp_min'].notna().any() else "—")
c3.metric("Chuva Acumulada", f"{df_v['chuva_mm'].sum():.1f} mm" if df_v['chuva_mm'].notna().any() else "—")
st.markdown("---")

st.markdown("### ⏳ Amostras Pendentes")
if not df_am.empty:
    df_p = df_am[df_am["pendente"]].copy()
    if not df_p.empty:
        df_p["Dias"] = (HOJE - df_p["data_visita"]).dt.days
        st.dataframe(df_p[["codigo_amostra", "id_local", "data_visita", "Dias"]].rename(columns={"codigo_amostra": "Código", "id_local": "Local", "data_visita": "Data"}), hide_index=True)
    else: st.success("🎉 Todas analisadas!")
else: st.info("Sem amostras.")
st.markdown("---")

st.markdown("### 🗺️ Mapas de Risco")
df_m = df_f.dropna(subset=["lat", "lon"])
if not df_m.empty:
    clat, clon = df_m["lat"].mean(), df_m["lon"].mean()
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📍 Base", "🔥 Calor", "🌐 Locais", "🏘️ Bairros", "🦠 SINAN"])

    with tab1:
        col_m, col_t = st.columns([3, 1])
        with col_m:
            m1 = folium.Map(location=[clat, clon], zoom_start=16, tiles="OpenStreetMap")
            for _, r in df_m.iterrows():
                folium.Marker([r["lat"], r["lon"]], icon=folium.Icon(color=STATUS_ICONES[r["status"]]), popup=r["id_local"]).add_to(m1)
            st_folium(m1, width=None, height=450, key="m1")
        with col_t:
            fig = go.Figure(go.Indicator(mode="gauge+number", value=pos, number={"suffix": "%"}, title={"text": niv}, gauge={"axis": {"range": [0, 100]}, "bar": {"color": cor}}))
            fig.update_layout(height=350, margin=dict(l=10, r=10, t=50, b=10)); st.plotly_chart(fig, use_container_width=True)

    with tab2:
        df_c = df_m[df_m["positivo"]]
        if not df_c.empty:
            fig = px.density_mapbox(df_c, lat="lat", lon="lon", z="qtd_alvo", radius=50, center=dict(lat=clat, lon=clon), zoom=13, mapbox_style="open-street-map", color_continuous_scale="Inferno")
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=450, coloraxis_showscale=False); st.plotly_chart(fig, use_container_width=True)
        else: st.info("Nenhum positivo.")

    with tab3:
        fig = px.scatter_mapbox(df_m.assign(t=df_m["n_exam"].clip(lower=1)), lat="lat", lon="lon", size="t", color="status", color_discrete_map=STATUS_CORES, center=dict(lat=clat, lon=clon), zoom=14, mapbox_style="open-street-map")
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=450); st.plotly_chart(fig, use_container_width=True)

    with tab4:
        df_b = df_m.groupby("bairro").agg(lat=("lat", "mean"), lon=("lon", "mean"), locais=("id_local", "count"), com_res=("resolvido", "sum"), pos=("positivo", "sum")).reset_index()
        df_b["%"] = pct(df_b["pos"], df_b["com_res"]).fillna(0)
        fig = px.scatter_mapbox(df_b, lat="lat", lon="lon", size="locais", color="%", color_continuous_scale=["#2E86AB", "#F4A261", "#E63946"], hover_name="bairro", center=dict(lat=clat, lon=clon), zoom=13, mapbox_style="open-street-map")
        fig.update_layout(height=450, margin=dict(l=0, r=0, t=0, b=0)); st.plotly_chart(fig, use_container_width=True)

    with tab5:
        render_sinan(df_m)

# GRÁFICOS FINAIS (Sazonalidade, Espécies, etc) - Mantidos de forma compacta
st.markdown("---")
st.markdown("### 📈 Série Temporal de Coletas")
df_s = df_v.dropna(subset=["data_visita"]).copy()
if not df_s.empty:
    df_s["mes"] = df_s["data_visita"].dt.to_period("M").astype(str)
    c = df_s.groupby("mes").agg(visitas=("id_visita", "count"), bromelias=("n_exam", "sum")).reset_index()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=c["mes"], y=c["visitas"], name="Visitas", marker_color="#2E86AB"))
    fig.add_trace(go.Bar(x=c["mes"], y=c["bromelias"], name="Bromélias", marker_color="#7BC8A4"))
    fig.update_layout(barmode="group", height=350); st.plotly_chart(fig, use_container_width=True)