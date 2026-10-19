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
    # 1. Processa o formulário de CAMPO
    dados = []
    for item in lista_campo:
        id_planta = item.get("grp_cadastro/id_bromelia_calc") or "Sem ID"
        bairro = item.get("grp_cadastro/bairro") or "Não informado"
        genero = item.get("grp_cadastro/genero") or "Não informado"
        
        # Extrai lat/lon
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
                        dados.append({
                            "id_bromelia_calc": id_planta, "bairro": bairro, "genero": genero, "latitude": lat, "longitude": lon,
                            "data_visita": data_visita, "presenca_imaturos": presenca, "id_amostra_calc": id_amostra,
                            "volume_agua_ml": vol_agua, "temp_agua_c": temp_agua, "ph_agua": ph_agua, "observacoes_visita": obs_visita
                        })
                else:
                    dados.append({
                        "id_bromelia_calc": id_planta, "bairro": bairro, "genero": genero, "latitude": lat, "longitude": lon,
                        "data_visita": data_visita, "presenca_imaturos": presenca, "id_amostra_calc": None,
                        "volume_agua_ml": vol_agua, "temp_agua_c": temp_agua, "ph_agua": ph_agua, "observacoes_visita": obs_visita
                    })

    # 2. Processa o formulário de LABORATÓRIO
    lab_dict = {}
    for item in lista_lab:
        id_amostra = item.get("grp_amostra/id_amostra_lab")
        if not id_amostra: continue
            
        resultado_digitado = item.get("grp_resultado/resultado_amostra") or "nao_processado"
        obs_lab = item.get("grp_resultado/observacoes_lab")
        
        especies = item.get("rep_especies", [])
        if isinstance(especies, list):
            for e in especies:
                especie_bruta = e.get("rep_especies/especie_identificada") or "nao_identificado"
                especie = str(especie_bruta).lower().strip().replace(" ", "_")
                
                soma_contagem = e.get("rep_especies/soma_contagem")
                try: soma_contagem = int(float(soma_contagem)) if soma_contagem else 0
                except: soma_contagem = 0

                resultado_real = "Positivo (Aedes)" if "aedes" in especie else "Negativo (Outros)"

                # Guarda a primeira espécie encontrada (ou a última, não importa muito para o merge básico)
                lab_dict[id_amostra] = {
                    "especie_identificada": especie,
                    "soma_contagem": soma_contagem,
                    "resultado_digitado": resultado_digitado,
                    "resultado_real": resultado_real,
                    "observacoes_lab": obs_lab
                }

    # 3. Junta os dados sem usar merge do pandas (mais seguro)
    for d in dados:
        id_am = d.get("id_amostra_calc")
        if id_am in lab_dict:
            lab_info = lab_dict[id_am]
            d["especie_identificada"] = lab_info["especie_identificada"]
            d["soma_contagem"] = lab_info["soma_contagem"]
            d["resultado_digitado"] = lab_info["resultado_digitado"]
            d["resultado_real"] = lab_info["resultado_real"]
            d["observacoes_lab"] = lab_info["observacoes_lab"]
        else:
            d["especie_identificada"] = None
            d["soma_contagem"] = 0
            d["resultado_digitado"] = "nao_processado"
            d["resultado_real"] = "Nenhum"
            d["observacoes_lab"] = None

    df_final = pd.DataFrame(dados)
    
    # Retorna também um df_plantas simulado (opcional para o app, mas o app precisa)
    df_plantas = df_final[["id_bromelia_calc", "bairro", "genero", "latitude", "longitude"]].drop_duplicates(subset=["id_bromelia_calc"]) if not df_final.empty else pd.DataFrame()

    return df_plantas, df_final