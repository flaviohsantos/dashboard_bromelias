# -*- coding: utf-8 -*-
import re
import unicodedata
import requests
import pandas as pd
import streamlit as st

def _get_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        import os
        return os.environ.get(key, default)

@st.cache_data(ttl=300, show_spinner=False)
def baixar_formulario(uid, token, base_url):
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

def normalizar_texto(valor):
    if valor is None: return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().replace("_", " ").strip().split())

def normalizar_codigo(valor):
    return re.sub(r"\s+", "", str(valor)).upper().replace("–", "-").replace("—", "-")

def numero_inteiro(valor):
    if valor is None or str(valor).strip() == "": return 0
    try: return max(0, int(float(str(valor).strip().replace(",", "."))))
    except (ValueError, TypeError): return 0

def para_numero(serie):
    return pd.to_numeric(serie.astype(str).str.replace(",", ".", regex=False), errors="coerce")

def pct(num, den):
    return (num / den.where(den > 0) * 100).round(1)

@st.cache_data(ttl=300, show_spinner=False)
def carregar_e_processar_dados():
    base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
    token = _get_secret("KOBO_TOKEN")
    uid_campo = _get_secret("UID_CAMPO")
    uid_lab = _get_secret("UID_LAB")
    uid_visita = _get_secret("UID_VISITA")

    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_visita = baixar_formulario(uid_visita, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)

    if not lista_campo:
        return None

    locais, visitas_list, amostras = [], [], []
    for indice, item in enumerate(lista_campo):
        id_local = normalizar_codigo(item.get("grp_cadastro/id_local_calc") or "") or f"SEM-ID-{indice}"
        bairro = item.get("grp_cadastro/bairro") or "N/I"
        tipologia = item.get("grp_cadastro/tipologia_imovel") or "N/I"
        geo = item.get("grp_cadastro/geolocalizacao", "")
        lat, lon = None, None
        if isinstance(geo, str) and " " in geo:
            try: lat, lon = float(geo.split()[0]), float(geo.split()[1])
            except ValueError: pass
        locais.append({"id_local": id_local, "bairro": bairro, "tipologia": tipologia, "lat": lat, "lon": lon})

        visitas = item.get("rep_visitas", [])
        if not isinstance(visitas, list): continue
        for n_visita, v in enumerate(visitas):
            id_visita = f"{indice}-{n_visita}"
            data_v = v.get("rep_visitas/data_visita")
            visitas_list.append({"id_visita": id_visita, "id_local": id_local, "data_visita": data_v,
                "n_exam": v.get("rep_visitas/qtd_bromelias_examinadas"), "n_secas": v.get("rep_visitas/qtd_secas"),
                "n_agua_sem": v.get("rep_visitas/qtd_agua_sem_imaturos")})
            ams = v.get("rep_visitas/rep_amostras", [])
            if not isinstance(ams, list): continue
            for a in ams:
                cod = a.get("rep_visitas/rep_amostras/codigo_amostra")
                if cod and str(cod).strip():
                    amostras.append({"id_visita": id_visita, "id_local": id_local, "codigo_amostra": normalizar_codigo(cod),
                        "data_visita": data_v, "ph": a.get("rep_visitas/rep_amostras/ph_agua"), "temp": a.get("rep_visitas/rep_amostras/temp_agua_c"),
                        "vol": a.get("rep_visitas/rep_amostras/volume_agua_ml"), "genero": a.get("rep_visitas/rep_amostras/genero") or "N/I",
                        "porte": a.get("rep_visitas/rep_amostras/porte") or "N/I"})

    locais_via_visita = {}
    for indice, item in enumerate(lista_visita):
        id_local = normalizar_codigo(item.get("grp_identificacao/id_bromelia_visita") or "")
        if not id_local: continue
        id_visita = f"V{indice}"
        data_v = item.get("grp_dados_visita/data_visita")
        visitas_list.append({"id_visita": id_visita, "id_local": id_local, "data_visita": data_v,
            "n_exam": item.get("grp_dados_visita/qtd_bromelias_examinadas"), "n_secas": item.get("grp_dados_visita/qtd_secas"),
            "n_agua_sem": item.get("grp_dados_visita/qtd_agua_sem_imaturos")})
        try: lat_v, lon_v = float(item.get("grp_identificacao/latitude")), float(item.get("grp_identificacao/longitude"))
        except (TypeError, ValueError): lat_v, lon_v = None, None
        locais_via_visita.setdefault(id_local, {"bairro": item.get("grp_identificacao/bairro") or "N/I", "lat": lat_v, "lon": lon_v})
        for a in item.get("rep_amostras", []) or []:
            cod = a.get("rep_amostras/codigo_amostra")
            if cod and str(cod).strip():
                amostras.append({"id_visita": id_visita, "id_local": id_local, "codigo_amostra": normalizar_codigo(cod),
                    "data_visita": data_v, "ph": a.get("rep_amostras/ph_agua"), "temp": a.get("rep_amostras/temp_agua_c"),
                    "vol": a.get("rep_amostras/volume_agua_ml"), "genero": a.get("rep_amostras/genero") or "N/I", "porte": a.get("rep_amostras/porte") or "N/I"})

    COLS_AM = ["id_visita", "id_local", "codigo_amostra", "data_visita", "ph", "temp", "vol", "genero", "porte"]
    df_locais_bruto = pd.DataFrame(locais, columns=["id_local", "bairro", "tipologia", "lat", "lon"])
    codigos_visita_sem_cadastro = sorted(set(locais_via_visita) - set(df_locais_bruto["id_local"]))
    if codigos_visita_sem_cadastro:
        df_extra = pd.DataFrame([{"id_local": c, "bairro": locais_via_visita[c]["bairro"], "tipologia": "N/I", "lat": locais_via_visita[c]["lat"], "lon": locais_via_visita[c]["lon"]} for c in codigos_visita_sem_cadastro])
        df_locais_bruto = pd.concat([df_locais_bruto, df_extra], ignore_index=True)
    
    df_amostras_bruto = pd.DataFrame(amostras, columns=COLS_AM)
    ids_locais_duplicados = sorted(df_locais_bruto.loc[df_locais_bruto["id_local"].duplicated(), "id_local"].unique())
    codigos_campo_duplicados = sorted(df_amostras_bruto.loc[df_amostras_bruto["codigo_amostra"].duplicated(), "codigo_amostra"].unique())

    df_locais = df_locais_bruto.drop_duplicates(subset=["id_local"])
    df_amostras = df_amostras_bruto.drop_duplicates(subset=["codigo_amostra"])
    df_visitas = pd.DataFrame(visitas_list, columns=["id_visita", "id_local", "data_visita", "n_exam", "n_secas", "n_agua_sem"])

    for col in ["n_exam", "n_secas", "n_agua_sem"]:
        df_visitas[col] = df_visitas[col].apply(numero_inteiro).astype(int)
    df_visitas["n_com"] = (df_visitas["n_exam"] - df_visitas["n_secas"] - df_visitas["n_agua_sem"]).clip(lower=0)
    df_visitas["data_visita"] = pd.to_datetime(df_visitas["data_visita"], errors="coerce")
    df_amostras["data_visita"] = pd.to_datetime(df_amostras["data_visita"], errors="coerce")
    for col in ["ph", "temp", "vol"]: df_amostras[col] = para_numero(df_amostras[col])

    lab_por_codigo, codigos_lab_duplicados = {}, set()
    for item in sorted(lista_lab, key=lambda i: i.get("_submission_time") or ""):
        cod_lab = item.get("grp_amostra/codigo_amostra")
        if not cod_lab or not str(cod_lab).strip(): continue
        cod_lab = normalizar_codigo(cod_lab)
        if cod_lab in lab_por_codigo: codigos_lab_duplicados.add(cod_lab)
        lab_por_codigo[cod_lab] = item

    codigos_lab = set(lab_por_codigo)
    lab_especies, resultados_lab = [], {}
    for cod_lab, item in lab_por_codigo.items():
        res_linhas = []
        for e in item.get("rep_especies", []) or []:
            especie = e.get("rep_especies/especie_identificada") or "nao_identificado"
            qtd = (numero_inteiro(e.get("rep_especies/qtd_larvas")) + numero_inteiro(e.get("rep_especies/qtd_pupas")) + numero_inteiro(e.get("rep_especies/qtd_adultos")))
            res = normalizar_texto(e.get("rep_especies/resultado_amostra"))
            if res: res_linhas.append(res)
            lab_especies.append({"codigo_amostra": cod_lab, "especie": normalizar_texto(especie).replace(" ", "_"), "qtd_especimes": qtd})
        res_geral = normalizar_texto(item.get("grp_resultado/resultado_amostra"))
        if not res_geral and res_linhas: res_geral = ("inconclusivo" if "inconclusivo" in res_linhas else "positivo" if "positivo" in res_linhas else "negativo")
        resultados_lab[cod_lab] = res_geral

    df_lab = pd.DataFrame(lab_especies, columns=["codigo_amostra", "especie", "qtd_especimes"])
    codigos_lab_orfaos = sorted(codigos_lab - set(df_amostras["codigo_amostra"]))

    return {
        "df_locais": df_locais, "df_locais_todos": df_locais.copy(), "df_visitas": df_visitas,
        "df_visitas_todas": df_visitas.copy(), "df_amostras": df_amostras, "df_amostras_todas": df_amostras.copy(),
        "df_lab": df_lab, "resultados_lab": resultados_lab, "codigos_lab": codigos_lab,
        "codigos_lab_orfaos": codigos_lab_orfaos, "codigos_lab_duplicados": codigos_lab_duplicados,
        "ids_locais_duplicados": ids_locais_duplicados, "codigos_campo_duplicados": codigos_campo_duplicados,
        "codigos_visita_sem_cadastro": codigos_visita_sem_cadastro
    }