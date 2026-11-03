# -*- coding: utf-8 -*-
"""Dashboard — Bromélias Ornamentais Urbanas e Culicídeos (registro por LOCAL).

Modelo: cada local (ex.: calçada) tem uma coordenada. Em cada visita registra-se quantas bromélias
foram examinadas, quantas estavam secas e quantas tinham água sem imaturos; cada bromélia COM imaturos
gera uma amostra (código, pH, temperatura, volume) que é analisada no laboratório.

Fontes (Kobo): cadastro dos locais (UID_CAMPO), visitas periódicas (UID_VISITA) e laboratório (UID_LAB).
As visitas se ligam ao cadastro pelo código do local.

Design: baseado em "Data-Dense Dashboard" (tokens de cor, tipografia do sistema, cards com borda,
sem emojis, cores semânticas verde/âmbar/vermelho). O tema base fica em .streamlit/config.toml.
"""
import difflib
import hmac
import os
import re
import unicodedata
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium

# set_page_config precisa ser o primeiro comando Streamlit
st.set_page_config(page_title="Bromélias & Culicídeos", layout="wide")

FUSO = ZoneInfo("America/Sao_Paulo")
AGORA = datetime.now(FUSO)
HOJE = pd.Timestamp(AGORA.date())
URL_FORMULARIO_LAB = "https://ee.kobotoolbox.org/AtOwQDsP"

# Faixas do alerta (% de locais positivos). Ajustar conforme definição da pesquisa.
RISCO_MEDIO = 15
RISCO_ALTO = 40
# Visita mensal: acima deste prazo (dias desde a última visita) o local aparece como atrasado
PRAZO_VISITA_DIAS = 35

# Critério de positividade: aplicado ao nome normalizado da espécie (ex.: "aedes_aegypti")
CRITERIOS = {
    "Aedes aegypti": lambda s: "aegypti" in s,
    "Aedes albopictus": lambda s: "albopictus" in s,
    "Qualquer Aedes": lambda s: "aedes" in s or "aegypti" in s or "albopictus" in s,
}

# --- DESIGN: tokens (Data-Dense Dashboard) ---
COR_TEXTO = "#333333"
COR_MUTED = "#6B7280"
COR_BORDA = "#E5E7EB"
COR_OK, COR_ALERTA, COR_ERRO = "#22C55E", "#F59E0B", "#EF4444"    # verde / âmbar / vermelho
COR_NEUTRA, COR_NEUTRA_ESCURA = "#9CA3AF", "#4B5563"
FONTE = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'

STATUS_CORES = {"Positivo": COR_ERRO, "Negativo": COR_OK, "Sem análise": COR_NEUTRA}
STATUS_ICONES = {"Positivo": "red", "Negativo": "green", "Sem análise": "gray"}
# nível de risco -> (cor do indicador, cor do texto com contraste, tom claro do fundo do termômetro)
NIVEIS = {
    "BAIXO": (COR_OK, "#15803D"), "MÉDIO": (COR_ALERTA, "#B45309"),
    "ALTO": (COR_ERRO, "#B91C1C"), "SEM DADOS": (COR_NEUTRA, COR_NEUTRA_ESCURA),
}

