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
    plantas = []
    dados_tabela = []

    # 1. Processa o formulário de CAMPO
    for item in lista_campo:
        # O Kobo coloca os dados dos grupos dentro de um dicionário
        cadastro = item.get("grp_cadastro", {})
        
        id_planta = cadastro.get("id_bromelia_calc") or "Sem ID"
        bairro = cadastro.get("bairro") or "Não informado"
        genero = cadastro.get("genero") or "Não informado"
        
        # Extrai coordenadas
        geo = cadastro.get("geolocalizacao")
        lat, lon = None, None
        if isinstance(geo, str) and " " in geo:
            try:
                partes = geo.split()
                lat, lon = float(partes[0]), float(partes[1])
            except:
                pass
        
        plantas.append({
            "id_bromelia_calc": id_planta,
            "bairro": bairro,
            "genero": genero,
            "latitude": lat,
            "longitude": lon
        })

        # 2. Processa as VISITAS (é uma lista dentro do formulário)
        visitas = item.get("rep_visitas", [])
        if isinstance(visitas, list):
            for v in visitas:
                # Formata a data para ficar amigável
                data_visita = v.get("data_visita")
                data_formatada = pd.to_datetime(data_visita).date() if data_visita else None
                
                presenca = v.get("presenca_imaturos")
                
                # 3. Processa as AMOSTRAS (lista dentro da visita)
                amostras = v.get("rep_amostras", [])
                if isinstance(amostras, list) and len(amostras) > 0:
                    for a in amostras:
                        dados_tabela.append({
                            "id_bromelia_calc": id_planta,
                            "bairro": bairro,
                            "genero": genero,
                            "data_visita": data_formatada,
                            "presenca_imaturos": presenca,
                            "id_amostra_calc": a.get("id_amostra_calc")
                        })
                else:
                    dados_tabela.append({
                        "id_bromelia_calc": id_planta,
                        "bairro": bairro,
                        "genero": genero,
                        "data_visita": data_formatada,
                        "presenca_imaturos": presenca,
                        "id_amostra_calc": None
                    })

    # 4. Processa o formulário de LABORATÓRIO
    lab_especies = []
    for item in lista_lab:
        # O código no lab está dentro do grupo 'grp_amostra'
        grupo_amostra = item.get("grp_amostra", {})
        id_amostra = grupo_amostra.get("id_amostra_lab") or "Sem ID"
        
        resultado = item.get("resultado_amostra")
        
        # As espécies vêm em uma lista 'rep_especies'
        especies = item.get("rep_especies", [])
        if isinstance(especies, list):
            for e in especies:
                lab_especies.append({
                    "id_amostra_calc": id_amostra,
                    "especie_identificada": e.get("especie_identificada") or "Não informado",
                    "soma_contagem": e.get("soma_contagem") or 0,
                    "resultado_amostra": resultado
                })
    
    df_plantas = pd.DataFrame(plantas)
    df_dados = pd.DataFrame(dados_tabela) if dados_tabela else pd.DataFrame(columns=["id_bromelia_calc", "bairro", "genero", "data_visita", "presenca_imaturos", "id_amostra_calc"])
    df_lab = pd.DataFrame(lab_especies) if lab_especies else pd.DataFrame(columns=["id_amostra_calc", "especie_identificada", "soma_contagem", "resultado_amostra"])

    # Junta os dados de campo com os de laboratório pelo ID da amostra
    if not df_dados.empty and "id_amostra_calc" in df_dados.columns:
        df_final = df_dados.merge(df_lab, on="id_amostra_calc", how="left")
    else:
        df_final = df_dados.copy()
        df_final["especie_identificada"] = None
        df_final["soma_contagem"] = None
        df_final["resultado_amostra"] = None

    return df_plantas, df_final