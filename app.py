# -*- coding: utf-8 -*-
import difflib, hmac, os, re, unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
import folium, pandas as pd, plotly.express as px, plotly.graph_objects as go, requests, streamlit as st
from streamlit_folium import st_folium

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

# --- CSS E TEMA (DATA-DENSE DASHBOARD) ---
DARK_MODE = st.sidebar.toggle("🌙 Modo escuro", value=False)

if DARK_MODE:
    T = {"bg": "#111827", "surface": "#1F2937", "text": "#F9FAFB", "muted": "#9CA3AF", "border": "#374151", "pri": "#22C55E", "warn": "#F59E0B", "dang": "#EF4444", "tpl": "plotly_dark", "tiles": "CartoDB dark_matter"}
else:
    T = {"bg": "#F5F5F5", "surface": "#FFFFFF", "text": "#333333", "muted": "#6B7280", "border": "#E5E7EB", "pri": "#22C55E", "warn": "#F59E0B", "dang": "#EF4444", "tpl": "plotly_white", "tiles": "CartoDB positron"}

STATUS_CORES = {"Positivo": T["dang"], "Negativo": T["pri"], "Sem análise": T["muted"]}
STATUS_ICONES = {"Positivo": "red", "Negativo": "green", "Sem análise": "gray"}

st.markdown(f"""<style>
:root {{ --bg: {T['bg']}; --surface: {T['surface']}; --text: {T['text']}; --muted: {T['muted']}; --border: {T['border']}; --pri: {T['pri']}; --warn: {T['warn']}; --dang: {T['dang']}; }}
.stApp {{ background-color: var(--bg); color: var(--text); }}
h1, h2, h3, h4, p, span, div, label {{ color: var(--text); font-family: -apple-system, sans-serif; }}
section[data-testid="stSidebar"] {{ background-color: var(--surface); border-right: 1px solid var(--border); }}
div[data-testid="stMetric"] {{ background-color: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
div[data-testid="stMetricLabel"] {{ color: var(--muted); }}
div[data-testid="stDataFrame"] {{ border: 1px solid var(--border); border-radius: 8px; }}
.card {{ padding: 16px; border-radius: 8px; border-left: 5px solid; background: var(--surface); box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
.card h4 {{ margin: 0 0 8px 0; }}
.card.baixo {{ border-left-color: var(--pri); }} .card.baixo h4 {{ color: var(--pri); }}
.card.medio {{ border-left-color: var(--warn); }} .card.medio h4 {{ color: var(--warn); }}
.card.alto {{ border-left-color: var(--dang); }} .card.alto h4 {{ color: var(--dang); }}
.card.sem-dados {{ border-left-color: var(--muted); }} .card.sem-dados h4 {{ color: var(--muted); }}
</style>""", unsafe_allow_html=True)

def layout_fig(fig, h=350, m=None):
    fig.update_layout(template=T["tpl"], paper_bgcolor=T["bg"], plot_bgcolor=T["surface"], font_color=T["text"], height=h, margin=m or dict(l=10, r=10, t=30, b=10))
    return fig

def pct(num, den): return (num / den.where(den > 0) * 100).round(1)

# --- HELPERS ---
def get_sec(k): return st.secrets.get(k, os.environ.get(k, ""))
def norm_txt(v): return "".join(c for c in unicodedata.normalize("NFKD", str(v)) if not unicodedata.combining(c)).lower().replace("_", " ").strip()
def norm_cod(v): return re.sub(r"\s+", "", str(v)).upper().replace("–", "-")
def num_int(v): 
    try: return max(0, int(float(str(v).replace(",", ".")))) if v else 0
    except: return 0
def to_num(s): return pd.to_numeric(s.astype(str).str.replace(",", ".", regex=False), errors="coerce")

@st.cache_data(ttl=300, show_spinner=False)
def fetch_data(uid, token, url):
    if not uid: return []
    headers = {"Authorization": f"Token {token}"}; res = []; nxt = f"{url}/api/v2/assets/{uid}/data/"
    while nxt:
        r = requests.get(nxt, headers=headers, params={"format": "json"}, timeout=60); r.raise_for_status()
        data = r.json(); res.extend(data.get("results", [])); nxt = data.get("next")
    return res

