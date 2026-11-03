# -*- coding: utf-8 -*-
import difflib
import hmac
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from themes import TEMAS, TEMA_PADRAO, css_do_tema, tokens_plotly, tiles_folium, cores_status
from dados import carregar_e_processar_dados, pct, normalizar_codigo

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
STATUS_ICONES = {"Positivo": "red", "Negativo": "blue", "Sem análise": "gray"}

def check_password():
    senha = os.environ.get("SENHA_ACESSO", "")
    try: senha = st.secrets["SENHA_ACESSO"]
    except Exception: pass
    if not senha: st.error("Senha não configurada."); return False
    def password_entered():
        st.session_state["password_correct"] = hmac.compare_digest(str(st.session_state.get("password", "")).encode("utf-8"), str(senha).encode("utf-8"))
        st.session_state.pop("password", None)
    if st.session_state.get("password_correct"): return True
    st.text_input("Senha de acesso:", type="password", on_change=password_entered, key="password")
    if st.session_state.get("password_correct") is False: st.error("😕 Senha incorreta.")
    return False

def locais_positivos_por_criterio(df_lab, df_amostras):
    out = {}
    for nome, fn in CRITERIOS.items():
        if df_lab.empty: out[nome] = 0; continue
        cods = df_lab.loc[df_lab["especie"].apply(fn).astype(bool), "codigo_amostra"].unique()
        out[nome] = int(df_amostras.loc[df_amostras["codigo_amostra"].isin(cods), "id_local"].nunique())
    return out

if not check_password(): st.stop()

# --- THEME SWITCHER ---
st.sidebar.header("🎨 Aparência")
opcoes_tema = {k: v["label"] for k, v in TEMAS.items()}
tema_nome = st.sidebar.selectbox("Design system", options=list(opcoes_tema.keys()), format_func=lambda k: opcoes_tema[k], index=list(opcoes_tema.keys()).index(TEMA_PADRAO))
st.sidebar.caption(TEMAS[tema_nome]["descricao"])
dark = st.sidebar.toggle("🌙 Modo escuro", value=False) if tema_nome == "Data-Dense Dashboard" else False
if not dark and tema_nome != "Data-Dense Dashboard": st.sidebar.caption("🌙 Modo escuro indisponível neste tema.")

st.markdown(css_do_tema(tema_nome, dark=dark), unsafe_allow_html=True)
STATUS_CORES = cores_status(tema_nome, dark=dark)
PLOTLY_LAYOUT = tokens_plotly(tema_nome, dark=dark)
FOLIUM_TILES = tiles_folium(tema_nome, dark=dark)

def _aplicar_layout(fig, height=350, margin=None):
    fig.update_layout(template=PLOTLY_LAYOUT["template"], paper_bgcolor=PLOTLY_LAYOUT["paper_bgcolor"], plot_bgcolor=PLOTLY_LAYOUT["plot_bgcolor"], font_color=PLOTLY_LAYOUT["font_color"], height=height, margin=margin or dict(l=10, r=10, t=30, b=10))
    return fig

# --- CARREGAMENTO ---
# ═══ NOVO: Auto-refresh nativo (substitui o streamlit_autorefresh) ═══
@st.fragment(run_every=300)  # 300 segundos = 5 minutos
def auto_refresh():
    # Este fragmento roda a cada 5 minutos e força o recarregamento dos dados
    st.cache_data.clear()
    st.rerun()

# Chama a função para ativar o timer
auto_refresh()
if st.sidebar.button("🔄 Atualizar dados agora"): st.cache_data.clear(); st.rerun()
st.title("Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption(f"Pesquisador: Flávio Santos (IOC - Fiocruz) | Atualizado em: {AGORA.strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")

with st.spinner("Baixando e processando dados do Kobo..."):
    try: dados = carregar_e_processar_dados()
    except Exception as exc: st.error(f"Falha ao baixar/processar dados: {exc}"); st.stop()

if dados is None or not dados:
    st.warning("Nenhum dado encontrado no formulário principal."); st.stop()

# Desempacota os dados
df_locais, df_locais_todos = dados["df_locais"], dados["df_locais_todos"]
df_visitas, df_visitas_todas = dados["df_visitas"], dados["df_visitas_todas"]
df_amostras, df_amostras_todas = dados["df_amostras"], dados["df_amostras_todas"]
df_lab, resultados_lab, codigos_lab = dados["df_lab"], dados["resultados_lab"], dados["codigos_lab"]

# --- BARRA LATERAL: CRITÉRIO E FILTRO ---
st.sidebar.markdown("---")
criterio_nome = st.sidebar.selectbox("🦟 Espécie-alvo", list(CRITERIOS), index=0)
criterio_fn = CRITERIOS[criterio_nome]
st.sidebar.markdown("---")
periodo_sel = None
datas_validas = df_visitas["data_visita"].dropna()
if not datas_validas.empty:
    periodo_sel = st.sidebar.date_input("🔎 Período da Visita", value=(datas_validas.min().date(), datas_validas.max().date()), min_value=datas_validas.min().date(), max_value=datas_validas.max().date())

if periodo_sel and len(periodo_sel) == 2:
    ini, fim = pd.Timestamp(periodo_sel[0]), pd.Timestamp(periodo_sel[1]) + pd.Timedelta(days=1)
    df_visitas = df_visitas[(df_visitas["data_visita"] >= ini) & (df_visitas["data_visita"] < fim)]
    df_amostras = df_amostras[(df_amostras["data_visita"] >= ini) & (df_amostras["data_visita"] < fim)]
    df_locais = df_locais[df_locais["id_local"].isin(df_visitas["id_local"].unique())]

if df_locais.empty: st.warning("Nenhum local com visita no período selecionado."); st.stop()
df_lab = df_lab[df_lab["codigo_amostra"].isin(df_amostras["codigo_amostra"])].copy()

# --- PROCESSAMENTO MATEMÁTICO PÓS-FILTRO ---
df_lab["alvo"] = df_lab["especie"].apply(criterio_fn).astype(bool)
df_lab["qtd_alvo"] = df_lab["qtd_especimes"].where(df_lab["alvo"], 0)

if df_lab.empty: df_res_lab = pd.DataFrame(columns=["codigo_amostra", "qtd_total", "qtd_alvo", "positiva"])
else: df_res_lab = df_lab.groupby("codigo_amostra").agg(qtd_total=("qtd_especimes", "sum"), qtd_alvo=("qtd_alvo", "sum"), positiva=("alvo", "any")).reset_index()

df_am = df_amostras.merge(df_res_lab, on="codigo_amostra", how="left")
df_am["positiva"] = df_am["positiva"].eq(True)
df_am["registrada_lab"] = df_am["codigo_amostra"].isin(codigos_lab)
df_am["resultado_lab"] = df_am["codigo_amostra"].map(resultados_lab).fillna("")
df_am["inconclusiva"] = df_am["registrada_lab"] & (df_am["resultado_lab"] == "inconclusivo") & ~df_am["positiva"]
df_am["analisada"] = df_am["registrada_lab"] & ~df_am["inconclusiva"]
df_am["pendente"] = ~df_am["registrada_lab"]
df_am["qtd_total"] = pd.to_numeric(df_am["qtd_total"], errors="coerce").fillna(0)
df_am["qtd_alvo"] = pd.to_numeric(df_am["qtd_alvo"], errors="coerce").fillna(0)

df_vis_loc = df_visitas.groupby