import os
import unicodedata
from datetime import datetime

import folium
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption(
    f"Pesquisador: Flávio Santos (IOC - Fiocruz) | "
    f"Atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
)
st.markdown("---")


def _get_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)


def baixar_formulario(uid, token, base_url):
    """Baixa todas as páginas de registros de um formulário KoboToolbox."""
    if not uid:
        return []

    url = f"{base_url}/api/v2/assets/{uid}/data/"
    headers = {"Authorization": f"Token {token}"}
    params = {"format": "json"}
    registros = []

    while url:
        response = requests.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        payload = response.json()
        registros.extend(payload.get("results", []))
        url = payload.get("next")
        params = {} 

    return registros


def normalizar_texto(valor):
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.lower().replace("_", " ").strip().split())


def primeiro_valor(registro, chaves):
    """Retorna o primeiro campo preenchido entre possíveis nomes Kobo."""
    if not isinstance(registro, dict):
        return None
    for chave in chaves:
        valor = registro.get(chave)
        if valor is not None and str(valor).strip() != "":
            return valor
    return None


def normalizar_codigo(valor):
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    codigo = str(valor).strip()
    return codigo or None


def numero_inteiro(valor):
    """Converte campos numéricos do Kobo para contagens inteiras não negativas."""
    if valor is None or str(valor).strip() == "":
        return 0
    try:
        texto = str(valor).strip().replace(",", ".")
        return max(0, int(float(texto)))
    except (TypeError, ValueError, OverflowError):
        return 0


def ler_contagem(registro, chaves_exatas, palavras_obrigatorias=()):
    """Lê uma contagem por nomes conhecidos ou detecta uma chave compatível."""
    if isinstance(registro, dict):
        for chave in chaves_exatas:
            if chave in registro:
                return numero_inteiro(registro.get(chave)), True

    if isinstance(registro, dict) and palavras_obrigatorias:
        for chave, valor in registro.items():
            nome = normalizar_texto(chave)
            if all(palavra in nome for palavra in palavras_obrigatorias):
                return numero_inteiro(valor), True

    return 0, False


def linhas_especies(registro_lab):
    linhas = registro_lab.get("rep_especies", []) if isinstance(registro_lab, dict) else []
    if isinstance(linhas, dict):
        return [linhas]
    if isinstance(linhas, list):
        return [linha for linha in linhas if isinstance(linha, dict)]
    return []


def extrair_analise(registro_lab):
    """Resume uma análise laboratorial, incluindo larvas e pupas."""
    codigo = normalizar_codigo(
        primeiro_valor(
            registro_lab,
            ["grp_amostra/codigo_amostra", "codigo_amostra"],
        )
    )
    if not codigo:
        return None

    especies = []
    detalhes = []
    total = 0

    for linha in linhas_especies(registro_lab):
        especie_original = primeiro_valor(
            linha,
            ["rep_especies/especie_identificada", "especie_identificada"],
        )
        especie = normalizar_texto(especie_original).replace(" ", "_")

        # Conta apenas larvas e pupas
        qtd_larvas, _ = ler_contagem(
            linha,
            ["rep_especies/qtd_larvas", "qtd_larvas", "quantidade_larvas"],
            ("larva",),
        )
        qtd_pupas, _ = ler_contagem(
            linha,
            ["rep_especies/qtd_pupas", "qtd_pupas", "quantidade_pupas"],
            ("pupa",),
        )

        subtotal = qtd_larvas + qtd_pupas
        total += subtotal

        if especie:
            especies.append(especie)
            detalhes.append(
                {
                    "codigo_amostra": codigo,
                    "especie": especie,
                    "qtd_especimes": subtotal,
                }
            )
        elif subtotal > 0:
            especie = "nao_identificado"
            especies.append(especie)
            detalhes.append(
                {
                    "codigo_amostra": codigo,
                    "especie": especie,
                    "qtd_especimes": subtotal,
                }
            )

    aedes = any("aedes" in especie for especie in especies)

    return {
        "codigo_amostra": codigo,
        "especies": list(dict.fromkeys(especies)),
        "qtd_especimes": total,
        "positivo": aedes,
        "detalhes": detalhes,
    }


