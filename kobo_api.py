"""
Módulo de conexão com a API do KoboToolbox.
Baixa os dados dos formulários de campo e de laboratório.
"""

import os
import requests
import pandas as pd
import streamlit as st


def _get_secret(key: str, default: str = "") -> str:
    """Lê segredos do Streamlit ou variáveis de ambiente."""
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)


def baixar_formulario(uid: str, token: str, base_url: str) -> pd.DataFrame:
    """Baixa todos os envios de um formulário do Kobo como DataFrame."""
    if not uid:
        return pd.DataFrame()
        
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
        params = {}  # já vem na URL de próximo

    if not registros:
        return pd.DataFrame()

    # Normaliza o JSON, separando os grupos e repeats com "/"
    df = pd.json_normalize(registros, sep="/")
    return df


def carregar_dados():
    """Carrega os dois formulários (campo e laboratório)."""
    base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
    token = _get_secret("KOBO_TOKEN")
    uid_campo = _get_secret("UID_CAMPO")
    uid_lab = _get_secret("UID_LAB")

    if not token or not uid_campo:
        st.error("⚠️ Configure KOBO_TOKEN e UID_CAMPO em .streamlit/secrets.toml")
        st.stop()

    with st.spinner("Baixando dados do KoboToolbox..."):
        df_campo = baixar_formulario(uid_campo, token, base_url)
        df_lab = baixar_formulario(uid_lab, token, base_url)

    return df_campo, df_lab


def achatar_repeats(df: pd.DataFrame) -> pd.DataFrame:
    """Achata listas aninhadas (repeats do Kobo) em linhas."""
    if df.empty:
        return df

    # Encontra colunas que contêm listas (repeats)
    colunas_repeat = [c for c in df.columns if df[c].apply(lambda x: isinstance(x, list)).any()]

    if not colunas_repeat:
        return df

    df_expandido = df.copy()
    
    for col in colunas_repeat:
        novas_linhas = []
        for _, row in df_expandido.iterrows():
            row_dict = row.to_dict()
            lista_itens = row_dict.pop(col, None)
            
            if not isinstance(lista_itens, list) or len(lista_itens) == 0:
                novas_linhas.append(row_dict)
                continue
                
            for item in lista_itens:
                nova_linha = row_dict.copy()
                if isinstance(item, dict):
                    for k, v in item.items():
                        nova_linha[f"{col}/{k}"] = v
                novas_linhas.append(nova_linha)
                
        df_expandido = pd.DataFrame(novas_linhas)

    return df_expandido


def preparar_campo(df_campo: pd.DataFrame) -> pd.DataFrame:
    """Prepara o DataFrame do formulário de campo."""
    if df_campo.empty:
        return df_campo

    # Achata visitas e amostras
    df = achatar_repeats(df_campo)

    # Coordenadas (o Kobo salva como "lat lon altitude precisão")
    col_geo = "grp_cadastro/geolocalizacao"
    if col_geo in df.columns:
        def extrair_coords(valor):
            if isinstance(valor, str) and " " in valor:
                partes = valor.split()
                try:
                    return float(partes[0]), float(partes[1])
                except (ValueError, IndexError):
                    return None, None
            return None, None

        df["latitude"], df["longitude"] = zip(*df[col_geo].apply(extrair_coords))

    return df


def preparar_lab(df_lab: pd.DataFrame) -> pd.DataFrame:
    """Prepara o DataFrame do formulário de laboratório."""
    if df_lab.empty:
        return df_lab

    df = achatar_repeats(df_lab)
    return df


def cruzar_campo_lab(df_campo: pd.DataFrame, df_lab: pd.DataFrame) -> pd.DataFrame:
    """Faz o JOIN entre campo e laboratório pelo código da amostra."""
    if df_campo.empty:
        return df_campo

    col_campo = "rep_amostras/id_amostra_calc"
    
    if df_lab.empty or col_campo not in df_campo.columns:
        return df_campo

    # No laboratório, o código pode estar com ou sem prefixo do grupo
    if "id_amostra_lab" in df_lab.columns:
        col_lab = "id_amostra_lab"
    elif "grp_amostra/id_amostra_lab" in df_lab.columns:
        col_lab = "grp_amostra/id_amostra_lab"
    else:
        return df_campo

    df_lab_renomeado = df_lab.rename(columns={col_lab: col_campo})

    df_merge = df_campo.merge(
        df_lab_renomeado,
        on=col_campo,
        how="left",
        suffixes=("", "_lab")
    )
    return df_merge