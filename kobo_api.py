import os
import requests
import pandas as pd
import streamlit as st

def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)

def baixar_formulario(uid: str, token: str, base_url: str) -> list:
    """Baixa os dados e retorna a lista bruta (JSON) para não perder a estrutura."""
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

def preparar_dados_completos(lista_campo: list, lista_lab: list):
    """Transforma as listas aninhadas em um único DataFrame plano e pronto para gráficos."""
    if not lista_campo:
        return pd.DataFrame()

    plantas = []
    amostras_flat = []

    for item in lista_campo:
        cadastro = item.get("grp_cadastro", {})
        id_planta = cadastro.get("id_bromelia_calc", "Sem ID")
        
        # Coordenadas
        geo = cadastro.get("geolocalizacao", "")
        lat, lon = None, None
        if isinstance(geo, str) and " " in geo:
            try:
                partes = geo.split()
                lat, lon = float(partes[0]), float(partes[1])
            except:
                pass

        # Dados base da planta
        planta_base = {
            "id_bromelia_calc": id_planta,
            "bairro": cadastro.get("bairro", "Não informado"),
            "genero": cadastro.get("genero", "Não informado"),
            "latitude": lat,
            "longitude": lon,
            "data_cadastro": cadastro.get("data_cadastro")
        }
        plantas.append(planta_base)

        # Processa Visitas e Amostras
        visitas = item.get("rep_visitas", [])
        if isinstance(visitas, list):
            for v in visitas:
                visita_info = {
                    "id_bromelia_calc": id_planta,
                    "data_visita": v.get("data_visita"),
                    "presenca_imaturos": v.get("presenca_imaturos")
                }
                
                amostras = v.get("rep_amostras", [])
                if isinstance(amostras, list):
                    for a in amostras:
                        amostra_info = visita_info.copy()
                        amostra_info.update({
                            "id_amostra_calc": a.get("id_amostra_calc"),
                            "data_visita": v.get("data_visita") # Garante a data
                        })
                        amostras_flat.append(amostra_info)

    # Cria o DataFrame de Plantas
    df_plantas = pd.DataFrame(plantas)
    
    # Cria o DataFrame de Amostras
    df_amostras = pd.DataFrame(amostras_flat) if amostras_flat else pd.DataFrame(columns=["id_bromelia_calc", "data_visita", "presenca_imaturos", "id_amostra_calc"])

    # Processa o Laboratório
    lab_especies = []
    for item in lista_lab:
        id_amostra = item.get("id_amostra_lab", "")
        resultado = item.get("resultado_amostra", "")
        
        especies = item.get("rep_especies", [])
        if isinstance(especies, list):
            for e in especies:
                lab_especies.append({
                    "id_amostra_calc": id_amostra,
                    "especie_identificada": e.get("especie_identificada", "Não identificado"),
                    "qtd_larvas": e.get("qtd_larvas", 0),
                    "soma_contagem": e.get("soma_contagem", 0),
                    "resultado_amostra": resultado
                })
                
    df_lab = pd.DataFrame(lab_especies) if lab_especies else pd.DataFrame(columns=["id_amostra_calc", "especie_identificada", "qtd_larvas", "soma_contagem", "resultado_amostra"])

    # Cruza Amostras com Laboratório
    if not df_amostras.empty:
        df_final = df_amostras.merge(df_lab, on="id_amostra_calc", how="left")
    else:
        df_final = df_plantas.copy()
        df_final["id_amostra_calc"] = None
        df_final["presenca_imaturos"] = None
        df_final["especie_identificada"] = None
        df_final["resultado_amostra"] = None

    # Para o dashboard não perder as plantas que não têm visita, podemos usar o df_plantas para o mapa.
    # Mas o df_final serve para os KPIs e tabelas.
    
    return df_plantas, df_final