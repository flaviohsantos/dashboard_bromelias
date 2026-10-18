import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from kobo_api import _get_secret, baixar_formulario, preparar_dados_completos

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.caption("Monitoramento mensal e análise laboratorial | Arraial do Cabo-RJ")

# 1. Carregar dados
base_url = _get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
token = _get_secret("KOBO_TOKEN")
uid_campo = _get_secret("UID_CAMPO")
uid_lab = _get_secret("UID_LAB")

with st.spinner("Baixando dados..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)
    df_plantas, df_dados = preparar_dados_completos(lista_campo, lista_lab)

if df_plantas.empty:
    st.warning("Nenhum dado encontrado.")
    st.stop()

# --- AUDITORIA DE DADOS ---
# Compara o que o técnico digitou (resultado_digitado) com o que deveria ser (resultado_real)
df_dados["resultado_digitado"] = df_dados["resultado_digitado"].fillna("nao_processado").astype(str)
df_dados["resultado_real"] = df_dados["resultado_real"].fillna("Nenhum")

# Erro se o técnico digitou "Negativo", mas tem Aedes (ou vice-versa)
erro_1 = (df_dados["resultado_real"] == "Positivo (Aedes)") & (df_dados["resultado_digitado"].str.lower() == "negativo")
erro_2 = (df_dados["resultado_real"] == "Negativo (Outros)") & (df_dados["resultado_digitado"].str.lower() == "positivo")
df_erros = df_dados[erro_1 | erro_2].copy()

with st.sidebar:
    st.markdown("---")
    st.markdown("### 🚨 Auditoria de Laboratório")
    if not df_erros.empty:
        st.error(f"⚠️ Encontrados **{len(df_erros)}** erros de seleção no laboratório.")
        for idx, row in df_erros.iterrows():
            amostra = row['id_amostra_calc']
            with st.expander(f"🔍 Amostra {amostra}"):
                st.write(f"**Planta:** {row['id_bromelia_calc']}")
                st.write(f"**Espécie encontrada:** {row['especie_identificada']}")
                st.write(f"**O técnico marcou:** {row['resultado_digitado'].capitalize()}")
                st.write(f"**O correto seria:** {row['resultado_real']}")
                st.warning("O resultado real foi corrigido automaticamente nos gráficos.")
    else:
        st.success("✅ Nenhum erro de seleção no laboratório.")

# 2. Filtros
st.sidebar.header("🔎 Filtros")
bairros = sorted(df_plantas["bairro"].dropna().unique())
bairro_sel = st.sidebar.multiselect("Bairro", bairros, default=bairros)
generos = sorted(df_plantas["genero"].dropna().unique())
genero_sel = st.sidebar.multiselect("Gênero da bromélia", generos, default=generos)

df_plantas_filtrado = df_plantas.copy()
df_dados_filtrado = df_dados.copy()

if bairro_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["bairro"].isin(bairro_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["bairro"].isin(bairro_sel)]
if genero_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["genero"].isin(genero_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["genero"].isin(genero_sel)]

# 4. KPIs
st.markdown("### 📊 Indicadores-chave")
c1, c2, c3, c4, c5 = st.columns(5)
n_plantas = df_plantas_filtrado["id_bromelia_calc"].nunique()
n_visitas = df_dados_filtrado["data_visita"].notna().sum()
n_amostras = df_dados_filtrado["id_amostra_calc"].nunique()

# Agora a positividade usa o "resultado_real" (calculado pelas espécies)
amostras_positivas = df_dados_filtrado[df_dados_filtrado["resultado_real"] == "Positivo (Aedes)"]["id_amostra_calc"].nunique()
positividade = (amostras_positivas / n_amostras * 100) if n_amostras > 0 else 0
total_especimes = pd.to_numeric(df_dados_filtrado["soma_contagem"], errors="coerce").sum()

c1.metric("Plantas", n_plantas)
c2.metric("Visitas", n_visitas)
c3.metric("Amostras", n_amostras)
c4.metric("Positividade (Aedes)", f"{positividade:.1f}%")
c5.metric("Espécimes (Lab)", int(total_especimes))

# 5. Mapa
st.markdown("### 🗺️ Mapa das plantas monitoradas")
df_mapa = df_plantas_filtrado.dropna(subset=["latitude", "longitude"])
if not df_mapa.empty:
    m = folium.Map(location=[-22.9661, -42.0272], zoom_start=13, tiles="OpenStreetMap")
    for _, row in df_mapa.iterrows():
        folium.CircleMarker(location=[row["latitude"], row["longitude"]], radius=7, color="blue", fill=True, fill_color="blue", fill_opacity=0.7,
            popup=f"<b>{row['id_bromelia_calc']}</b><br>Gênero: {row['genero']}<br>Bairro: {row['bairro']}").add_to(m)
    st_folium(m, width=None, height=500)

# 6. Série Temporal
st.markdown("### 📈 Série temporal de coletas")
if "data_visita" in df_dados_filtrado.columns and not df_dados_filtrado.empty:
    df_serie = df_dados_filtrado.dropna(subset=["data_visita"]).copy()
    if not df_serie.empty:
        df_serie["data_visita"] = pd.to_datetime(df_serie["data_visita"], errors="coerce")
        df_serie["mes"] = df_serie["data_visita"].dt.to_period("M").astype(str)
        contagem = df_serie.groupby("mes").agg(visitas=("data_visita", "count"), amostras=("id_amostra_calc", "nunique")).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=contagem["mes"], y=contagem["visitas"], name="Visitas", marker_color="#2E86AB"))
        fig.add_trace(go.Bar(x=contagem["mes"], y=contagem["amostras"], name="Amostras", marker_color="#E63946"))
        fig.update_layout(barmode="group", height=400)
        st.plotly_chart(fig, use_container_width=True)

