"""
Módulo de conexão com a API do KoboToolbox.
"""

import os
import requests
import pandas as pd
import streamlit as st

def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)

def baixar_formulario(uid: str, token: str, base_url: str) -> pd.DataFrame:
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
        params = {}

    if not registros:
        return pd.DataFrame()

    df = pd.json_normalize(registros, sep="/")
    return df

def carregar_dados():
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
    """Achata listas aninhadas de forma segura usando loop (sem json_normalize)."""
    if df.empty:
        return df

    colunas_repeat = [c for c in df.columns if df[c].apply(lambda x: isinstance(x, list)).any()]

    if not colunas_repeat:
        return df

    df_expandido = df.copy()
    
    for col in colunas_repeat:
        novas_linhas = []
        
        for _, row in df_expandido.iterrows():
            row_dict = row.to_dict()
            lista_itens = row_dict.pop(col, None)
            
            # Se a lista for vazia ou inválida (None/NaN), mantém a linha original
            if not isinstance(lista_itens, list) or len(lista_itens) == 0:
                novas_linhas.append(row_dict)
                continue
                
            # Se for lista, expande cada item
            for item in lista_itens:
                nova_linha = row_dict.copy()
                if isinstance(item, dict):
                    for k, v in item.items():
                        nova_linha[f"{col}/{k}"] = v
                novas_linhas.append(nova_linha)
                
        df_expandido = pd.DataFrame(novas_linhas)

    return df_expandido

def preparar_campo(df_campo: pd.DataFrame) -> pd.DataFrame:
    if df_campo.empty:
        return df_campo
    df = achatar_repeats(df_campo)

    # Extrai lat/lon
    if "grp_cadastro/geolocalizacao" in df.columns:
        def extrair_coords(valor):
            if isinstance(valor, str) and " " in valor:
                partes = valor.split()
                try:
                    return float(partes[0]), float(partes[1])
                except:
                    return None, None
            return None, None
        df["latitude"], df["longitude"] = zip(*df["grp_cadastro/geolocalizacao"].apply(extrair_coords))

    return df

def preparar_lab(df_lab: pd.DataFrame) -> pd.DataFrame:
    if df_lab.empty:
        return df_lab
    return achatar_repeats(df_lab)

def cruzar_campo_lab(df_campo: pd.DataFrame, df_lab: pd.DataFrame) -> pd.DataFrame:
    if df_campo.empty:
        return df_campo

    col_campo = "rep_amostras/id_amostra_calc"
    
    if df_lab.empty or col_campo not in df_campo.columns:
        return df_campo

    # Identifica onde está o código no lab
    if "id_amostra_lab" in df_lab.columns:
        col_lab = "id_amostra_lab"
    elif "grp_amostra/id_amostra_lab" in df_lab.columns:
        col_lab = "grp_amostra/id_amostra_lab"
    else:
        # Se não achou, tenta pegar pelo nome do label (como está no seu Excel)
        colunas_possiveis = [c for c in df_lab.columns if "Código da amostra" in c]
        if colunas_possiveis:
            col_lab = colunas_possiveis[0]
        else:
            return df_campo

    df_lab_renomeado = df_lab.rename(columns={col_lab: col_campo})
    
    # Faz o merge
    df_merge = df_campo.merge(
        df_lab_renomeado,
        on=col_campo,
        how="left",
        suffixes=("", "_lab")
    )
    return df_merge