base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)

if not lista_campo:
    st.warning("Nenhum dado de campo encontrado.")
    st.stop()

# --- PROCESSAMENTO DOS DADOS DE CAMPO ---
plantas = []
amostras = []

for indice, item in enumerate(lista_campo):
    id_planta = primeiro_valor(
        item,
        ["grp_cadastro/id_bromelia_calc", "id_bromelia_calc", "codigo_planta"],
    )
    if id_planta is None:
        id_planta = f"SEM-ID-{item.get('_id', indice)}"
    id_planta = str(id_planta).strip()

    bairro = primeiro_valor(item, ["grp_cadastro/bairro", "bairro"]) or "Não informado"
    genero = primeiro_valor(item, ["grp_cadastro/genero", "genero"]) or "Não informado"

    geo = primeiro_valor(item, ["grp_cadastro/geolocalizacao", "geolocalizacao"])
    lat, lon = None, None
    if isinstance(geo, str):
        partes = geo.replace(",", " ").split()
        if len(partes) >= 2:
            try:
                lat, lon = float(partes[0]), float(partes[1])
            except (TypeError, ValueError):
                pass

    plantas.append(
        {
            "id_bromelia": id_planta,
            "bairro": bairro,
            "genero": genero,
            "lat": lat,
            "lon": lon,
        }
    )

    visitas = item.get("rep_visitas", [])
    if isinstance(visitas, dict):
        visitas = [visitas]
    if isinstance(visitas, list):
        for visita in visitas:
            if not isinstance(visita, dict):
                continue
            ams = visita.get("rep_visitas/rep_amostras", [])
            if isinstance(ams, dict):
                ams = [ams]
            if isinstance(ams, list):
                for amostra in ams:
                    if not isinstance(amostra, dict):
                        continue
                    codigo = normalizar_codigo(
                        primeiro_valor(
                            amostra,
                            [
                                "rep_visitas/rep_amostras/codigo_amostra",
                                "codigo_amostra",
                            ],
                        )
                    )
                    if codigo:
                        amostras.append(
                            {"id_bromelia": id_planta, "codigo_amostra": codigo}
                        )

df_plantas = pd.DataFrame(plantas)
df_plantas = df_plantas.drop_duplicates(subset=["id_bromelia"], keep="last")

df_amostras = pd.DataFrame(amostras, columns=["id_bromelia", "codigo_amostra"])
if not df_amostras.empty:
    df_amostras = df_amostras.drop_duplicates(subset=["codigo_amostra"], keep="first")

# --- PROCESSAMENTO DOS DADOS LABORATORIAIS ---
analises_por_codigo = {}
for item in lista_lab:
    analise = extrair_analise(item)
    if analise:
        analises_por_codigo[analise["codigo_amostra"]] = analise

df_lab = pd.DataFrame(
    [
        {k: v for k, v in analise.items() if k != "detalhes"}
        for analise in analises_por_codigo.values()
    ],
    columns=["codigo_amostra", "especies", "qtd_especimes", "positivo"],
)
df_lab_detalhes = pd.DataFrame(
    [
        detalhe
        for analise in analises_por_codigo.values()
        for detalhe in analise["detalhes"]
    ],
    columns=["codigo_amostra", "especie", "qtd_especimes"],
)

# --- CRUZAMENTO ---
if not df_amostras.empty and not df_lab.empty:
    df_merge = pd.merge(
        df_amostras,
        df_lab,
        on="codigo_amostra",
        how="left",
        validate="one_to_one",
    )
    df_por_planta = (
        df_merge.groupby("id_bromelia", as_index=False)
        .agg(
            {
                "especies": lambda valores: list(
                    dict.fromkeys(
                        especie
                        for lista in valores
                        if isinstance(lista, list)
                        for especie in lista
                    )
                ),
                "qtd_especimes": "sum",
                "positivo": "max",
            }
        )
    )
else:
    df_por_planta = pd.DataFrame(
        columns=["id_bromelia", "especies", "qtd_especimes", "positivo"]
    )

