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

if not token or not uid_campo:
    st.error("⚠️ Configure KOBO_TOKEN e UID_CAMPO em .streamlit/secrets.toml")
    st.stop()

with st.spinner("Baixando dados..."):
    lista_campo = baixar_formulario(uid_campo, token, base_url)
    lista_lab = baixar_formulario(uid_lab, token, base_url)
    df_plantas, df_dados = preparar_dados_completos(lista_campo, lista_lab)

if df_plantas.empty:
    st.warning("Nenhum dado encontrado.")
    st.stop()

# --- AUDITORIA DE DADOS (NOVO) ---
# Limpa a coluna de espécies e resultado
df_dados["especie_identificada"] = df_dados["especie_identificada"].fillna("nao_identificado").astype(str)
df_dados["resultado_amostra"] = df_dados["resultado_amostra"].fillna("nao_processado").astype(str)

# Regra de Ouro: Tem Aedes = Positivo. Não tem Aedes = Negativo.
df_dados["tem_aedes"] = df_dados["especie_identificada"].str.contains("aedes", case=False)
df_dados["tem_outros"] = df_dados["especie_identificada"].str.contains("culex|nao_identificado", case=False)

# Cria as máscaras de erro
# Erro 1: Tem Aedes, mas marcou como Negativo
erro_1 = (df_dados["tem_aedes"] == True) & (df_dados["resultado_amostra"].str.lower() == "negativo")

# Erro 2: Não tem Aedes (só tem Culex ou Não Identificado), mas marcou como Positivo
erro_2 = (df_dados["tem_aedes"] == False) & (df_dados["resultado_amostra"].str.lower() == "positivo")

# Junta os erros
df_erros = df_dados[erro_1 | erro_2].copy()

# Criação do Alerta na Barra Lateral
with st.sidebar:
    st.markdown("---")
    st.markdown("### 🚨 Auditoria de Laboratório")
    
    if not df_erros.empty:
        st.error(f"⚠️ Foram encontrados **{len(df_erros)}** erros de seleção no laboratório.")
        st.write("Clique no código da amostra para ver o detalhe:")
        
        # Loop para criar os botões de erro
        for idx, row in df_erros.iterrows():
            amostra = row['id_amostra_calc']
            planta = row['id_bromelia_calc']
            
            # Define o texto do botão dependendo do tipo de erro
            if row["tem_aedes"] and row["resultado_amostra"].lower() == "negativo":
                texto_botao = f"🔍 Amostra {amostra} (Falso Negativo)"
            else:
                texto_botao = f"🔍 Amostra {amostra} (Falso Positivo)"
            
            # Cria um expansor (popup) para cada erro
            with st.expander(texto_botao):
                st.write(f"**Planta:** {planta}")
                st.write(f"**Data da Visita:** {row['data_visita']}")
                st.write(f"**Espécie encontrada:** {row['especie_identificada']}")
                st.write(f"**O que foi digitado:** {row['resultado_amostra'].capitalize()}")
                
                if row["tem_aedes"] and row["resultado_amostra"].lower() == "negativo":
                    st.warning("Erro: A amostra contém *Aedes*, mas foi marcada como Negativa.")
                else:
                    st.warning("Erro: A amostra não contém *Aedes* (apenas Culex/Outro), mas foi marcada como Positiva.")
    else:
        st.success("✅ Nenhum erro de seleção encontrado no laboratório.")

# 2. Filtros (Apenas Bairro e Gênero)
st.sidebar.header("🔎 Filtros")
bairros = sorted(df_plantas["bairro"].dropna().unique())
bairro_sel = st.sidebar.multiselect("Bairro", bairros, default=bairros)

generos = sorted(df_plantas["genero"].dropna().unique())
genero_sel = st.sidebar.multiselect("Gênero da bromélia", generos, default=generos)

# 3. Aplicar filtros
df_plantas_filtrado = df_plantas.copy()
df_dados_filtrado = df_dados.copy()

if bairro_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["bairro"].isin(bairro_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["bairro"].isin(bairro_sel)]

if genero_sel:
    df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["genero"].isin(genero_sel)]
    df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["genero"].isin(genero_sel)]

# 4. KPIs (Usando a nova regra de positividade corrigida)
st.markdown("### 📊 Indicadores-chave")
c1, c2, c3, c4, c5 = st.columns(5)

