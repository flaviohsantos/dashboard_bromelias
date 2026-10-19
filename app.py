import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from kobo_api import _get_secret, baixar_formulario, preparar_dados_completos
from datetime import datetime

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")

st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.markdown(f"""
<div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 20px; font-size: 14px;">
    <b>Pesquisador:</b> Flávio Santos (Mestrado Profissional - IOC - Fiocruz) | <b>Contato:</b> fhsantos@gmail.com <br>
    <b>Última atualização dos dados:</b> {datetime.now().strftime('%d/%m/%Y às %H:%M')}
</div>
""", unsafe_allow_html=True)

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

# --- LIMPEZA E AUDITORIA ---
if "resultado_digitado" in df_dados.columns:
    df_dados["resultado_digitado"] = df_dados["resultado_digitado"].astype(str).str.lower().str.strip().replace(["nan", "none", ""], "nao_processado")
else:
    df_dados["resultado_digitado"] = "nao_processado"

if "resultado_real" in df_dados.columns:
    df_dados["resultado_real"] = df_dados["resultado_real"].fillna("Nenhum")
else:
    df_dados["resultado_real"] = "Nenhum"

if "soma_contagem" in df_dados.columns:
    df_dados["soma_contagem"] = pd.to_numeric(df_dados["soma_contagem"], errors="coerce").fillna(0)
    df_dados.loc[df_dados["soma_contagem"] > 200, "soma_contagem"] = 0
else:
    df_dados["soma_contagem"] = 0

erro_1 = (df_dados["resultado_real"] == "Positivo (Aedes)") & (df_dados["resultado_digitado"] == "negativo")
erro_2 = (df_dados["resultado_real"] == "Negativo (Outros)") & (df_dados["resultado_digitado"] == "positivo")
df_erros = df_dados[erro_1 | erro_2].copy()

with st.sidebar:
    st.markdown("### 🚨 Auditoria de Laboratório")
    if not df_erros.empty:
        st.error(f"⚠️ Encontrados **{len(df_erros)}** erros.")
        for idx, row in df_erros.iterrows():
            with st.expander(f"🔍 Amostra {row['id_amostra_calc']}"):
                st.write(f"**Espécie:** {row['especie_identificada'].replace('_', ' ').capitalize()}")
                st.write(f"**Digitou:** {row['resultado_digitado'].capitalize()} | **Correto:** {row['resultado_real']}")
    else:
        st.success("✅ Nenhum erro de seleção.")

    st.markdown("---")
    st.header("🔎 Filtros")
    bairros = sorted(df_plantas["bairro"].dropna().unique())
    bairro_sel = st.multiselect("Bairro", bairros, default=bairros)
    generos = sorted(df_plantas["genero"].dropna().unique())
    genero_sel = st.multiselect("Gênero da bromélia", generos, default=generos)

    st.markdown("---")
    st.markdown("### 🗺️ Visualização do Mapa")
    tipo_mapa = st.radio("Selecione o mapa:", ["Mapa Base e Raio (100m)", "🔥 Mapa de Calor (Apenas Focos)"])

df_plantas_filtrado = df_plantas.copy()
df_dados_filtrado = df_dados.copy()

if bairro_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["bairro"].isin(bairro_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["bairro"].isin(bairro_sel)]
if genero_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["genero"].isin(genero_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["genero"].isin(genero_sel)]

if "especie_identificada" in df_dados_filtrado.columns:
    df_dados_filtrado["especie_display"] = df_dados_filtrado["especie_identificada"].apply(
        lambda x: f"{str(x).replace('_', ' ').capitalize()}" if pd.notna(x) and str(x).lower() != "nan" else "Não informado"
    )
else:
    df_dados_filtrado["especie_display"] = "Não informado"

n_plantas = df_plantas_filtrado["id_bromelia_calc"].nunique()
n_visitas = df_dados_filtrado["data_visita"].notna().sum() if "data_visita" in df_dados_filtrado.columns else 0
n_amostras = df_dados_filtrado["id_amostra_calc"].nunique() if "id_amostra_calc" in df_dados_filtrado.columns else 0

if "especie_identificada" in df_dados_filtrado.columns and "id_amostra_calc" in df_dados_filtrado.columns:
    amostras_com_aedes = df_dados_filtrado[df_dados_filtrado["especie_identificada"].str.contains("aedes", case=False, na=False)]
    amostras_positivas = amostras_com_aedes["id_amostra_calc"].nunique()
else:
    amostras_positivas = 0

positividade = (amostras_positivas / n_amostras * 100) if n_amostras > 0 else 0
total_especimes = pd.to_numeric(df_dados_filtrado["soma_contagem"], errors="coerce").sum()