# 7. Gráficos de Espécies e Tabela
st.markdown("---")
col_esq, col_dir = st.columns([2, 1])
with col_esq:
    st.markdown("### 🦟 Frequência de Espécies Identificadas")
    df_especies_counts = df_dados_filtrado.groupby("especie_identificada").agg(
        Total_Larvas=("soma_contagem", "sum"),
        Amostras=("id_amostra_calc", "nunique")
    ).reset_index().sort_values(by="Total_Larvas", ascending=False)
    df_especies_counts["Total_Larvas"] = pd.to_numeric(df_especies_counts["Total_Larvas"], errors="coerce").fillna(0)
    
    if not df_especies_counts.empty:
        fig_esp = px.bar(df_especies_counts, x="especie_identificada", y="Total_Larvas", color="especie_identificada", text="Total_Larvas", color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_esp.update_layout(showlegend=False, xaxis_title="", yaxis_title="Qtd. de Espécimes")
        st.plotly_chart(fig_esp, use_container_width=True)

with col_dir:
    st.markdown("### 📋 Totais e Percentuais")
    if not df_especies_counts.empty:
        total_geral = df_especies_counts["Total_Larvas"].sum()
        if total_geral > 0:
            percentual = (df_especies_counts["Total_Larvas"] / total_geral * 100).round(1)
            df_especies_counts["Percentual (%)"] = percentual.astype(str) + "%"
        else:
            df_especies_counts["Percentual (%)"] = "0%"
        
        df_tabela = df_especies_counts.rename(columns={"especie_identificada": "Espécie", "Total_Larvas": "Total Larvas", "Amostras": "Nº Amostras", "Percentual (%)": "Percentual"})
        linha_total = pd.DataFrame([{"Espécie": "TOTAL GERAL", "Total Larvas": total_geral, "Nº Amostras": df_especies_counts["Amostras"].sum(), "Percentual": "100%"}])
        df_tabela = pd.concat([df_tabela, linha_total], ignore_index=True)
        st.dataframe(df_tabela, hide_index=True, use_container_width=True)

# 8. Gráficos Gerais
st.markdown("---")
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("#### 🌱 Plantas por gênero")
    if not df_plantas_filtrado.empty:
        cont = df_plantas_filtrado["genero"].value_counts().reset_index()
        cont.columns = ["genero", "quantidade"]
        st.plotly_chart(px.pie(cont, names="genero", values="quantidade", hole=0.4), use_container_width=True)
with col_b:
    st.markdown("#### 🏘️ Plantas por bairro")
    if not df_plantas_filtrado.empty:
        cont = df_plantas_filtrado["bairro"].value_counts().reset_index()
        cont.columns = ["bairro", "quantidade"]
        st.plotly_chart(px.bar(cont, x="quantidade", y="bairro", orientation="h", color="quantidade"), use_container_width=True)

# 9. Tabela Consolidada
st.markdown("### 📋 Tabela consolidada de campo e laboratório")
colunas_uteis = ["id_bromelia_calc", "bairro", "genero", "data_visita", "id_amostra_calc", "especie_identificada", "resultado_real", "resultado_digitado"]
colunas_existentes = [c for c in colunas_uteis if c in df_dados_filtrado.columns]

if not df_dados_filtrado.empty and colunas_existentes:
    df_exibicao = df_dados_filtrado[colunas_existentes].rename(columns={
        "id_bromelia_calc": "Planta", "bairro": "Bairro", "genero": "Gênero", "data_visita": "Data Visita",
        "id_amostra_calc": "Amostra", "especie_identificada": "Espécie (Lab)", "resultado_real": "Result. Real", "resultado_digitado": "Result. Digitado"
    })
    st.dataframe(df_exibicao, use_container_width=True, height=400)