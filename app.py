import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import MarkerCluster, HeatMap
from streamlit_folium import st_folium
from kobo_api import _get_secret, baixar_formulario, preparar_dados_completos
from datetime import datetime

# Configuração da página
st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")

# --- IDENTIFICAÇÃO DO PESQUISADOR (TOPO) ---
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.markdown(f"""
<div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 20px; font-size: 14px;">
    <b>Pesquisador:</b> Flávio Santos (Mestrado Profissional - IOC - Fiocruz) | <b>Contato:</b> fhsantos@gmail.com <br>
    <b>Última atualização dos dados:</b> {datetime.now().strftime('%d/%m/%Y às %H:%M')}
</div>
""", unsafe_allow_html=True)

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

# --- LIMPEZA DE DADOS E AUDITORIA ---
if "resultado_digitado" in df_dados.columns:
    df_dados["resultado_digitado"] = df_dados["resultado_digitado"].fillna("nao_processado").astype(str)
else:
    df_dados["resultado_digitado"] = "nao_processado"

if "resultado_real" in df_dados.columns:
    df_dados["resultado_real"] = df_dados["resultado_real"].fillna("Nenhum")
else:
    df_dados["resultado_real"] = "Nenhum"

if "soma_contagem" in df_dados.columns:
    df_dados["soma_contagem"] = pd.to_numeric(df_dados["soma_contagem"], errors="coerce").fillna(0)
    df_dados.loc[df_dados["soma_contagem"] > 200, "soma_contagem"] = 0

erro_1 = (df_dados["resultado_real"] == "Positivo (Aedes)") & (df_dados["resultado_digitado"].str.lower() == "negativo")
erro_2 = (df_dados["resultado_real"] == "Negativo (Outros)") & (df_dados["resultado_digitado"].str.lower() == "positivo")
df_erros = df_dados[erro_1 | erro_2].copy()

# --- MENU LATERAL E FILTROS ---
with st.sidebar:
    st.markdown("---")
    st.markdown("### 🚨 Auditoria de Laboratório")
    if not df_erros.empty:
        st.error(f"⚠️ Encontrados **{len(df_erros)}** erros de seleção.")
        for idx, row in df_erros.iterrows():
            with st.expander(f"🔍 Amostra {row['id_amostra_calc']}"):
                st.write(f"**Planta:** {row['id_bromelia_calc']}")
                st.write(f"**Espécie:** {row['especie_identificada'].replace('_', ' ').capitalize()}")
                st.write(f"**Digitou:** {row['resultado_digitado'].capitalize()}")
                st.write(f"**Correto:** {row['resultado_real']}")
    else:
        st.success("✅ Nenhum erro de seleção.")

    st.markdown("---")
    st.header("🔎 Filtros")
    bairros = sorted(df_plantas["bairro"].dropna().unique())
    bairro_sel = st.multiselect("Bairro", bairros, default=bairros)
    generos = sorted(df_plantas["genero"].dropna().unique())
    genero_sel = st.multiselect("Gênero da bromélia", generos, default=generos)

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
        lambda x: f"{str(x).replace('_', ' ').capitalize()}" if pd.notna(x) else "Não informado"
    )
else:
    df_dados_filtrado["especie_display"] = "Não informado"

# Cálculos base
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

# ==========================================
# TOPO: MAPAS EM ABAS E TERMÔMETRO
# ==========================================
st.markdown("### 🗺️ Mapas de Risco Georreferenciados e Termômetro")

df_mapa = df_plantas_filtrado.dropna(subset=["latitude", "longitude"])
plantas_positivas = df_dados_filtrado[df_dados_filtrado["resultado_real"] == "Positivo (Aedes)"]
ids_positivos = plantas_positivas["id_bromelia_calc"].unique() if not plantas_positivas.empty else []

col_mapa, col_termo = st.columns([3, 1])

