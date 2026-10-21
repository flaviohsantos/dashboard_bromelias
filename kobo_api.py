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
    if not uid: return []
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
        id_planta = item.get("grp_cadastro/id_bromelia_calc") or item.get("Código único da planta") or "Sem ID"
        bairro = item.get("grp_cadastro/bairro") or item.get("Bairro") or "Não informado"
        genero = item.get("grp_cadastro/genero") or item.get("Gênero da bromélia") or "Não informado"
        
        geo = item.get("grp_cadastro/geolocalizacao") or item.get("Geolocalização da planta")
        lat, lon = None, None
        if isinstance(geo, str) and " " in geo:
            try:
                partes = geo.split()
                lat, lon = float(partes[0]), float(partes[1])
            except: pass
        
        plantas.append({"id_bromelia": id_planta, "bairro": bairro, "genero": genero, "lat": lat, "lon": lon})

        visitas = item.get("rep_visitas", [])
        if isinstance(visitas, list):
            for v in visitas:
                amostras = v.get("rep_amostras", [])
                if isinstance(amostras, list):
                    for a in amostras:
                        # Pega o código da amostra que liga ao laboratório
                        id_amostra = a.get("codigo_amostra") or a.get("id_amostra_calc")
                        if id_amostra:
                            dados_tabela.append({
                                "id_bromelia": id_planta,
                                "codigo_amostra": str(id_amostra).strip()
                            })

    # 2. Processa o formulário de LABORATÓRIO
    lab_especies = []
    for item in lista_lab:
        # Pega o código da amostra no lab
        id_amostra_lab = item.get("grp_amostra/codigo_amostra") or item.get("Código da amostra (Ex: BRO-2610181726-30)") or item.get("Código da amostra")
        if not id_amostra_lab: continue
        
        especies = item.get("rep_especies", [])
        if isinstance(especies, list):
            for e in especies:
                # Pega a espécie e a quantidade de larvas
                especie = e.get("rep_especies/especie_identificada") or e.get("Espécie identificada") or "nao_identificado"
                qtd = e.get("rep_especies/qtd_larvas") or e.get("Qtd. de larvas") or 0
                
                lab_especies.append({
                    "codigo_amostra": str(id_amostra_lab).strip(),
                    "especie": str(especie).lower().strip().replace(" ", "_"),
                    "qtd_larvas": int(float(qtd)) if qtd else 0
                })
    
    df_plantas = pd.DataFrame(plantas)
    df_dados = pd.DataFrame(dados_tabela) if dados_tabela else pd.DataFrame(columns=["id_bromelia", "codigo_amostra"])
    df_lab = pd.DataFrame(lab_especies) if lab_especies else pd.DataFrame(columns=["codigo_amostra", "especie", "qtd_larvas"])

    # Junta campo com lab
    if not df_dados.empty and not df_lab.empty:
        df_merge = pd.merge(df_dados, df_lab, on="codigo_amostra", how="left")
    else:
        df_merge = df_dados.copy()
        df_merge["especie"] = None
        df_merge["qtd_larvas"] = 0

    # Agrupa por planta
    if not df_merge.empty:
        df_final = df_merge.groupby("id_bromelia").agg({
            "especie": lambda x: list(x.dropna().unique()),
            "qtd_larvas": "sum"
        }).reset_index()
    else:
        df_final = df_plantas.copy()
        df_final["especie"] = None
        df_final["qtd_larvas"] = 0

    return df_plantas, df_final