st.markdown("### 🗺️ Mapas de Risco Georreferenciados e Termômetro")
df_mapa = df_plantas_filtrado.dropna(subset=["latitude", "longitude"])
plantas_positivas = df_dados_filtrado[df_dados_filtrado["resultado_real"] == "Positivo (Aedes)"]
ids_positivos = plantas_positivas["id_bromelia_calc"].unique() if not plantas_positivas.empty else []

col_mapa, col_termo = st.columns([3, 1])
with col_mapa:
    if not df_mapa.empty:
        if tipo_mapa == "Mapa Base e Raio (100m)":
            m1 = folium.Map(location=[-22.9661, -42.0272], zoom_start=15, tiles="OpenStreetMap")
            for _, row in df_mapa.iterrows():
                tem_risco = row["id_bromelia_calc"] in ids_positivos
                if tem_risco:
                    folium.Circle(location=[row["latitude"], row["longitude"]], radius=100, color="#E63946", fill=True, fill_color="#E63946", fill_opacity=0.2, weight=2).add_to(m1)
                    folium.Marker(location=[row["latitude"], row["longitude"]], icon=folium.Icon(color="red", icon="info-sign"), popup=f"<b>{row['id_bromelia_calc']}</b>").add_to(m1)
                else:
                    folium.Marker(location=[row["latitude"], row["longitude"]], icon=folium.Icon(color="blue", icon="info-sign"), popup=f"<b>{row['id_bromelia_calc']}</b>").add_to(m1)
            st_folium(m1, width=None, height=500, key="mapa_base_estatico")
        else:
            df_calor = df_mapa[df_mapa["id_bromelia_calc"].isin(ids_positivos)]
            if not df_calor.empty:
                m2 = folium.Map(location=[-22.9661, -42.0272], zoom_start=14, tiles="OpenStreetMap")
                heat_data = [[row["latitude"], row["longitude"]] for index, row in df_calor.iterrows()]
                HeatMap(heat_data, radius=50, blur=30, min_opacity=0.8).add_to(m2)
                st_folium(m2, width=None, height=500, key="mapa_calor_estatico")
            else:
                st.info("✅ Nenhuma planta positiva para gerar o mapa de calor no momento.")

with col_termo:
    st.markdown("#### 🌡️ Termômetro de Risco")
    if positividade < 15: cor_termo, status_risco = "#2E86AB", "BAIXO"
    elif positividade < 40: cor_termo, status_risco = "#F4A261", "MÉDIO"
    else: cor_termo, status_risco = "#E63946", "ALTO"

    fig_termo = go.Figure(go.Indicator(
        mode = "gauge+number", value = positividade,
        number = {'suffix': "%", 'font': {'size': 36}},
        title = {'text': f"Risco {status_risco}", 'font': {'size': 18}},
        gauge = {
            'axis': {'range': [0, 100]}, 'bar': {'color': cor_termo},
            'steps': [{'range': [0, 15], 'color': '#D6EAF8'}, {'range': [15, 40], 'color': '#FDEBD0'}, {'range': [40, 100], 'color': '#FADBD8'}],
        }
    ))
    fig_termo.update_layout(height=350, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig_termo, use_container_width=True)

st.markdown("---")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Plantas", n_plantas)
c2.metric("Visitas", n_visitas)
c3.metric("Amostras", n_amostras)
c4.metric("Espécimes (Lab)", int(total_especimes))

st.markdown("#### 🌡️ Resumo do Microclima e Ambiente")
if not df_dados_filtrado.empty:
    colunas_agua = ["ph_agua", "temp_agua_c", "volume_agua_ml"]
    for col in colunas_agua:
        if col in df_dados_filtrado.columns:
            df_dados_filtrado[col] = pd.to_numeric(df_dados_filtrado[col], errors="coerce")
    
    media_ph = df_dados_filtrado["ph_agua"].mean() if "ph_agua" in df_dados_filtrado.columns else 0
    media_temp = df_dados_filtrado["temp_agua_c"].mean() if "temp_agua_c" in df_dados_filtrado.columns else 0
    media_vol = df_dados_filtrado["volume_agua_ml"].mean() if "volume_agua_ml" in df_dados_filtrado.columns else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("pH Médio da Água", f"{media_ph:.2f}" if pd.notna(media_ph) else "—")
    m2.metric("Temperatura Média", f"{media_temp:.1f} °C" if pd.notna(media_temp) else "—")
    m3.metric("Volume Médio", f"{media_vol:.0f} mL" if pd.notna(media_vol) else "—")
    pct_agua = (df_dados_filtrado["presenca_imaturos"].notna().sum() / len(df_dados_filtrado) * 100) if len(df_dados_filtrado) > 0 else 0
    m4.metric("Bromélias com Água", f"{pct_agua:.1f}%")

