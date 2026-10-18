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
    return pd.DataFrame(registros) if registros else pd.DataFrame()

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

def preparar_campo(df_campo: pd.DataFrame) -> pd.DataFrame:
    if df_campo.empty: return df_campo
    
    df_plantas = []
    for _, row in df_campo.iterrows():
        # Extrai os dados base da planta
        planta = {
            "id_bromelia_calc": row.get("grp_cadastro/id_bromelia_calc"),
            "bairro": row.get("grp_cadastro/bairro"),
            "genero": row.get("grp_cadastro/genero"),
            "data_cadastro": row.get("grp_cadastro/data_cadastro"),
            "latitude": None,
            "longitude": None,
            "visitas": [],
            "amostras": []
        }
        
        # Extrai coordenadas
        geo = row.get("grp_cadastro/geolocalizacao")
        if isinstance(geo, str) and " " in geo:
            partes = geo.split()
            try:
                planta["latitude"] = float(partes[0])
                planta["longitude"] = float(partes[1])
            except:
                pass

        # Extrai as visitas (lista de dicionários)
        if isinstance(row.get("rep_visitas"), list):
            planta["visitas"] = row["rep_visitas"]
            
        # Extrai as amostras (lista de dicionários)
        if isinstance(row.get("rep_amostras"), list):
            planta["amostras"] = row["rep_amostras"]

        df_plantas.append(planta)
        
    return pd.DataFrame(df_plantas)

def preparar_lab(df_lab: pd.DataFrame) -> pd.DataFrame:
    if df_lab.empty: return df_lab
    
    df_especies = []
    for _, row in df_lab.iterrows():
        amostra_codigo = row.get("id_amostra_lab")
        if not amostra_codigo:
            # Tenta achar em outra coluna caso o Kobo mude o nome
            for k, v in row.items():
                if "Código da amostra" in k and isinstance(v, str):
                    amostra_codigo = v
                    break
        
        especies_lista = row.get("rep_especies")
        if isinstance(especies_lista, list):
            for esp in especies_lista:
                if isinstance(esp, dict):
                    esp["id_amostra_lab"] = amostra_codigo
                    esp["resultado_amostra"] = row.get("resultado_amostra")
                    df_especies.append(esp)
                    
    return pd.DataFrame(df_especies)

def cruzar_campo_lab(df_campo: pd.DataFrame, df_lab: pd.DataFrame) -> pd.DataFrame:
    if df_campo.empty: return df_campo
    if df_lab.empty: 
        df_campo["especie_identificada"] = None
        df_campo["resultado_amostra"] = None
        return df_campo

    # Expande as amostras da planta
    df_amostras_expandidas = df_campo.explode("amostras").reset_index()
    
    # Extrai o ID da amostra de dentro do dicionário
    def pegar_id_amostra(x):
        if isinstance(x, dict): return x.get("id_amostra_calc")
        return None
    df_amostras_expandidas["id_amostra_calc"] = df_amostras_expandidas["amostras"].apply(pegar_id_amostra)
    
    # Faz o merge com o laboratório
    df_merge = df_amostras_expandidas.merge(
        df_lab, 
        left_on="id_amostra_calc", 
        right_on="id_amostra_lab", 
        how="left"
    )
    return df_merge