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
    # Processa o CAMPO (Planta e Visitas)
    dados = []
    for item in lista_campo:
        id_planta = str(item.get("grp_cadastro/id_bromelia_calc") or "Sem ID").strip()
        bairro = item.get("grp_cadastro/bairro") or "Não informado"
        genero = item.get("grp_cadastro/genero") or "Não informado"
        
        geo = item.get("grp_cadastro/geolocalizacao", "")
        lat, lon = None, None
        if isinstance(geo, str) and " " in geo:
            try:
                partes = geo.split()
                lat, lon = float(partes[0]), float(partes[1])
            except: pass

        visitas = item.get("rep_visitas", [])
        if isinstance(visitas, list):
            for v in visitas:
                data_visita = v.get("rep_visitas/data_visita")
                presenca = v.get("rep_visitas/presenca_imaturos")
                vol_agua = v.get("rep_visitas/volume_agua_ml")
                temp_agua = v.get("rep_visitas/temp_agua_c")
                ph_agua = v.get("rep_visitas/ph_agua")
                obs_visita = v.get("rep_visitas/observacoes_visita")
                
                amostras = v.get("rep_visitas/rep_amostras", [])
                if isinstance(amostras, list) and len(amostras) > 0:
                    for a in amostras:
                        id_amostra = a.get("rep_visitas/rep_amostras/id_amostra_calc") or a.get("id_amostra_calc")
                        id_amostra = str(id_amostra).strip() if id_amostra else None
                        dados.append({
                            "id_bromelia_calc": id_planta, "bairro": bairro, "genero": genero, "latitude": lat, "longitude": lon,
                            "data_visita": data_visita, "presenca_imaturos": presenca, "id_amostra_calc": id_amostra,
                            "volume_agua_ml": vol_agua, "temp_agua_c": temp_agua, "ph_agua": ph_agua, "observacoes_visita": obs_visita,
                            "especie_identificada": None, "soma_contagem": 0, "resultado_digitado": "nao_processado", "resultado_real": "Nenhum", "observacoes_lab": None
                        })

    # Processa o LABORATÓRIO
    lab_dict = {}
    for item in lista_lab:
        id_amostra = str(item.get("grp_amostra/id_amostra_lab") or "").strip()
        if not id_amostra: continue
            
        resultado_digitado = item.get("grp_resultado/resultado_amostra") or "nao_processado"
        obs_lab = item.get("grp_resultado/observacoes_lab")
        
        especies = item.get("rep_especies", [])
        if isinstance(especies, list):
            for e in especies:
                especie_bruta = e.get("rep_especies/especie_identificada") or "nao_identificado"
                especie = str(especie_bruta).lower().strip().replace(" ", "_")
                
                soma = e.get("rep_especies/soma_contagem")
                try: soma = int(float(soma)) if soma else 0
                except: soma = 0

                resultado_real = "Positivo (Aedes)" if "aedes" in especie else "Negativo (Outros)"

                lab_dict[id_amostra] = {
                    "especie_identificada": especie,
                    "soma_contagem": soma,
                    "resultado_digitado": resultado_digitado,
                    "resultado_real": resultado_real,
                    "observacoes_lab": obs_lab
                }

    # Cruza os dados
    for d in dados:
        id_am = d.get("id_amostra_calc")
        if id_am and id_am in lab_dict:
            d.update(lab_dict[id_am])

    df_final = pd.DataFrame(dados) if dados else pd.DataFrame()
    df_plantas = df_final[["id_bromelia_calc", "bairro", "genero", "latitude", "longitude"]].drop_duplicates(subset=["id_bromelia_calc"]) if not df_final.empty else pd.DataFrame()

    return df_plantas, df_final