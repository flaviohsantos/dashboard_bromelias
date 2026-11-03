# -*- coding: utf-8 -*-
"""Dashboard — Bromélias Ornamentais Urbanas e Culicídeos (registro por LOCAL).

v2 — Theme switcher com 3 design systems da biblioteca designmd.app.br:
  1. Data-Dense Dashboard (BI, light + dark)
  2. CRM Copper Sand (SaaS, light)
  3. Bento Dados Estruturados (Bento grid, light)

Modelo: cada local (ex.: calçada) tem uma coordenada. Em cada visita registra-se quantas bromélias
foram examinadas, quantas estavam secas e quantas tinham água sem imaturos; cada bromélia COM imaturos
gera uma amostra (código, pH, temperatura, volume) que é analisada no laboratório.

Fontes (Kobo): cadastro dos locais (UID_CAMPO), visitas periódicas (UID_VISITA) e laboratório (UID_LAB).
As visitas se ligam ao cadastro pelo código do local.
"""
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

# ═══ NOVO: importa o módulo de temas ═══
from themes import (
    TEMAS, TEMA_PADRAO,
    css_do_tema, tokens_plotly, tiles_folium, cores_status,
)

# set_page_config precisa ser o primeiro comando Streamlit
st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")

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
# ═══ ALTERADO: STATUS_CORES agora vem do tema (função cores_status) ═══
# STATUS_CORES = {...}  # removido — agora é dinâmico
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

# ═══════════════════════════════════════════════════════════════════════════
# ═══ NOVO: THEME SWITCHER (sidebar) ═══
# ═══════════════════════════════════════════════════════════════════════════
st.sidebar.header("🎨 Aparência")
# Rótulos amigáveis (dict tema → label)
opcoes_tema = {k: v["label"] for k, v in TEMAS.items()}
tema_nome = st.sidebar.selectbox(
    "Design system",
    options=list(opcoes_tema.keys()),
    format_func=lambda k: opcoes_tema[k],
    index=list(opcoes_tema.keys()).index(TEMA_PADRAO),
    help="Cada opção segue um DESIGN.md da biblioteca designmd.app.br",
)
st.sidebar.caption(TEMAS[tema_nome]["descricao"])

# Dark mode só faz sentido no Data-Dense (os outros 2 são light-only)
dark = False
if tema_nome == "Data-Dense Dashboard":
    dark = st.sidebar.toggle("🌙 Modo escuro", value=False,
                             help="Disponível apenas no Data-Dense Dashboard")
else:
    st.sidebar.caption("🌙 Modo escuro indisponível neste tema (light-only).")

# Injeta o CSS do tema escolhido (sobrescreve o config.toml)
st.markdown(css_do_tema(tema_nome, dark=dark), unsafe_allow_html=True)

# ═══ NOVO: tokens derivados do tema, usados no resto do app ═══
STATUS_CORES = cores_status(tema_nome, dark=dark)
PLOTLY_LAYOUT = tokens_plotly(tema_nome, dark=dark)
FOLIUM_TILES = tiles_folium(tema_nome, dark=dark)

# ═══ NOVO: helper para aplicar layout Plotly padronizado ═══
def _aplicar_layout(fig, height=350, margin=None):
    """Aplica tokens do tema a qualquer figura Plotly."""
    if margin is None:
        margin = dict(l=10, r=10, t=30, b=10)
    fig.update_layout(
        template=PLOTLY_LAYOUT["template"],
        paper_bgcolor=PLOTLY_LAYOUT["paper_bgcolor"],
        plot_bgcolor=PLOTLY_LAYOUT["plot_bgcolor"],
        font_color=PLOTLY_LAYOUT["font_color"],
        height=height,
        margin=margin,
    )
    return fig

# ═══════════════════════════════════════════════════════════════════════════
# ═══ FIM DO BLOCO NOVO — o resto é o app.py original (com ajustes pontuais) ═══
# ═══════════════════════════════════════════════════════════════════════════

st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")
if st.sidebar.button("🔄 Atualizar dados agora"):
    st.cache_data.clear()
    st.rerun()
# ═══ ALTERADO: emojis removidos dos títulos (DESIGN.md proíbe) ═══
st.title("Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption(f"Pesquisador: Flávio Santos (IOC - Fiocruz) | Atualizado em: {AGORA.strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")

# --- CARREGAMENTO --- (idêntico ao original)
base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")
uid_visita = _get_secret("UID_VISITA")

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

# --- PROCESSAMENTO: CAMPO --- (idêntico ao original)
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
                amostras.append({
                    "id_visita": id_visita, "id_local": id_local, "codigo_amostra": normalizar_codigo(cod),
                    "data_visita": data_v,
                    "ph": a.get("rep_visitas/rep_amostras/ph_agua"),
                    "temp": a.get("rep_visitas/rep_amostras/temp_agua_c"),
                    "vol": a.get("rep_visitas/rep_amostras/volume_agua_ml"),
                    "genero": a.get("rep_visitas/rep_amostras/genero") or "N/I",
                    "porte": a.get("rep_visitas/rep_amostras/porte") or "N/I",
                })

# --- PROCESSAMENTO: VISITAS PERIÓDICAS --- (idêntico ao original)
locais_via_visita = {}
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
               