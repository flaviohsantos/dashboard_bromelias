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
        id_planta = item.get("grp_cadastro/id_bromelia_calc") or "Sem ID"
        bairro = item.get("grp_cadastro/bairro") or "Não informado"
        genero = item.get("grp_cadastro/genero") or "Não informado"
        
        geo = item.get("grp_cadastro/geolocalizacao")
        lat, lon = None, None
        if isinstance(geo, str) and " " in geo:
            try:
                partes = geo.split()
                lat, lon = float(partes[0]), float(partes[1])
            except: pass
        
        plantas.append({"id_bromelia_calc": id_planta, "bairro": bairro, "genero": genero, "latitude": lat, "longitude": lon})

        visitas = item.get("rep_visitas", [])
        if isinstance(visitas, list):
            for v in visitas:
                data_visita = v.get("rep_visitas/data_visita")
                presenca = v.get("rep_visitas/presenca_imaturos")
                vol_agua = v.get("rep_visitas/volume_agua_ml")
                temp_agua = v.get("rep_visitas/temp_agua_c")
                ph_agua = v.get("rep_visitas/ph_agua")
                obs_visita = v.get("rep_visitas/observacoes_visita") or v.get("observacoes_visita")
                
                amostras = v.get("rep_visitas/rep_amostras", [])
                if isinstance(amostras, list) and len(amostras) > 0:
                    for a in amostras:
                        id_amostra = a.get("rep_visitas/rep_amostras/id_amostra_calc") or a.get("id_amostra_calc")
                        # Limpa espaços em branco no ID da amostra
                        id_amostra = str(id_amostra).strip() if id_amostra else None
                        
                        dados_tabela.append({
                            "id_bromelia_calc": id_planta, "bairro": bairro, "genero": genero,
                            "data_visita": data_visita, "presenca_imaturos": presenca,
                            "id_amostra_calc": id_amostra,
                            "volume_agua_ml": vol_agua, "temp_agua_c": temp_agua, "ph_agua": ph_agua,
                            "observacoes_visita": obs_visita
                        })
                else:
                    dados_tabela.append({
                        "id_bromelia_calc": id_planta, "bairro": bairro, "genero": genero,
                        "data_visita": data_visita, "presenca_imaturos": presenca,
                        "id_amostra_calc": None,
                        "volume_agua_ml": vol_agua, "temp_agua_c": temp_agua, "ph_agua": ph_agua,
                        "observacoes_visita": obs_visita
                    })

    # 2. Processa o formulário de LABORATÓRIO
    lab_especies = []
    for item in lista_lab:
        id_amostra = item.get("grp_amostra/id_amostra_lab") or item.get("id_amostra_lab")
        # Limpa espaços em branco no ID da amostra do laboratório
        id_amostra = str(id_amostra).strip() if id_amostra else None
        
        if not id_amostra: continue
            
        resultado_digitado = item.get("grp_resultado/resultado_amostra") or "nao_processado"
        obs_lab = item.get("grp_resultado/observacoes_lab")
        
        especies = item.get("rep_especies", [])
        if isinstance(especies, list):
            for e in especies:
                especie_bruta = e.get("rep_especies/especie_identificada") or "nao_identificado"
                # Limpa espaços em branco e formata
                especie_formatada = str(especie_bruta).lower().strip().replace(" ", "_")
                
                soma_contagem = e.get("rep_especies/soma_contagem")
                try: soma_contagem = int(float(soma_contagem)) if soma_contagem else 0
                except: soma_contagem = 0

                resultado_real = "Positivo (Aedes)" if "aedes" in especie_formatada else "Negativo (Outros)"

                lab_especies.append({
                    "id_amostra_calc": id_amostra,
                    "especie_identificada": especie_formatada,
                    "soma_contagem": soma_contagem,
                    "resultado_digitado": resultado_digitado,
                    "resultado_real": resultado_real,
                    "observacoes_lab": obs_lab
                })
    
    # 3. Criando DataFrames
    df_plantas = pd.DataFrame(plantas)
    df_dados = pd.DataFrame(dados_tabela) if dados_tabela else pd.DataFrame(columns=["id_bromelia_calc", "bairro", "genero", "data_visita", "presenca_imaturos", "id_amostra_calc", "volume_agua_ml", "temp_agua_c", "ph_agua", "observacoes_visita"])
    df_lab = pd.DataFrame(lab_especies) if lab_especies else pd.DataFrame(columns=["id_amostra_calc", "especie_identificada", "soma_contagem", "resultado_digitado", "resultado_real", "observacoes_lab"])

    # 4. Cruzando os dados (Merge)
    if not df_dados.empty and not df_lab.empty:
        df_final = pd.merge(df_dados, df_lab, on="id_amostra_calc", how="left")
    else:
        df_final = df_dados.copy()
        for col in ["especie_identificada", "soma_contagem", "resultado_digitado", "resultado_real", "observacoes_lab"]:
            df_final[col] = None

    return df_plantas, df_final