n_plantas = df_plantas_filtrado["id_bromelia_calc"].nunique()
n_visitas = df_dados_filtrado["data_visita"].notna().sum() if "data_visita" in df_dados_filtrado.columns else 0
n_amostras = df_dados_filtrado["id_amostra_calc"].nunique() if "id_amostra_calc" in df_dados_filtrado.columns else 0

amostras_com_aedes = df_dados_filtrado[df_dados_filtrado["tem_aedes"] == True]["id_amostra_calc"].nunique()
positividade = (amostras_com_aedes / n_amostras * 100) if n_amostras > 0 else 0

total_especimes = pd.to_numeric(df_dados_filtrado["soma_contagem"], errors="coerce").sum() if "soma_contagem" in df_dados_filtrado.columns else 0

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
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]], radius=7, color="blue", fill=True, fill_color="blue", fill_opacity=0.7,
            popup=f"<b>{row['id_bromelia_calc']}</b><br>Gênero: {row['genero']}<br>Bairro: {row['bairro']}"
        ).add_to(m)
    st_folium(m, width=None, height=500)

# 6. Série temporal
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

# 7. Gráficos de Espécies e Tabela de Percentuais
st.markdown("---")
col_esq, col_dir = st.columns([2, 1])

with col_esq:
    st.markdown("### 🦟 Frequência de Espécies Identificadas")
    df_especies_counts = df_dados_filtrado.groupby("especie_identificada").agg(
        Total_Larvas=("soma_contagem", "sum"),
        Amostras=("id_amostra_calc", "nunique")
    ).reset_index().sort_values(by="Total_Larvas", ascending=False)
    
    fig_esp = px.bar(
        df_especies_counts, 
        x="especie_identificada", 
        y="Total_Larvas",
        color="especie_identificada",
        text="Total_Larvas",
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    fig_esp.update_layout(showlegend=False, xaxis_title="", yaxis_title="Qtd. de Espécimes")
    st.plotly_chart(fig_esp, use_container_width=True)

with col_dir:
    st.markdown("### 📋 Totais e Percentuais")
    
    # Garante que a coluna é numérica e não tem valores nulos que travam a conta
    df_especies_counts["Total_Larvas"] = pd.to_numeric(df_especies_counts["Total_Larvas"], errors="coerce").fillna(0)
    total_geral = df_especies_counts["Total_Larvas"].sum()
    
    # Calcula o percentual de forma segura
    if total_geral > 0:
        percentual = (df_especies_counts["Total_Larvas"] / total_geral * 100).round(1)
        df_especies_counts["Percentual (%)"] = percentual.astype(str) + "%"
    else:
        df_especies_counts["Percentual (%)"] = "0%"
    
    # Renomeia colunas para ficarem bonitas
    df_especies_counts.columns = ["Espécie", "Total de Larvas", "Nº de Amostras", "Percentual (%)"]
    
    # Mostra a tabela no Streamlit
    st.dataframe(df_especies_counts, hide_index=True, use_container_width=True)
    
    df_especies_counts.columns = ["Espécie", "Total de Larvas", "Nº de Amostras", "Percentual (%)"]
    st.dataframe(df_especies_counts, hide_index=True, use_container_width=True)

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
colunas_uteis = ["id_bromelia_calc", "bairro", "genero", "data_visita", "presenca_imaturos", "id_amostra_calc", "especie_identificada", "tem_aedes", "resultado_amostra"]
colunas_existentes = [c for c in colunas_uteis if c in df_dados_filtrado.columns]

if not df_dados_filtrado.empty and colunas_existentes:
    df_exibicao = df_dados_filtrado[colunas_existentes].copy()
    df_exibicao["tem_aedes"] = df_exibicao["tem_aedes"].map({True: "SIM (Risco)", False: "NÃO"})
    
    df_exibicao = df_exibicao.rename(columns={
        "id_bromelia_calc": "Planta",
        "bairro": "Bairro",
        "genero": "Gênero",
        "data_visita": "Data Visita",
        "presenca_imaturos": "Imaturos (Campo)",
        "id_amostra_calc": "Amostra",
        "especie_identificada": "Espécie (Lab)",
        "tem_aedes": "Status de Risco",
        "resultado_amostra": "Result. Digitado"
    })
    st.dataframe(df_exibicao, use_container_width=True, height=400)
else:
    st.info("Nenhum dado para exibir na tabela.")