st.markdown("---")
col_esq, col_dir = st.columns([2, 1])
with col_esq:
    st.markdown("### 🦟 Frequência de Espécies Identificadas")
    df_especies_counts = df_dados_filtrado.groupby("especie_display").agg(Total_Larvas=("soma_contagem", "sum"), Amostras=("id_amostra_calc", "nunique")).reset_index().sort_values(by="Total_Larvas", ascending=False)
    df_especies_counts["Total_Larvas"] = pd.to_numeric(df_especies_counts["Total_Larvas"], errors="coerce").fillna(0)
    if not df_especies_counts.empty:
        fig_esp = px.bar(df_especies_counts, x="especie_display", y="Total_Larvas", text="Total_Larvas", color="especie_display", color_discrete_sequence=px.colors.qualitative.Pastel)
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
        df_tabela = df_especies_counts.rename(columns={"especie_display": "Espécie", "Total_Larvas": "Total Larvas", "Amostras": "Nº Amostras", "Percentual (%)": "Percentual"})
        linha_total = pd.DataFrame([{"Espécie": "TOTAL GERAL", "Total Larvas": total_geral, "Nº Amostras": df_especies_counts["Amostras"].sum(), "Percentual": "100%"}])
        df_tabela = pd.concat([df_tabela, linha_total], ignore_index=True)
        st.dataframe(df_tabela, hide_index=True, use_container_width=True)

st.markdown("---")
st.markdown("### 📝 Notas e Intercorrências de Campo")
if "observacoes_visita" in df_dados_filtrado.columns:
    df_obs = df_dados_filtrado.copy()
    df_obs["observacoes_visita"] = df_obs["observacoes_visita"].astype(str).str.strip()
    df_obs = df_obs[(df_obs["observacoes_visita"] != "") & (df_obs["observacoes_visita"].str.lower() != "nan") & (df_obs["observacoes_visita"].str.lower() != "none")]
    if not df_obs.empty:
        for _, row in df_obs.drop_duplicates(subset=["id_bromelia_calc", "data_visita"]).iterrows():
            data_str = pd.to_datetime(row["data_visita"]).strftime('%d/%m/%Y') if pd.notna(row["data_visita"]) else "Data não informada"
            st.info(f"**{data_str}** | Planta **{row['id_bromelia_calc']}**: *\"{row['observacoes_visita']}\"*")
    else:
        st.success("✅ Nenhuma intercorrência registrada.")

st.markdown("### 🔬 Notas do Laboratório")
if "observacoes_lab" in df_dados_filtrado.columns:
    df_lab_obs = df_dados_filtrado.copy()
    df_lab_obs["observacoes_lab"] = df_lab_obs["observacoes_lab"].astype(str).str.strip()
    df_lab_obs = df_lab_obs[(df_lab_obs["observacoes_lab"] != "") & (df_lab_obs["observacoes_lab"].str.lower() != "nan") & (df_lab_obs["observacoes_lab"].str.lower() != "none")]
    if not df_lab_obs.empty:
        for _, row in df_lab_obs.drop_duplicates(subset=["id_amostra_calc"]).iterrows():
            st.warning(f"**Amostra {row['id_amostra_calc']}**: *\"{row['observacoes_lab']}\"*")
    else:
        st.success("✅ Nenhuma observação registrada no laboratório.")

st.markdown("---")
st.markdown("### 📋 Tabela consolidada de campo e laboratório")
colunas_uteis = ["id_bromelia_calc", "bairro", "genero", "data_visita", "id_amostra_calc", "especie_display", "resultado_real", "resultado_digitado"]
colunas_existentes = [c for c in colunas_uteis if c in df_dados_filtrado.columns]

if not df_dados_filtrado.empty and colunas_existentes:
    df_exibicao = df_dados_filtrado[colunas_existentes].rename(columns={
        "id_bromelia_calc": "Planta", "bairro": "Bairro", "genero": "Gênero", "data_visita": "Data Visita",
        "id_amostra_calc": "Amostra", "especie_display": "Espécie (Lab)", "resultado_real": "Result. Real", "resultado_digitado": "Result. Digitado"
    })
    st.dataframe(df_exibicao, use_container_width=True, height=400)

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: gray; font-size: 14px; padding: 20px;">
    Dashboard desenvolvido por <b>Flávio Santos</b><br>
    Mestrado Profissional em Vigilância e Controle de Vetores (PPG-VCV) - IOC / Fiocruz<br>
    Contato: fhsantos@gmail.com
</div>
""", unsafe_allow_html=True)