with col_mapa:
    tab1, tab2 = st.tabs(["📍 Mapa Base e Raio (100m)", "🔥 Mapa de Calor"])

    with tab1:
        if not df_mapa.empty:
            m1 = folium.Map(location=[-22.9661, -42.0272], zoom_start=15, tiles="OpenStreetMap")
            for _, row in df_mapa.iterrows():
                tem_risco = row["id_bromelia_calc"] in ids_positivos
                if tem_risco:
                    folium.Circle(location=[row["latitude"], row["longitude"]], radius=100, color="#E63946", fill=True, fill_color="#E63946", fill_opacity=0.2, weight=2, popup="Raio 100m (Aedes)").add_to(m1)
                    folium.Marker(location=[row["latitude"], row["longitude"]], icon=folium.Icon(color="red", icon="info-sign"), popup=f"<b>{row['id_bromelia_calc']}</b><br>POSITIVO").add_to(m1)
                else:
                    folium.Marker(location=[row["latitude"], row["longitude"]], icon=folium.Icon(color="blue", icon="info-sign"), popup=f"<b>{row['id_bromelia_calc']}</b><br>Negativo").add_to(m1)
            st_folium(m1, width=None, height=450, key="mapa1")

    with tab2:
        if not df_mapa.empty:
            m2 = folium.Map(location=[-22.9661, -42.0272], zoom_start=13, tiles="OpenStreetMap")
            df_calor = df_mapa[df_mapa["id_bromelia_calc"].isin(ids_positivos)]
            if not df_calor.empty:
                heat_data = [[row["latitude"], row["longitude"]] for index, row in df_calor.iterrows()]
                HeatMap(heat_data, radius=40, blur=25, min_opacity=0.8).add_to(m2)
                for _, row in df_calor.iterrows():
                    folium.Marker(location=[row["latitude"], row["longitude"]], icon=folium.Icon(color="red", icon="info-sign")).add_to(m2)
                st_folium(m2, width=None, height=450, key="mapa2")
            else:
                st.info("Nenhuma planta positiva para gerar o mapa de calor.")

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
    st.info("Reflete a % de amostras positivas para *Aedes* com base nos filtros.")

# ==========================================
# MEIO: KPIs E MICROCLIMA
# ==========================================
st.markdown("---")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Plantas", n_plantas)
c2.metric("Visitas", n_visitas)
c3.metric("Amostras", n_amostras)
c4.metric("Espécimes (Lab)", int(total_especimes))

# --- NOVO: MICROCLIMA E AMBIENTE (Inspirado no colega) ---
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
    
    # Porcentagem de bromélias com água
    pct_agua = (df_dados_filtrado["presenca_imaturos"].notna().sum() / len(df_dados_filtrado) * 100) if len(df_dados_filtrado) > 0 else 0
    m4.metric("Bromélias com Água", f"{pct_agua:.1f}%")

# ==========================================
# SÉRIE TEMPORAL COM PICO (Inspirado no colega)
# ==========================================
st.markdown("---")
st.markdown("### 📈 Série temporal de coletas")
if "data_visita" in df_dados_filtrado.columns and not df_dados_filtrado.empty:
    df_serie = df_dados_filtrado.dropna(subset=["data_visita"]).copy()
    if not df_serie.empty:
        df_serie["data_visita"] = pd.to_datetime(df_serie["data_visita"], errors="coerce")
        df_serie["mes"] = df_serie["data_visita"].dt.to_period("M").astype(str)
        contagem = df_serie.groupby("mes").agg(visitas=("data_visita", "count"), amostras=("id_amostra_calc", "nunique")).reset_index()
        
        # Encontra o pico
        if not contagem.empty:
            pico = contagem.loc[contagem["amostras"].idxmax()]
            st.info(f"🏆 **Pico de Coletas:** O mês com mais amostras foi **{pico['mes']}** com **{pico['amostras']}** amostras coletadas.")
        
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
    df_especies_counts = df_dados_filtrado.groupby("especie_display").agg(
        Total_Larvas=("soma_contagem", "sum"), Amostras=("id_amostra_calc", "nunique")
    ).reset_index().sort_values(by="Total_Larvas", ascending=False)
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

# 8. Gráficos Gerais
st.markdown("---")
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("#### 🌱 Plantas por gênero")
    if not df_plantas_filtrado.empty:
        cont = df_plantas_filtrado["genero"].value_counts().reset_index()
        cont.columns = ["genero", "quantidade"]
        cont["genero_display"] = cont["genero"].apply(lambda x: f"{str(x).capitalize()}")
        st.plotly_chart(px.pie(cont, names="genero_display", values="quantidade", hole=0.4), use_container_width=True)

with col_b:
    st.markdown("#### 🏘️ Plantas por bairro")
    if not df_plantas_filtrado.empty:
        cont = df_plantas_filtrado["bairro"].value_counts().reset_index()
        cont.columns = ["bairro", "quantidade"]
        cont["bairro_display"] = cont["bairro"].apply(lambda x: f"{str(x).replace('_', ' ').capitalize()}")
        st.plotly_chart(px.bar(cont, x="quantidade", y="bairro_display", orientation="h", color="quantidade"), use_container_width=True)

# 10. Análise da Água
st.markdown("---")
st.markdown("### 💧 Análise Físico-Química da Água (Fatores de Risco)")
df_agua = df_dados_filtrado.dropna(subset=["ph_agua", "presenca_imaturos"]).copy()
df_agua["status_imatur"] = df_agua["presenca_imaturos"].map({"presenca": "Com Larvas", "ausencia": "Sem Larvas"})
df_agua = df_agua[df_agua["status_imatur"].isin(["Com Larvas", "Sem Larvas"])]