def check_auth():
    pwd = get_sec("SENHA_ACESSO")
    if not pwd: st.error("Senha não configurada."); return False
    if st.session_state.get("auth"): return True
    def cb(): st.session_state["auth"] = hmac.compare_digest(str(st.session_state.get("p", "")), str(pwd)); st.session_state.pop("p", None)
    st.text_input("Senha:", type="password", on_change=cb, key="p")
    return st.session_state.get("auth", False)

if not check_auth(): st.stop()

# --- AUTO REFRESH NATIVO ---
@st.fragment(run_every=300)
def auto_refresh():
    st.cache_data.clear(); st.rerun()
auto_refresh()

if st.sidebar.button("🔄 Atualizar dados agora"): st.cache_data.clear(); st.rerun()

st.title("Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption(f"Pesquisador: Flávio Santos (IOC - Fiocruz) | Atualizado em: {AGORA.strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")

# --- CARREGAMENTO ---
base, token = get_sec("KOBO_URL") or "https://kf.kobotoolbox.org", get_sec("KOBO_TOKEN")
with st.spinner("Processando dados..."):
    try:
        c, v, l = fetch_data(get_sec("UID_CAMPO"), token, base), fetch_data(get_sec("UID_VISITA"), token, base), fetch_data(get_sec("UID_LAB"), token, base)
    except Exception as e: st.error(f"Erro Kobo: {e}"); st.stop()

if not c: st.warning("Sem dados."); st.stop()

# --- PROCESSAMENTO ---
locais, visitas, amostras = [], [], []
for i, item in enumerate(c):
    id_l = norm_cod(item.get("grp_cadastro/id_local_calc") or "") or f"SEM-{i}"
    geo = item.get("grp_cadastro/geolocalizacao", ""); lat, lon = None, None
    if isinstance(geo, str) and " " in geo:
        try: lat, lon = float(geo.split()[0]), float(geo.split()[1])
        except: pass
    locais.append({"id_local": id_l, "bairro": item.get("grp_cadastro/bairro") or "N/I", "tipologia": item.get("grp_cadastro/tipologia_imovel") or "N/I", "lat": lat, "lon": lon})
    for n, vis in enumerate(item.get("rep_visitas", []) if isinstance(item.get("rep_visitas"), list) else []):
        id_v = f"{i}-{n}"; dt = vis.get("rep_visitas/data_visita")
        visitas.append({"id_visita": id_v, "id_local": id_l, "data_visita": dt, "n_exam": vis.get("rep_visitas/qtd_bromelias_examinadas"), "n_secas": vis.get("rep_visitas/qtd_secas"), "n_agua_sem": vis.get("rep_visitas/qtd_agua_sem_imaturos")})
        for a in (vis.get("rep_visitas/rep_amostras", []) if isinstance(vis.get("rep_visitas/rep_amostras"), list) else []):
            cod = a.get("rep_visitas/rep_amostras/codigo_amostra")
            if cod: amostras.append({"id_visita": id_v, "id_local": id_l, "codigo_amostra": norm_cod(cod), "data_visita": dt, "ph": a.get("rep_visitas/rep_amostras/ph_agua"), "temp": a.get("rep_visitas/rep_amostras/temp_agua_c"), "vol": a.get("rep_visitas/rep_amostras/volume_agua_ml"), "genero": a.get("rep_visitas/rep_amostras/genero") or "N/I", "porte": a.get("rep_visitas/rep_amostras/porte") or "N/I"})

locais_v = {}
for i, item in enumerate(v):
    id_l = norm_cod(item.get("grp_identificacao/id_bromelia_visita") or "")
    if not id_l: continue
    id_v = f"V{i}"; dt = item.get("grp_dados_visita/data_visita")
    visitas.append({"id_visita": id_v, "id_local": id_l, "data_visita": dt, "n_exam": item.get("grp_dados_visita/qtd_bromelias_examinadas"), "n_secas": item.get("grp_dados_visita/qtd_secas"), "n_agua_sem": item.get("grp_dados_visita/qtd_agua_sem_imaturos")})
    try: lat, lon = float(item.get("grp_identificacao/latitude")), float(item.get("grp_identificacao/longitude"))
    except: lat, lon = None, None
    locais_v.setdefault(id_l, {"bairro": item.get("grp_identificacao/bairro") or "N/I", "lat": lat, "lon": lon})
    for a in item.get("rep_amostras") or []:
        cod = a.get("rep_amostras/codigo_amostra")
        if cod: amostras.append({"id_visita": id_v, "id_local": id_l, "codigo_amostra": norm_cod(cod), "data_visita": dt, "ph": a.get("rep_amostras/ph_agua"), "temp": a.get("rep_amostras/temp_agua_c"), "vol": a.get("rep_amostras/volume_agua_ml"), "genero": a.get("rep_amostras/genero") or "N/I", "porte": a.get("rep_amostras/porte") or "N/I"})

df_loc = pd.DataFrame(locais).drop_duplicates("id_local")
df_am = pd.DataFrame(amostras).drop_duplicates("codigo_amostra") if amostras else pd.DataFrame(columns=["id_visita", "id_local", "codigo_amostra", "data_visita", "ph", "temp", "vol", "genero", "porte"])
df_vis = pd.DataFrame(visitas)

for col in ["n_exam", "n_secas", "n_agua_sem"]: df_vis[col] = df_vis[col].apply(num_int) if col in df_vis else 0
df_vis["n_com"] = (df_vis["n_exam"] - df_vis["n_secas"] - df_vis["n_agua_sem"]).clip(lower=0)
for col in ["data_visita"]:
    df_vis[col] = pd.to_datetime(df_vis[col], errors="coerce"); df_am[col] = pd.to_datetime(df_am[col], errors="coerce")
for col in ["ph", "temp", "vol"]: df_am[col] = to_num(df_am[col])

lab_dic, lab_esp = {}, []
for item in sorted(l, key=lambda x: x.get("_submission_time") or ""):
    cod = norm_cod(item.get("grp_amostra/codigo_amostra", ""))
    if not cod: continue
    lab_dic[cod] = item
    for e in (item.get("rep_especies") or []):
        qtd = num_int(e.get("rep_especies/qtd_larvas")) + num_int(e.get("rep_especies/qtd_pupas")) + num_int(e.get("rep_especies/qtd_adultos"))
        lab_esp.append({"codigo_amostra": cod, "especie": norm_txt(e.get("rep_especies/especie_identificada") or "nao_identificado").replace(" ", "_"), "qtd_especimes": qtd})

df_lab = pd.DataFrame(lab_esp) if lab_esp else pd.DataFrame(columns=["codigo_amostra", "especie", "qtd_especimes"])

# --- FILTROS ---
st.sidebar.markdown("---")
crit_nome = st.sidebar.selectbox("🦟 Espécie-alvo", list(CRITERIOS), index=0)
crit_fn = CRITERIOS[crit_nome]
st.sidebar.markdown("---")
dts = df_vis["data_visita"].dropna()
if not dts.empty:
    per = st.sidebar.date_input("🔎 Período", value=(dts.min().date(), dts.max().date()), min_value=dts.min().date(), max_value=dts.max().date())
    if len(per) == 2:
        i, f = pd.Timestamp(per[0]), pd.Timestamp(per[1]) + pd.Timedelta(days=1)
        df_vis = df_vis[(df_vis["data_visita"] >= i) & (df_vis["data_visita"] < f)]
        df_am = df_am[(df_am["data_visita"] >= i) & (df_am["data_visita"] < f)]
        df_loc = df_loc[df_loc["id_local"].isin(df_vis["id_local"].unique())]

if df_loc.empty: st.warning("Sem dados no período."); st.stop()
df_lab = df_lab[df_lab["codigo_amostra"].isin(df_am["codigo_amostra"])]

# --- CRUZAMENTO ---
if not df_lab.empty:
    df_lab["alvo"] = df_lab["especie"].apply(crit_fn); df_lab["qtd_alvo"] = df_lab["qtd_especimes"].where(df_lab["alvo"], 0)
    df_res = df_lab.groupby("codigo_amostra").agg(qtd_total=("qtd_especimes", "sum"), qtd_alvo=("qtd_alvo", "sum"), positiva=("alvo", "any")).reset_index()
else: df_res = pd.DataFrame(columns=["codigo_amostra", "qtd_total", "qtd_alvo", "positiva"])

df_am = df_am.merge(df_res, on="codigo_amostra", how="left")
df_am["positiva"] = df_am["positiva"].eq(True)
df_am["analisada"] = df_am["codigo_amostra"].isin(lab_dic.keys())
df_am["pendente"] = ~df_am["analisada"]
df_am["qtd_total"] = df_am["qtd_total"].fillna(0); df_am["qtd_alvo"] = df_am["qtd_alvo"].fillna(0)

df_vl = df_vis.groupby("id_local").agg(visitas=("id_visita", "count"), n_exam=("n_exam", "sum"), n_com=("n_com", "sum"), n_agua_sem=("n_agua_sem", "sum")).reset_index()
df_al = df_am.groupby("id_local").agg(positivas=("positiva", "sum"), pendentes=("pendente", "sum"), qtd_total=("qtd_total", "sum")).reset_index() if not df_am.empty else pd.DataFrame(columns=["id_local", "positivas", "pendentes", "qtd_total"])

df_f = df_loc.merge(df_vl, on="id_local", how="left").merge(df_al, on="id_local", how="left").fillna(0)
df_f["positivo"] = df_f["positivas"] > 0
df_f["resolvido"] = df_f["positivo"] | (df_f["pendentes"] == 0)
df_f["status"] = "Sem análise"; df_f.loc[df_f["resolvido"], "status"] = "Negativo"; df_f.loc[df_f["positivo"], "status"] = "Positivo"

# --- KPIs ---
n_loc, n_res, n_pos = len(df_f), int(df_f["resolvido"].sum()), int(df_f["positivo"].sum())
pos = (n_pos / n_res * 100) if n_res else 0
n_exam, n_com = int(df_f["n_exam"].sum()), int(df_f["n_com"].sum())
b_pos = int(df_am["positiva"].sum())
b_base = n_exam - int(df_am["pendente"].sum())
pos_b = (b_pos / b_base * 100) if b_base > 0 else 0

df_rk = df_f.groupby("bairro").agg(Com=("resolvido", "sum"), Pos=("positivo", "sum")).reset_index()
df_rk["%"] = pct(df_rk["Pos"], df_rk["Com"])
bairro_al = "Nenhum"
if not df_rk.empty:
    top = df_rk[df_rk["%"] > 0].sort_values("%", ascending=False)
    if not top.empty: bairro_al = f"{top.iloc[0]['bairro'].capitalize()} ({int(top.iloc[0]['Pos'])}/{int(top.iloc[0]['Com'])})"

if n_res == 0: niv, cls, ico, msg = "SEM DADOS", "sem-dados", "ℹ️", "Sem resultados no período."
elif pos < RISCO_MEDIO: niv, cls, ico, msg = "BAIXO", "baixo", "✅", "Risco Baixo."
elif pos < RISCO_ALTO: niv, cls, ico, msg = "MÉDIO", "medio", "⚠️", f"Atenção ao bairro {bairro_al}."
else: niv, cls, ico, msg = "ALTO", "alto", "🚨", f"Ação urgente em {bairro_al}."

st.markdown("### Painel Executivo")
c1, c2 = st.columns([3, 2])
with c1:
    a1, a2, a3 = st.columns(3); a1.metric("Locais", n_loc); a2.metric("Examinadas", n_exam); a3.metric("Com imaturos", n_com)
    b1, b2, b3 = st.columns(3); b1.metric("Positivas", b_pos); b2.metric("Positividade", f"{pos_b:.1f}%"); b3.metric("Locais positivos", f"{n_pos}/{n_res}")
with c2: st.markdown(f'<div class="card {cls}"><h4>{ico} Status: {niv}</h4><p>{msg}</p></div>', unsafe_allow_html=True)
st.markdown("---")

# --- TABELAS PENDENTES ---
st.markdown("### Amostras Pendentes")
if not df_am.empty:
    df_p = df_am[df_am["pendente"]].copy()
    if not df_p.empty:
        df_p["Dias"] = (HOJE - df_p["data_visita"]).dt.days
        st.dataframe(df_p[["codigo_amostra", "id_local", "data_visita", "Dias"]].rename(columns={"codigo_amostra": "Código", "id_local": "Local", "data_visita": "Data", "Dias": "Espera (dias)"}), hide_index=True)
    else: st.success("🎉 Todas as amostras foram analisadas!")
else: st.info("Sem amostras.")
st.markdown("---")

# --- MAPAS ---
df_m = df_f.dropna(subset=["lat", "lon"])
if not df_m.empty:
    clat, clon = df_m["lat"].mean(), df_m["lon"].mean()
    t1, t2 = st.tabs(["Mapa Base", "Mapa de Calor"])
    with t1:
        c_m, c_t = st.columns([3, 1])
        with c_m:
            m = folium.Map(location=[clat, clon], zoom_start=16, tiles=T["tiles"])
            for _, r in df_m.iterrows():
                pop = f"<b>{r['id_local']}</b> - {r['status'].upper()}<br>Examinadas: {r['n_exam']}"
                folium.Marker([r["lat"], r["lon"]], icon=folium.Icon(color=STATUS_ICONES[r["status"]]), popup=folium.Popup(pop, max_width=300)).add_to(m)
            st_folium(m, width=None, height=400, key="m1")
        with c_t:
            st.markdown("#### Termômetro")
            fig = go.Figure(go.Indicator(mode="gauge+number", value=pos, number={"suffix": "%"}, title={"text": niv}, gauge={"axis": {"range": [0, 100]}, "bar": {"color": T["text"]}, "steps": [{"range": [0, RISCO_MEDIO], "color": T["pri"]}, {"range": [RISCO_MEDIO, RISCO_ALTO], "color": T["warn"]}, {"range": [RISCO_ALTO, 100], "color": T["dang"]}]}))
            layout_fig(fig, h=350); st.plotly_chart(fig, use_container_width=True, theme=None)
    with t2:
        df_c = df_m[df_m["positivo"]]
        if not df_c.empty:
            fig = px.density_mapbox(df_c, lat="lat", lon="lon", z="qtd_alvo", radius=50, center=dict(lat=clat, lon=clon), zoom=13, mapbox_style="open-street-map", color_continuous_scale="Inferno")
            layout_fig(fig, h=400, m=dict(l=0, r=0, t=0, b=0)); fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True, theme=None)
        else: st.info("Nenhum local positivo.")
st.markdown("---")

# --- GRÁFICOS FINAIS ---
col_e, col_p = st.columns(2)
with col_e:
    st.markdown("#### Frequência de Espécies")
    if not df_lab.empty:
        dfe = df_lab.groupby("especie").agg(Qtd=("qtd_especimes", "sum")).reset_index()
        dfe["especie"] = dfe["especie"].str.replace("_", " ").str.capitalize()
        fig = px.bar(dfe, x="especie", y="Qtd", text="Qtd", color="especie")
        layout_fig(fig, h=350); st.plotly_chart(fig, use_container_width=True, theme=None)
with col_p:
    st.markdown(f"#### pH ({crit_nome} vs Outros)")
    df_ph = df_am[df_am["analisada"]].dropna(subset=["ph"])
    if not df_ph.empty:
        df_ph["Resultado"] = df_ph["positiva"].map({True: "Alvo", False: "Outros"})
        fig = px.box(df_ph, x="Resultado", y="ph", points="all", color="Resultado", color_discrete_map={"Alvo": T["dang"], "Outros": T["pri"]})
        layout_fig(fig, h=350); st.plotly_chart(fig, use_container_width=True, theme=None)