CSS = """
<style>
:root { --c-text:#333333; --c-muted:#6B7280; --c-border:#E5E7EB; --c-surface:#FFFFFF; }
html, body, .stApp, [data-testid="stAppViewContainer"], button, input, textarea, select {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}
.block-container { max-width: 1280px; padding: 1.5rem 1.5rem 3rem 1.5rem; }
h1, h2, h3, h4 { color: var(--c-text); letter-spacing: -0.01em; }
.app-title { display:flex; align-items:center; gap:12px; margin:0 0 4px 0; font-size:2.25rem; font-weight:700;
  line-height:1.15; color: var(--c-text); }
.app-title svg { flex:none; }
.section-title { display:flex; align-items:center; gap:8px; margin:28px 0 8px 0; padding-bottom:6px;
  border-bottom:1px solid var(--c-border); font-size:1.25rem; font-weight:700; color:var(--c-text); }
.section-title svg { flex:none; stroke: var(--c-text); }
[data-testid="stMetric"] { background: var(--c-surface); border:1px solid var(--c-border); border-radius:8px;
  padding:12px 16px; box-shadow:0 2px 12px rgba(0,0,0,0.06); }
[data-testid="stMetricLabel"] p { font-size:0.75rem; font-weight:500; letter-spacing:0.04em;
  text-transform:uppercase; color: var(--c-muted); }
[data-testid="stMetricValue"] { font-size:1.75rem; font-weight:700; color: var(--c-text); }
.card { background: var(--c-surface); border:1px solid var(--c-border); border-radius:8px; padding:12px 16px;
  box-shadow:0 2px 12px rgba(0,0,0,0.06); }
.card p { margin:0 0 6px 0; font-size:0.875rem; color: var(--c-text); line-height:1.5; }
.card p:last-child { margin-bottom:0; }
.card .muted { color: var(--c-muted); }
.status-card { height:100%; }
.status-label { font-size:0.75rem; font-weight:500; letter-spacing:0.04em; text-transform:uppercase;
  color: var(--c-muted); }
.status-value { display:flex; align-items:center; gap:8px; margin:4px 0 8px 0; font-size:1.5rem; font-weight:700; }
.dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
[data-testid="stDataFrame"] { border:1px solid var(--c-border); border-radius:8px; overflow:hidden; }
.stButton > button, .stDownloadButton > button { border-radius:8px; font-weight:600;
  transition: transform 200ms ease, box-shadow 200ms ease; }
.stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-1px);
  box-shadow:0 2px 8px rgba(0,0,0,0.08); }
[data-testid="stSidebar"] { border-right:1px solid var(--c-border); }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { font-size:0.75rem; font-weight:500;
  letter-spacing:0.04em; text-transform:uppercase; color: var(--c-muted); }
[data-testid="stTabs"] button[role="tab"] { font-weight:500; }
@media (max-width: 768px) {
  .block-container { padding: 1rem 0.75rem 2rem 0.75rem; }
  .app-title { font-size:1.6rem; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Tema dos gráficos: fonte do sistema, fundo transparente, grades discretas, sem gradientes
pio.templates["bromelias"] = go.layout.Template(layout=dict(
    font=dict(family=FONTE, color=COR_TEXTO, size=12),
    colorway=[COR_NEUTRA_ESCURA, COR_NEUTRA, COR_OK, COR_ALERTA, COR_ERRO],
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(gridcolor=COR_BORDA, linecolor="#D1D5DB", zerolinecolor=COR_BORDA),
    yaxis=dict(gridcolor=COR_BORDA, linecolor="#D1D5DB", zerolinecolor=COR_BORDA),
    margin=dict(l=8, r=8, t=32, b=8),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text=""),
))
pio.templates.default = "plotly_white+bromelias"

# Ícones (traços no estilo Lucide) usados nos títulos de seção
_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="{t}" height="{t}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{p}</svg>')
ICONES = {
    "folha": '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/>'
             '<path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
    "painel": '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/>'
              '<rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
    "agua": '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
    "relogio": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "calendario": '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "mapa": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "serie": '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/>',
    "barras": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "frasco": '<path d="M10 2v7.527a2 2 0 0 1-.211.896L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45l-5.069-10.127A2 2 0 0 1 14 9.527V2"/>'
              '<path d="M8.5 2h7"/><path d="M7 16h10"/>',
    "casa": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    "tabela": '<path d="M12 3v18"/><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18M3 15h18"/>',
    "tendencia": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/>'
                '<line x1="12" x2="12" y1="15" y2="3"/>',
}


def icone(nome, tamanho=20):
    return _SVG.format(t=tamanho, p=ICONES[nome])


def secao(titulo, nome_icone):
    st.markdown(f'<div class="section-title">{icone(nome_icone)}<span>{escape(titulo)}</span></div>',
                unsafe_allow_html=True)


def grafico(fig):
    st.plotly_chart(fig, use_container_width=True, theme=None)


def exportar(df, rotulo, arquivo):
    """CSV pronto para Excel em português (separador ';', decimal ',', UTF-8 com BOM)."""
    st.download_button(rotulo, data=df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                       file_name=arquivo, mime="text/csv", key=f"dl_{arquivo}")


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
        st.error("Senha incorreta. Tente novamente.")
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


def pct(num, den):
    """Percentual com proteção contra divisão por zero (retorna NaN)."""
    return (num / den.where(den > 0) * 100).round(1)


def locais_positivos_por_criterio(df_lab, df_amostras):
    """Nº de locais positivos para cada critério (independe da seleção na barra lateral)."""
    out = {}
    for nome, fn in CRITERIOS.items():
        if df_lab.empty:
            out[nome] = 0
            continue
        mask = df_lab["especie"].apply(fn).astype(bool)
        cods = df_lab.loc[mask, "codigo_amostra"].unique()
        out[nome] = int(df_amostras.loc[df_amostras["codigo_amostra"].isin(cods), "id_local"].nunique())
    return out


# --- ACESSO ---
if not check_password():
    st.stop()

st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")
if st.sidebar.button("Atualizar dados agora"):
    st.cache_data.clear()
    st.rerun()
st.markdown(f'<h1 class="app-title">{icone("folha", 34)}<span>Bromélias Ornamentais Urbanas e Culicídeos</span></h1>',
            unsafe_allow_html=True)
st.caption(f"Pesquisador: Flávio Santos (IOC - Fiocruz) | Atualizado em: {AGORA.strftime('%d/%m/%Y %H:%M')}")

# --- CARREGAMENTO ---
base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")
uid_visita = _get_secret("UID_VISITA")   # projeto de visita periódica (opcional)

with st.spinner("Baixando dados do Kobo..."):
    try:
        lista_campo = baixar_formulario(uid_campo, token, base_url)
        lista_visita = baixar_formulario(uid_visita, token, base_url)
        lista_lab = baixar_formulario(uid_lab, token, base_url)
    except requests.RequestException as exc:
        st.error(f"Falha ao baixar dados do Kobo: {exc}")
        st.stop()

if not lista_campo:
    st.warning("Nenhum dado encontrado.")
    st.stop()

# --- PROCESSAMENTO: CAMPO ---
locais, visitas_list, amostras = [], [], []

for indice, item in enumerate(lista_campo):
    id_local = normalizar_codigo(item.get("grp_cadastro/id_local_calc") or "") or f"SEM-ID-{indice}"
    bairro = item.get("grp_cadastro/bairro") or "N/I"
    tipologia = item.get("grp_cadastro/tipologia_imovel") or "N/I"

    geo = item.get("grp_cadastro/geolocalizacao", "")
    lat, lon = None, None
    if isinstance(geo, str) and " " in geo:
        try:
            p = geo.split()
            lat, lon = float(p[0]), float(p[1])
        except ValueError:
            pass

    locais.append({"id_local": id_local, "bairro": bairro, "tipologia": tipologia, "lat": lat, "lon": lon})

    visitas = item.get("rep_visitas", [])
    if not isinstance(visitas, list):
        continue
    for n_visita, v in enumerate(visitas):
        id_visita = f"{indice}-{n_visita}"
        data_v = v.get("rep_visitas/data_visita")
        visitas_list.append({
            "id_visita": id_visita, "id_local": id_local, "data_visita": data_v,
            "n_exam": v.get("rep_visitas/qtd_bromelias_examinadas"),
            "n_secas": v.get("rep_visitas/qtd_secas"),
            "n_agua_sem": v.get("rep_visitas/qtd_agua_sem_imaturos"),
        })
        ams = v.get("rep_visitas/rep_amostras", [])
        if not isinstance(ams, list):
            continue
        for a in ams:
            cod = a.get("rep_visitas/rep_amostras/codigo_amostra")
            if cod and str(cod).strip():
                # Cada amostra = uma bromélia com imaturos; a data da coleta fica junto da amostra
                amostras.append({
                    "id_visita": id_visita, "id_local": id_local, "codigo_amostra": normalizar_codigo(cod),
                    "data_visita": data_v,
                    "ph": a.get("rep_visitas/rep_amostras/ph_agua"),
                    "temp": a.get("rep_visitas/rep_amostras/temp_agua_c"),
                    "vol": a.get("rep_visitas/rep_amostras/volume_agua_ml"),
                    "genero": a.get("rep_visitas/rep_amostras/genero") or "N/I",
                    "porte": a.get("rep_visitas/rep_amostras/porte") or "N/I",
                })

# --- PROCESSAMENTO: VISITAS PERIÓDICAS (uma submissão = uma visita a um local já cadastrado) ---
locais_via_visita = {}   # código -> dados copiados do cadastro pelo formulário de visita
for indice, item in enumerate(lista_visita):
    id_local = normalizar_codigo(item.get("grp_identificacao/id_bromelia_visita") or "")
    if not id_local:
        continue
    id_visita = f"V{indice}"
    data_v = item.get("grp_dados_visita/data_visita")
    visitas_list.append({
        "id_visita": id_visita, "id_local": id_local, "data_visita": data_v,
        "n_exam": item.get("grp_dados_visita/qtd_bromelias_examinadas"),
        "n_secas": item.get("grp_dados_visita/qtd_secas"),
        "n_agua_sem": item.get("grp_dados_visita/qtd_agua_sem_imaturos"),
    })
    try:
        lat_v = float(item.get("grp_identificacao/latitude"))
        lon_v = float(item.get("grp_identificacao/longitude"))
    except (TypeError, ValueError):
        lat_v, lon_v = None, None
    locais_via_visita.setdefault(id_local, {
        "bairro": item.get("grp_identificacao/bairro") or "N/I", "lat": lat_v, "lon": lon_v})
    for a in item.get("rep_amostras", []) or []:
        cod = a.get("rep_amostras/codigo_amostra")
        if cod and str(cod).strip():
            amostras.append({
                "id_visita": id_visita, "id_local": id_local, "codigo_amostra": normalizar_codigo(cod),
                "data_visita": data_v,
                "ph": a.get("rep_amostras/ph_agua"),
                "temp": a.get("rep_amostras/temp_agua_c"),
                "vol": a.get("rep_amostras/volume_agua_ml"),
                "genero": a.get("rep_amostras/genero") or "N/I",
                "porte": a.get("rep_amostras/porte") or "N/I",
            })

COLS_AM = ["id_visita", "id_local", "codigo_amostra", "data_visita", "ph", "temp", "vol", "genero", "porte"]
df_locais_bruto = pd.DataFrame(locais, columns=["id_local", "bairro", "tipologia", "lat", "lon"])
# Visita com código que não está no cadastro: o local é criado com os dados copiados na própria visita
codigos_visita_sem_cadastro = sorted(set(locais_via_visita) - set(df_locais_bruto["id_local"]))
if codigos_visita_sem_cadastro:
    df_extra = pd.DataFrame([{"id_local": c, "bairro": locais_via_visita[c]["bairro"], "tipologia": "N/I",
                              "lat": locais_via_visita[c]["lat"], "lon": locais_via_visita[c]["lon"]}
                             for c in codigos_visita_sem_cadastro])
    df_locais_bruto = pd.concat([df_locais_bruto, df_extra], ignore_index=True)
df_amostras_bruto = pd.DataFrame(amostras, columns=COLS_AM)

# Colisões de código (não deveriam existir): o app mantém só o primeiro registro e avisa
ids_locais_duplicados = sorted(df_locais_bruto.loc[df_locais_bruto["id_local"].duplicated(), "id_local"].unique())
codigos_campo_duplicados = sorted(
    df_amostras_bruto.loc[df_amostras_bruto["codigo_amostra"].duplicated(), "codigo_amostra"].unique())

df_locais = df_locais_bruto.drop_duplicates(subset=["id_local"])
df_amostras = df_amostras_bruto.drop_duplicates(subset=["codigo_amostra"])
df_visitas = pd.DataFrame(visitas_list, columns=["id_visita", "id_local", "data_visita", "n_exam", "n_secas", "n_agua_sem"])

for col in ["n_exam", "n_secas", "n_agua_sem"]:
    df_visitas[col] = df_visitas[col].apply(numero_inteiro).astype(int)
# Bromélias com imaturos = examinadas − secas − com água sem imaturos (igual ao cálculo do formulário)
df_visitas["n_com"] = (df_visitas["n_exam"] - df_visitas["n_secas"] - df_visitas["n_agua_sem"]).clip(lower=0)

df_visitas["data_visita"] = pd.to_datetime(df_visitas["data_visita"], errors="coerce")
df_amostras["data_visita"] = pd.to_datetime(df_amostras["data_visita"], errors="coerce")
for col in ["ph", "temp", "vol"]:
    df_amostras[col] = para_numero(df_amostras[col])

# --- PROCESSAMENTO: LABORATÓRIO ---
# Uma análise por amostra: se o mesmo código foi enviado mais de uma vez, vale o envio mais recente
lab_por_codigo = {}
codigos_lab_duplicados = set()
for item in sorted(lista_lab, key=lambda i: i.get("_submission_time") or ""):
    cod_lab = item.get("grp_amostra/codigo_amostra")
    if not cod_lab or not str(cod_lab).strip():
        continue
    cod_lab = normalizar_codigo(cod_lab)
    if cod_lab in lab_por_codigo:
        codigos_lab_duplicados.add(cod_lab)
    lab_por_codigo[cod_lab] = item

codigos_lab = set(lab_por_codigo)   # amostras com formulário de laboratório preenchido (mesmo sem larvas)
lab_especies = []
resultados_lab = {}                 # código -> positivo / negativo / inconclusivo
for cod_lab, item in lab_por_codigo.items():
    res_linhas = []
    for e in item.get("rep_especies", []) or []:
        especie = e.get("rep_especies/especie_identificada") or "nao_identificado"
        # Mesma soma do formulário do laboratório: larvas + pupas + adultos
        qtd = (numero_inteiro(e.get("rep_especies/qtd_larvas")) + numero_inteiro(e.get("rep_especies/qtd_pupas"))
               + numero_inteiro(e.get("rep_especies/qtd_adultos")))
        res = normalizar_texto(e.get("rep_especies/resultado_amostra"))
        if res:
            res_linhas.append(res)
        lab_especies.append({"codigo_amostra": cod_lab,
                             "especie": normalizar_texto(especie).replace(" ", "_"),
                             "qtd_especimes": qtd})
    # Lê o resultado geral fora do grupo repetido (se for movido) ou, senão, das linhas de espécie
    res_geral = normalizar_texto(item.get("grp_resultado/resultado_amostra"))
    if not res_geral and res_linhas:
        res_geral = ("inconclusivo" if "inconclusivo" in res_linhas
                     else "positivo" if "positivo" in res_linhas else "negativo")
    resultados_lab[cod_lab] = res_geral

df_lab = pd.DataFrame(lab_especies, columns=["codigo_amostra", "especie", "qtd_especimes"])

# Códigos do laboratório que não existem em nenhuma coleta (provável erro de digitação)
df_amostras_todas = df_amostras.copy()
codigos_lab_orfaos = sorted(codigos_lab - set(df_amostras["codigo_amostra"]))

df_visitas_todas = df_visitas.copy()
df_locais_todos = df_locais.copy()

# --- BARRA LATERAL: CRITÉRIO E FILTRO DE DATA ---
st.sidebar.header("Critério de positividade")
criterio_nome = st.sidebar.selectbox("Espécie-alvo", list(CRITERIOS), index=0,
                                     help="Define o que conta como positivo em todo o painel.")
criterio_fn = CRITERIOS[criterio_nome]

st.sidebar.header("Filtro de data")
periodo_sel = None
datas_validas = df_visitas["data_visita"].dropna()
if not datas_validas.empty:
    data_min, data_max = datas_validas.min().date(), datas_validas.max().date()
    periodo_sel = st.sidebar.date_input("Período da visita", value=(data_min, data_max),
                                        min_value=data_min, max_value=data_max)

if periodo_sel and len(periodo_sel) == 2:
    ini = pd.Timestamp(periodo_sel[0])
    fim = pd.Timestamp(periodo_sel[1]) + pd.Timedelta(days=1)
    df_visitas = df_visitas[(df_visitas["data_visita"] >= ini) & (df_visitas["data_visita"] < fim)]
    # Amostras filtradas pela data da PRÓPRIA coleta (e não pelo local)
    df_amostras = df_amostras[(df_amostras["data_visita"] >= ini) & (df_amostras["data_visita"] < fim)]
    df_locais = df_locais[df_locais["id_local"].isin(df_visitas["id_local"].unique())]

if df_locais.empty:
    st.warning("Nenhum local com visita no período selecionado.")
    st.stop()

df_lab = df_lab[df_lab["codigo_amostra"].isin(df_amostras["codigo_amostra"])].copy()

# --- RESULTADO POR AMOSTRA (cada amostra = uma bromélia com imaturos) ---
df_lab["alvo"] = df_lab["especie"].apply(criterio_fn).astype(bool)
df_lab["qtd_alvo"] = df_lab["qtd_especimes"].where(df_lab["alvo"], 0)

if df_lab.empty:
    df_res_lab = pd.DataFrame(columns=["codigo_amostra", "qtd_total", "qtd_alvo", "positiva"])
else:
    df_res_lab = df_lab.groupby("codigo_amostra").agg(
        qtd_total=("qtd_especimes", "sum"), qtd_alvo=("qtd_alvo", "sum"), positiva=("alvo", "any")
    ).reset_index()

df_am = df_amostras.merge(df_res_lab, on="codigo_amostra", how="left")
df_am["positiva"] = df_am["positiva"].eq(True)
df_am["registrada_lab"] = df_am["codigo_amostra"].isin(codigos_lab)
df_am["resultado_lab"] = df_am["codigo_amostra"].map(resultados_lab).fillna("")
# Espécie-alvo encontrada = positiva, mesmo que o resultado geral esteja inconclusivo
df_am["inconclusiva"] = df_am["registrada_lab"] & (df_am["resultado_lab"] == "inconclusivo") & ~df_am["positiva"]
df_am["analisada"] = df_am["registrada_lab"] & ~df_am["inconclusiva"]
df_am["pendente"] = ~df_am["registrada_lab"]
df_am["qtd_total"] = pd.to_numeric(df_am["qtd_total"], errors="coerce").fillna(0)
df_am["qtd_alvo"] = pd.to_numeric(df_am["qtd_alvo"], errors="coerce").fillna(0)

# --- RESULTADO POR LOCAL ---
df_vis_loc = df_visitas.groupby("id_local").agg(
    visitas=("id_visita", "count"), n_exam=("n_exam", "sum"), n_secas=("n_secas", "sum"),
    n_agua_sem=("n_agua_sem", "sum"), n_com=("n_com", "sum")).reset_index()

if df_am.empty:
    df_am_loc = pd.DataFrame(columns=["id_local", "amostras", "analisadas", "pendentes", "inconclusivas",
                                      "positivas", "qtd_total", "qtd_alvo"])
else:
    df_am_loc = df_am.groupby("id_local").agg(
        amostras=("codigo_amostra", "count"), analisadas=("analisada", "sum"), pendentes=("pendente", "sum"),
        inconclusivas=("inconclusiva", "sum"), positivas=("positiva", "sum"),
        qtd_total=("qtd_total", "sum"), qtd_alvo=("qtd_alvo", "sum")).reset_index()

df_final = df_locais.merge(df_vis_loc, on="id_local", how="left").merge(df_am_loc, on="id_local", how="left")
for col in ["visitas", "n_exam", "n_secas", "n_agua_sem", "n_com", "amostras", "analisadas", "pendentes",
            "inconclusivas", "positivas", "qtd_total", "qtd_alvo"]:
    df_final[col] = pd.to_numeric(df_final[col], errors="coerce").fillna(0)

# Status do local: Positivo (alguma bromélia com a espécie-alvo); Negativo (todas as amostras já
# analisadas sem a espécie-alvo, ou nenhuma bromélia com imaturos); Sem análise (pendente/inconclusiva)
df_final["positivo"] = df_final["positivas"] > 0
df_final["resolvido"] = df_final["positivo"] | ((df_final["pendentes"] == 0) & (df_final["inconclusivas"] == 0))
df_final["status"] = "Sem análise"
df_final.loc[df_final["resolvido"], "status"] = "Negativo"
df_final.loc[df_final["positivo"], "status"] = "Positivo"

# --- INDICADORES ---
n_locais = len(df_final)
n_resolvidos = int(df_final["resolvido"].sum())
locais_positivos = int(df_final["positivo"].sum())
positividade = (locais_positivos / n_resolvidos * 100) if n_resolvidos else 0.0   # % de locais positivos

n_exam = int(df_final["n_exam"].sum())
n_com = int(df_final["n_com"].sum())
n_agua = n_com + int(df_final["n_agua_sem"].sum())
bromelias_positivas = int(df_am["positiva"].sum())
n_sem_resultado = int(df_am["pendente"].sum() + df_am["inconclusiva"].sum())
base_bromelias = n_exam - n_sem_resultado
positividade_bromelias = (bromelias_positivas / base_bromelias * 100) if base_bromelias > 0 else 0.0
total_especimes = int(df_final["qtd_total"].sum())

df_rank = df_final.groupby("bairro").agg(
    Locais=("id_local", "count"), Com_resultado=("resolvido", "sum"), Locais_positivos=("positivo", "sum"),
    Bromelias=("n_exam", "sum"), Positivas=("positivas", "sum"),
    Pendentes=("pendentes", "sum"), Inconclusivas=("inconclusivas", "sum")).reset_index()
df_rank["% Locais positivos"] = pct(df_rank["Locais_positivos"], df_rank["Com_resultado"])
df_rank["Positividade de bromélias (%)"] = pct(
    df_rank["Positivas"], df_rank["Bromelias"] - df_rank["Pendentes"] - df_rank["Inconclusivas"])

bairro_alerta = "Nenhum"
df_top = df_rank.dropna(subset=["% Locais positivos"])
df_top = df_top[df_top["% Locais positivos"] > 0].sort_values("% Locais positivos", ascending=False)
if not df_top.empty:
    t = df_top.iloc[0]
    bairro_alerta = f"{str(t['bairro']).capitalize()} ({int(t['Locais_positivos'])}/{int(t['Com_resultado'])} locais)"

if n_resolvidos == 0:
    nivel, msg = "SEM DADOS", "Nenhum local com resultado de laboratório no período."
elif positividade < RISCO_MEDIO:
    nivel, msg = "BAIXO", "Risco baixo."
elif positividade < RISCO_ALTO:
    nivel, msg = "MÉDIO", f"Risco médio. Atenção ao bairro {bairro_alerta}."
else:
    nivel, msg = "ALTO", f"Risco alto. Ação urgente no bairro {bairro_alerta}."
cor, cor_texto = NIVEIS[nivel]

# 1. PAINEL EXECUTIVO
secao("Painel executivo", "painel")
k = st.columns(6)
k[0].metric("Locais", n_locais)
k[1].metric("Bromélias examinadas", n_exam)
k[2].metric("Com imaturos", n_com)
k[3].metric("Bromélias positivas", bromelias_positivas)
k[4].metric("Positividade de bromélias", f"{positividade_bromelias:.1f}%")
k[5].metric("Locais positivos", f"{locais_positivos}/{n_resolvidos}")

col_notas, col_alerta = st.columns([2, 1])
with col_notas:
    por_criterio = locais_positivos_por_criterio(df_lab, df_amostras)
    pct_agua = f"{n_agua / n_exam * 100:.0f}%" if n_exam else "—"
    st.markdown(
        '<div class="card">'
        f'<p><b>Critério:</b> {escape(criterio_nome)}. Positividade do local = locais positivos ÷ locais com resultado '
        f'({n_locais - n_resolvidos} sem resultado: amostras pendentes ou inconclusivas).</p>'
        f'<p class="muted">Positividade de bromélias = bromélias positivas ÷ examinadas, descontadas as sem resultado '
        f'({n_sem_resultado}).</p>'
        f'<p class="muted">Bromélias com água: {n_agua} ({pct_agua} das examinadas) · '
        f'Espécimes no laboratório (larvas + pupas + adultos): {total_especimes}</p>'
        '<p class="muted">Locais positivos por espécie (período): '
        + " · ".join(f"{escape(nome)}: {v}" for nome, v in por_criterio.items()) + '</p>'
        '</div>', unsafe_allow_html=True)
with col_alerta:
    st.markdown(
        f'<div class="card status-card" style="border-left:4px solid {cor};">'
        '<div class="status-label">Nível de risco</div>'
        f'<div class="status-value" style="color:{cor_texto};"><span class="dot" style="background:{cor};"></span>'
        f'{escape(nivel)}</div>'
        f'<p>{escape(msg)}</p></div>', unsafe_allow_html=True)

# 2. MÉDIAS DA ÁGUA
secao("Médias da água (bromélias com imaturos)", "agua")
st.caption("pH, temperatura e volume são medidos apenas nas bromélias com imaturos.")
if not df_am.empty:
    m1, m2, m3 = st.columns(3)
    m1.metric("pH médio", f"{df_am['ph'].mean():.1f}" if df_am["ph"].notna().any() else "—")
    m2.metric("Temperatura média", f"{df_am['temp'].mean():.1f} °C" if df_am["temp"].notna().any() else "—")
    m3.metric("Volume médio", f"{df_am['vol'].mean():.0f} mL" if df_am["vol"].notna().any() else "—")

# 3. AMOSTRAS PENDENTES
secao("Amostras pendentes de análise (coletadas, não processadas)", "relogio")
if not df_am.empty:
    df_pend = df_am[df_am["pendente"]].copy()
    if not df_pend.empty:
        df_pend["Dias de Espera"] = (HOJE - df_pend["data_visita"]).dt.days.astype("Int64")
        df_exibicao = df_pend[["codigo_amostra", "id_local", "data_visita", "Dias de Espera"]].copy()
        df_exibicao["data_visita"] = df_exibicao["data_visita"].dt.strftime("%d/%m/%Y")
        df_exibicao["Ação"] = URL_FORMULARIO_LAB
        df_exibicao = df_exibicao.rename(columns={"codigo_amostra": "Código da Amostra", "id_local": "Local",
                                                  "data_visita": "Data da Coleta"})
        df_exibicao = df_exibicao.sort_values(by="Dias de Espera", ascending=False)
        st.dataframe(df_exibicao[["Código da Amostra", "Local", "Data da Coleta", "Dias de Espera", "Ação"]],
                     hide_index=True, use_container_width=True,
                     column_config={"Ação": st.column_config.LinkColumn("Ação", display_text="Analisar")})
        dias_max = df_exibicao["Dias de Espera"].max()
        if pd.notna(dias_max) and dias_max > 30:
            st.warning(f"Existem amostras com mais de 30 dias de espera. A mais antiga aguarda há {int(dias_max)} dias.")
        else:
            st.info("Todas as amostras pendentes foram coletadas há menos de 30 dias.")
        exportar(df_exibicao.drop(columns=["Ação"]), "Exportar pendências (CSV)", "amostras_pendentes.csv")
    else:
        st.success("Todas as amostras coletadas já foram analisadas no laboratório.")
else:
    st.info("Ainda não há amostras coletadas para verificar.")

# Verificações de qualidade dos dados
if codigos_lab_orfaos:
    with st.expander(f"{len(codigos_lab_orfaos)} código(s) do laboratório sem coleta correspondente"):
        codigos_campo = sorted(set(df_amostras_todas["codigo_amostra"]))
        for cod in codigos_lab_orfaos:
            prox = difflib.get_close_matches(cod, codigos_campo, n=1, cutoff=0.6)
            st.write(f"**{cod}** → código parecido no campo: {prox[0] if prox else 'nenhum'}")

if codigos_lab_duplicados:
    st.warning(f"{len(codigos_lab_duplicados)} código(s) com mais de um envio no laboratório "
               f"(vale o mais recente): {', '.join(sorted(codigos_lab_duplicados))}")

if ids_locais_duplicados:
    st.warning(f"Código de local repetido em cadastros diferentes (só o primeiro é usado): "
               f"{', '.join(ids_locais_duplicados)}")

if codigos_campo_duplicados:
    st.warning(f"Código de amostra repetido no campo (só o primeiro é usado): "
               f"{', '.join(codigos_campo_duplicados)}")

df_cont = df_am.groupby("id_visita").size().rename("n_amostras").reset_index()
df_chk = df_visitas.merge(df_cont, on="id_visita", how="left").fillna({"n_amostras": 0})
df_incons = df_chk[df_chk["n_com"] != df_chk["n_amostras"]]
if not df_incons.empty:
    with st.expander(f"{len(df_incons)} visita(s) em que o nº de amostras difere do nº de bromélias com imaturos"):
        st.dataframe(df_incons[["id_local", "data_visita", "n_com", "n_amostras"]].rename(
            columns={"id_local": "Local", "data_visita": "Data", "n_com": "Com imaturos (campo)",
                     "n_amostras": "Amostras registradas"}), hide_index=True, use_container_width=True)

if codigos_visita_sem_cadastro:
    st.warning(f"{len(codigos_visita_sem_cadastro)} código(s) de visita não estão no cadastro "
               f"(local criado com os dados da própria visita): {', '.join(codigos_visita_sem_cadastro)}")

# 3.1 ACOMPANHAMENTO MENSAL
secao("Acompanhamento mensal", "calendario")
df_ult = (df_visitas_todas.dropna(subset=["data_visita"]).groupby("id_local")["data_visita"].max().reset_index())
if not df_ult.empty:
    df_ult["Dias sem visita"] = (HOJE - df_ult["data_visita"]).dt.days
    df_ult = df_ult.merge(df_locais_todos[["id_local", "bairro"]], on="id_local", how="left")
    df_atras = df_ult[df_ult["Dias sem visita"] > PRAZO_VISITA_DIAS].sort_values("Dias sem visita", ascending=False)
    k1, k2, _ = st.columns([1, 1, 2])
    k1.metric("Locais acompanhados", len(df_ult))
    k2.metric(f"Em atraso (> {PRAZO_VISITA_DIAS} dias)", len(df_atras))
    if not df_atras.empty:
        df_atras = df_atras.assign(**{"Última visita": df_atras["data_visita"].dt.strftime("%d/%m/%Y")})
        st.dataframe(df_atras[["id_local", "bairro", "Última visita", "Dias sem visita"]].rename(
            columns={"id_local": "Local", "bairro": "Bairro"}), hide_index=True, use_container_width=True)
    else:
        st.success("Todos os locais foram visitados dentro do prazo.")
else:
    st.info("Ainda não há visitas registradas.")

# 4. MAPAS E TERMÔMETRO
secao("Mapas de risco e termômetro", "mapa")
df_mapa = df_final.dropna(subset=["lat", "lon"])
if not df_mapa.empty:
    centro_lat = df_mapa["lat"].mean()
    centro_lon = df_mapa["lon"].mean()
    tab1, tab2, tab3, tab4 = st.tabs(["Mapa base", "Mapa de calor", "Locais", "Risco por bairro"])

    with tab1:
        col_mapa, col_termo = st.columns([3, 1])
        with col_mapa:
            m1 = folium.Map(location=[centro_lat, centro_lon], zoom_start=16, tiles="OpenStreetMap")
            for _, row in df_mapa.iterrows():
                if row["positivo"]:
                    folium.Circle(location=[row["lat"], row["lon"]], radius=100, color=STATUS_CORES["Positivo"],
                                  fill=True, fill_opacity=0.2, weight=2).add_to(m1)
                popup = (f"<b>{escape(str(row['id_local']))}</b> — {escape(row['status'].upper())}<br>"
                         f"Bromélias examinadas: {int(row['n_exam'])}<br>"
                         f"Com imaturos: {int(row['n_com'])} | positivas: {int(row['positivas'])}")
                folium.Marker(location=[row["lat"], row["lon"]],
                              icon=folium.Icon(color=STATUS_ICONES[row["status"]], icon="info-sign"),
                              popup=folium.Popup(popup, max_width=320)).add_to(m1)
            st_folium(m1, width=None, height=450, key="mapa1")
        with col_termo:
            st.markdown("#### Termômetro")
            fig_termo = go.Figure(go.Indicator(
                mode="gauge+number", value=positividade, number={"suffix": "%"}, title={"text": nivel},
                gauge={"axis": {"range": [0, 100]}, "bar": {"color": cor},
                       "steps": [{"range": [0, RISCO_MEDIO], "color": "#DCFCE7"},
                                 {"range": [RISCO_MEDIO, RISCO_ALTO], "color": "#FEF3C7"},
                                 {"range": [RISCO_ALTO, 100], "color": "#FEE2E2"}]}))
            fig_termo.update_layout(height=320, margin=dict(l=10, r=10, t=50, b=10))
            grafico(fig_termo)
            st.caption("% de locais positivos")

    with tab2:
        st.markdown(f"#### Mapa de calor ({criterio_nome}: espécimes por local)")
        df_calor = df_mapa[df_mapa["positivo"]]
        if not df_calor.empty:
            fig_mapa_calor = px.density_mapbox(
                df_calor, lat="lat", lon="lon", z="qtd_alvo", radius=60,
                center=dict(lat=centro_lat, lon=centro_lon), zoom=13,
                mapbox_style="open-street-map", color_continuous_scale="YlOrRd")
            fig_mapa_calor.add_scattermapbox(
                lat=df_calor["lat"], lon=df_calor["lon"], mode="markers",
                marker=dict(size=12, color=COR_ERRO), showlegend=False,
                hovertext=df_calor["id_local"], hoverinfo="text")
            fig_mapa_calor.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=450, coloraxis_showscale=False)
            grafico(fig_mapa_calor)
        else:
            st.info(f"Nenhum local positivo para {criterio_nome} no período.")

    with tab3:
        st.markdown("#### Locais (tamanho = bromélias examinadas)")
        df_bolhas = df_mapa.assign(tamanho=df_mapa["n_exam"].clip(lower=1))
        fig_loc = px.scatter_mapbox(
            df_bolhas, lat="lat", lon="lon", size="tamanho", color="status", color_discrete_map=STATUS_CORES,
            hover_name="id_local", hover_data={"bairro": True, "n_exam": True, "n_com": True, "positivas": True,
                                               "tamanho": False, "lat": False, "lon": False},
            center=dict(lat=centro_lat, lon=centro_lon), zoom=14, mapbox_style="open-street-map", size_max=40)
        fig_loc.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=450, legend_title_text="Status")
        grafico(fig_loc)

    with tab4:
        df_bairro = df_mapa.groupby("bairro").agg(
            lat=("lat", "mean"), lon=("lon", "mean"), locais=("id_local", "count"),
            com_resultado=("resolvido", "sum"), positivos=("positivo", "sum")).reset_index()
        df_bairro["% risco"] = pct(df_bairro["positivos"], df_bairro["com_resultado"]).fillna(0)
        fig_bairro = px.scatter_mapbox(
            df_bairro, lat="lat", lon="lon", size="locais", color="% risco",
            color_continuous_scale=[COR_OK, COR_ALERTA, COR_ERRO], hover_name="bairro",
            hover_data=["com_resultado", "positivos"], center=dict(lat=centro_lat, lon=centro_lon),
            zoom=13, mapbox_style="open-street-map", size_max=50)
        fig_bairro.update_layout(height=450, margin=dict(l=0, r=0, t=0, b=0))
        grafico(fig_bairro)

# 5. SÉRIE TEMPORAL
secao("Série temporal de coletas", "serie")
df_serie = df_visitas.dropna(subset=["data_visita"]).copy()
if not df_serie.empty:
    df_serie["mes"] = df_serie["data_visita"].dt.to_period("M").astype(str)
    contagem = df_serie.groupby("mes").agg(visitas=("id_visita", "count"), bromelias=("n_exam", "sum")).reset_index()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=contagem["mes"], y=contagem["visitas"], name="Visitas", marker_color=COR_NEUTRA_ESCURA))
    fig.add_trace(go.Bar(x=contagem["mes"], y=contagem["bromelias"], name="Bromélias examinadas",
                         marker_color=COR_NEUTRA))
    fig.update_layout(barmode="group", height=320)
    grafico(fig)

# 6. ESPÉCIES E ECOLOGIA
secao("Espécies e ecologia", "barras")
col_esp, col_eco = st.columns([2, 1])
with col_esp:
    st.markdown("#### Frequência de espécies")
    if not df_lab.empty:
        df_chart = df_lab.groupby("especie").agg(qtd_especimes=("qtd_especimes", "sum")).reset_index()
        df_chart["Grupo"] = df_chart["especie"].apply(lambda s: "Espécie-alvo" if criterio_fn(s) else "Outras")
        df_chart["especie"] = df_chart["especie"].str.replace("_", " ").str.capitalize()
        grafico(px.bar(df_chart, x="especie", y="qtd_especimes", text="qtd_especimes", color="Grupo",
                       color_discrete_map={"Espécie-alvo": COR_ERRO, "Outras": COR_NEUTRA}))
with col_eco:
    st.markdown(f"#### pH: {criterio_nome} × outros imaturos")
    st.caption("A água só é medida em bromélias com imaturos; a comparação é entre espécies, não com água sem larvas.")
    df_ph = df_am[df_am["analisada"]].dropna(subset=["ph"]).copy()
    if not df_ph.empty:
        df_ph["Resultado"] = df_ph["positiva"].map({True: "Espécie-alvo", False: "Outros imaturos"})
        grafico(px.box(df_ph, x="Resultado", y="ph", points="all", color="Resultado",
                       color_discrete_map={"Espécie-alvo": COR_ERRO, "Outros imaturos": COR_NEUTRA}))
    else:
        st.info("Sem amostras analisadas com pH registrado.")

# 7. TIPOLOGIA
secao("Análise por tipologia de imóvel", "casa")
df_tipo = df_final.groupby("tipologia").agg(
    Com_resultado=("resolvido", "sum"), Positivos=("positivo", "sum")).reset_index()
df_tipo["% Positividade"] = pct(df_tipo["Positivos"], df_tipo["Com_resultado"])
df_plot = pd.melt(df_tipo, id_vars=["tipologia"], value_vars=["Positivos", "Com_resultado"],
                  var_name="Status", value_name="Quantidade")
fig_tipo = px.bar(df_plot, x="tipologia", y="Quantidade", color="Status", barmode="group", text="Quantidade",
                  color_discrete_map={"Positivos": COR_ERRO, "Com_resultado": COR_NEUTRA_ESCURA})
for _, row in df_tipo.iterrows():
    texto = f"{row['% Positividade']}%" if pd.notna(row["% Positividade"]) else "—"
    fig_tipo.add_annotation(x=row["tipologia"], y=row["Com_resultado"] + 0.5, text=texto, showarrow=False,
                            font=dict(color="#B91C1C", size=13))
fig_tipo.update_layout(height=360)
grafico(fig_tipo)

# 8. TABELAS FINAIS
secao("Tabelas de totais e estatísticas", "tabela")
col_tab1, col_tab2 = st.columns(2)
with col_tab1:
    st.markdown("#### Totais por espécie")
    if not df_lab.empty:
        df_esp = df_lab.groupby("especie").agg(Total=("qtd_especimes", "sum")).reset_index()
        df_esp["especie"] = df_esp["especie"].str.replace("_", " ").str.capitalize()
        df_esp["%"] = (df_esp["Total"] / df_esp["Total"].sum() * 100).round(1).astype(str) + "%"
        df_esp = df_esp.rename(columns={"especie": "Espécie", "Total": "Espécimes"})
        st.dataframe(df_esp, hide_index=True, use_container_width=True)
        exportar(df_esp, "Exportar espécies (CSV)", "totais_por_especie.csv")
with col_tab2:
    st.markdown("#### Estatística descritiva (variáveis ambientais)")
    if not df_am.empty:
        variaveis = {"pH da Água": df_am["ph"], "Temperatura (°C)": df_am["temp"], "Volume (mL)": df_am["vol"]}
        stats = []
        for nome, serie in variaveis.items():
            dados = serie.dropna()
            if not dados.empty:
                stats.append({"Variável": nome, "N": len(dados), "Média": round(dados.mean(), 2),
                              "Mediana": round(dados.median(), 2),
                              "Desvio Padrão": round(dados.std(), 2) if len(dados) > 1 else None,
                              "Mínimo": round(dados.min(), 2), "Máximo": round(dados.max(), 2)})
        if stats:
            df_stats = pd.DataFrame(stats)
            st.dataframe(df_stats, hide_index=True, use_container_width=True)
            exportar(df_stats, "Exportar estatísticas (CSV)", "estatisticas_ambientais.csv")

# 9. SAZONALIDADE E RANKING
secao("Sazonalidade e ranking de bairros", "tendencia")
col_saz, col_rank = st.columns([2, 1])
with col_saz:
    st.markdown(f"#### Positividade de bromélias ({criterio_nome}) por mês")
    df_v = df_visitas.dropna(subset=["data_visita"]).copy()
    df_a = df_am.dropna(subset=["data_visita"]).copy()
    if not df_v.empty:
        df_v["mes"] = df_v["data_visita"].dt.to_period("M").astype(str)
        df_a["mes"] = df_a["data_visita"].dt.to_period("M").astype(str)
        exam_mes = df_v.groupby("mes")["n_exam"].sum()
        pos_mes = df_a[df_a["positiva"]].groupby("mes").size().rename("Positivas")
        sem_mes = df_a[df_a["pendente"] | df_a["inconclusiva"]].groupby("mes").size().rename("Sem_resultado")
        df_saz = pd.DataFrame({"Examinadas": exam_mes}).join(pos_mes).join(sem_mes).fillna(0).reset_index()
        df_saz["Base"] = df_saz["Examinadas"] - df_saz["Sem_resultado"]
        df_saz["%"] = pct(df_saz["Positivas"], df_saz["Base"])
        fig_saz = px.line(df_saz, x="mes", y="%", markers=True, color_discrete_sequence=[COR_TEXTO],
                          hover_data=["Examinadas", "Positivas", "Sem_resultado"])
        fig_saz.update_layout(height=340, yaxis_title="% de bromélias com a espécie-alvo", xaxis_title="Mês da coleta")
        grafico(fig_saz)
with col_rank:
    st.markdown("#### Ranking de bairros (maior risco)")
    st.caption("% de locais positivos = locais positivos ÷ locais com resultado.")
    df_ranking = df_rank.drop(columns=["Pendentes", "Inconclusivas"]).rename(columns={
        "bairro": "Bairro", "Com_resultado": "Com resultado", "Locais_positivos": "Locais positivos",
        "Bromelias": "Bromélias", "Positivas": "Bromélias positivas"}
    ).sort_values(by="% Locais positivos", ascending=False, na_position="last")
    st.dataframe(df_ranking, hide_index=True, use_container_width=True)
    exportar(df_ranking, "Exportar ranking (CSV)", "ranking_bairros.csv")

# 10. EXPORTAÇÃO
secao("Exportar dados", "download")
st.caption("Arquivos CSV para Excel (separador ponto e vírgula, decimal vírgula). Respeitam o período e o critério "
           "selecionados. Não incluem coordenadas nem endereços.")
df_exp_locais = df_final[["id_local", "bairro", "tipologia", "status", "visitas", "n_exam", "n_secas", "n_agua_sem",
                          "n_com", "amostras", "analisadas", "pendentes", "inconclusivas", "positivas",
                          "qtd_total"]].rename(columns={
    "id_local": "Local", "bairro": "Bairro", "tipologia": "Tipologia", "status": "Status", "visitas": "Visitas",
    "n_exam": "Bromélias examinadas", "n_secas": "Secas", "n_agua_sem": "Com água sem imaturos",
    "n_com": "Com imaturos", "amostras": "Amostras", "analisadas": "Analisadas", "pendentes": "Pendentes",
    "inconclusivas": "Inconclusivas", "positivas": "Positivas (espécie-alvo)", "qtd_total": "Espécimes"})
df_exp_amostras = df_am[["codigo_amostra", "id_local", "data_visita", "ph", "temp", "vol", "genero", "porte",
                         "registrada_lab", "resultado_lab", "positiva", "qtd_total"]].rename(columns={
    "codigo_amostra": "Amostra", "id_local": "Local", "data_visita": "Data da coleta", "ph": "pH",
    "temp": "Temperatura (°C)", "vol": "Volume (mL)", "genero": "Gênero", "porte": "Porte",
    "registrada_lab": "Registrada no laboratório", "resultado_lab": "Resultado geral",
    "positiva": "Positiva (espécie-alvo)", "qtd_total": "Espécimes"})
e1, e2, _ = st.columns([1, 1, 2])
with e1:
    exportar(df_exp_locais, "Exportar locais (CSV)", "locais.csv")
with e2:
    exportar(df_exp_amostras, "Exportar amostras (CSV)", "amostras.csv")