col_grafico1, col_grafico2 = st.columns(2)
with col_grafico1:
    st.markdown("#### 🧪 pH da Água vs. Presença de Larvas")
    if not df_agua.empty and df_agua["ph_agua"].notna().any():
        fig_ph = px.box(df_agua, x="status_imatur", y="ph_agua", color="status_imatur", points="all", color_discrete_map={"Com Larvas": "#E63946", "Sem Larvas": "#2E86AB"})
        fig_ph.update_layout(showlegend=False, xaxis_title="Status", yaxis_title="pH da Água")
        st.plotly_chart(fig_ph, use_container_width=True)
    else:
        st.info("Sem dados de pH.")

with col_grafico2:
    st.markdown("#### 🌡️ Temperatura x Volume de Água")
    df_temp = df_dados_filtrado.dropna(subset=["temp_agua_c", "volume_agua_ml", "presenca_imaturos"]).copy()
    df_temp["status_imatur"] = df_temp["presenca_imaturos"].map({"presenca": "Com Larvas", "ausencia": "Sem Larvas"})
    if not df_temp.empty:
        fig_vol = px.scatter(df_temp, x="volume_agua_ml", y="temp_agua_c", color="status_imatur", size="volume_agua_ml", color_discrete_map={"Com Larvas": "#E63946", "Sem Larvas": "#2E86AB"})
        st.plotly_chart(fig_vol, use_container_width=True)
    else:
        st.info("Sem dados de volume/temperatura.")

# --- NOVO: NOTAS E INTERCORRÊNCIAS DE CAMPO ---
st.markdown("---")
st.markdown("### 📝 Notas e Intercorrências de Campo")
if "observacoes_visita" in df_dados_filtrado.columns:
    # Filtra apenas as observações que não estão vazias
    df_obs = df_dados_filtrado.dropna(subset=["observacoes_visita"]).copy()
    df_obs = df_obs[df_obs["observacoes_visita"].astype(str).str.strip() != ""]
    
    if not df_obs.empty:
        # Remove duplicatas da mesma visita
        df_obs = df_obs.drop_duplicates(subset=["id_bromelia_calc", "data_visita"])
        
        for _, row in df_obs.iterrows():
            data_str = pd.to_datetime(row["data_visita"]).strftime('%d/%m/%Y') if pd.notna(row["data_visita"]) else "Data não informada"
            st.info(f"**{data_str}** | Planta **{row['id_bromelia_calc']}** (Bairro: {row['bairro']}): *\"{row['observacoes_visita']}\"*")
    else:
        st.success("✅ Nenhuma intercorrência registrada nas visitas filtradas.")

# --- NOVO: NOTAS DO LABORATÓRIO ---
st.markdown("### 🔬 Notas do Laboratório")
if "observacoes_lab" in df_dados_filtrado.columns:
    df_lab_obs = df_dados_filtrado.dropna(subset=["observacoes_lab"]).copy()
    df_lab_obs = df_lab_obs[df_lab_obs["observacoes_lab"].astype(str).str.strip() != ""]
    
    if not df_lab_obs.empty:
        df_lab_obs = df_lab_obs.drop_duplicates(subset=["id_amostra_calc"])
        for _, row in df_lab_obs.iterrows():
            st.warning(f"**Amostra {row['id_amostra_calc']}**: *\"{row['observacoes_lab']}\"*")
    else:
        st.success("✅ Nenhuma observação registrada no laboratório para as amostras filtradas.")


# 9. Tabela Consolidada (Movida para o final)
st.markdown("---")
st.markdown("### 📋 Tabela consolidada de campo e laboratório")
colunas_uteis = ["id_bromelia_calc", "bairro", "genero", "data_visita", "id_amostra_calc", "especie_display", "resultado_real", "resultado_digitado"]
colunas_existentes = [c for c in colunas_uteis if c in df_dados_filtrado.columns]

if not df_dados_filtrado.empty and colunas_existentes:
    df_exibicao = df_dados_filtrado[colunas_existentes].rename(columns={
        "id_bromelia_calc": "Planta", "bairro": "Bairro", "genero": "Gênero", "data_visita": "Data Visita",
        "id_amostra_calc": "Amostra", "especie_display": "Espécie (Lab)", "resultado_real": "Result. Real", "resultado_digitado": "Result. Digitado"
    })
    df_exibicao["Gênero"] = df_exibicao["Gênero"].apply(lambda x: f"{str(x).capitalize()}")
    st.dataframe(df_exibicao, use_container_width=True, height=400)

# --- RODAPÉ ---
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: gray; font-size: 14px; padding: 20px;">
    Dashboard desenvolvido por <b>Flávio Santos</b><br>
    Mestrado Profissional em Vigilância e Controle de Vetores (PPG-VCV) - IOC / Fiocruz<br>
    Contato: fhsantos@gmail.com | Dados atualizados via KoboToolbox
</div>
""", unsafe_allow_html=True)