df_final = pd.merge(df_plantas, df_por_planta, on="id_bromelia", how="left")
if "especies" not in df_final:
    df_final["especies"] = [[] for _ in range(len(df_final))]
else:
    df_final["especies"] = df_final["especies"].apply(
        lambda valor: valor if isinstance(valor, list) else []
    )

df_final["qtd_especimes"] = pd.to_numeric(
    df_final.get("qtd_especimes", 0), errors="coerce"
).fillna(0)
df_final["positivo"] = df_final.get("positivo", False).fillna(False).astype(bool)
df_final["especie_str"] = df_final["especies"].apply(
    lambda lista: ", ".join(lista) if lista else "Não informado"
)
df_final["especie_str"] = df_final["especie_str"].str.replace("_", " ").str.capitalize()

# --- MÉTRICAS ---
n_plantas = int(df_final["id_bromelia"].nunique())
total_especimes = int(df_final["qtd_especimes"].sum())
plantas_positivas = int(df_final.loc[df_final["positivo"], "id_bromelia"].nunique())
positividade = (
    plantas_positivas / n_plantas * 100
    if n_plantas > 0
    else 0
)

st.markdown("### 📊 Indicadores")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Plantas cadastradas", n_plantas)
c2.metric("Espécimes (Larvas + Pupas)", total_especimes)
c3.metric("Plantas positivas (Aedes)", plantas_positivas)
c4.metric("Positividade", f"{positividade:.1f}%")

st.markdown("---")

# --- MAPA ---
st.markdown("### 🗺️ Mapa de Risco (Raio de 100m)")
df_mapa = df_final.dropna(subset=["lat", "lon"])

if not df_mapa.empty:
    centro_lat = df_mapa["lat"].mean()
    centro_lon = df_mapa["lon"].mean()
    mapa = folium.Map(
        location=[centro_lat, centro_lon], zoom_start=16, tiles="OpenStreetMap"
    )

    for _, linha in df_mapa.iterrows():
        if linha["positivo"]:
            folium.Circle(
                location=[linha["lat"], linha["lon"]],
                radius=100,
                color="#E63946",
                fill=True,
                fill_color="#E63946",
                fill_opacity=0.2,
                weight=2,
            ).add_to(mapa)
            cor = "red"
            resultado_mapa = f"POSITIVO ({linha['especie_str']})"
        else:
            cor = "blue"
            resultado_mapa = "Sem Aedes detectado"

        folium.Marker(
            location=[linha["lat"], linha["lon"]],
            icon=folium.Icon(color=cor, icon="info-sign"),
            popup=f"<b>{linha['id_bromelia']}</b><br>{resultado_mapa}",
        ).add_to(mapa)

    st_folium(mapa, width=None, height=500, key="mapa")
else:
    st.info("Sem coordenadas para o mapa.")

# --- GRÁFICO DE ESPÉCIES ---
st.markdown("---")
st.markdown("### 🦟 Frequência de Espécies")

if not df_lab_detalhes.empty:
    df_chart = (
        df_lab_detalhes.groupby("especie", as_index=False)["qtd_especimes"]
        .sum()
    )
    df_chart["especie"] = (
        df_chart["especie"].str.replace("_", " ", regex=False).str.capitalize()
    )

    if df_chart["qtd_especimes"].sum() > 0:
        figura = px.bar(
            df_chart,
            x="especie",
            y="qtd_especimes",
            text="qtd_especimes",
            color="especie",
        )
        figura.update_layout(showlegend=False, xaxis_title="", yaxis_title="Espécimes")
        st.plotly_chart(figura, use_container_width=True)

        st.markdown("#### 📋 Totais")
        st.dataframe(
            df_chart.rename(
                columns={
                    "especie": "Espécie",
                    "qtd_especimes": "Larvas + Pupas",
                }
            ),
            hide_index=True,
        )
    else:
        st.info("Nenhum espécime contado nos registros laboratoriais.")
else:
    st.info("Ainda não há espécies registradas nas análises laboratoriais.")

st.markdown("---")
st.caption(
    "Dashboard desenvolvido por Flávio Santos | PPG-VCV / IOC - Fiocruz | "
    "Contato: fhsantos@gmail.com"
)
