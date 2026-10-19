import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from datetime import datetime
import time

  # Importação do módulo kobo_api
import kobo_api

st.set_page_config(page_title="Bromélias & Culicídeos", page_icon="🌿", layout="wide")

  # --- DIAGNÓSTICO DE VERSÃO ---
  # Se você ver "VERSÃO 2.0" na tela, significa que o código atualizou!
st.markdown("🚀 **Versão do App: 2.0 (Diagnóstico)**")

  # --- CABEÇALHO ---
st.title("🌿 Dashboard — Bromélias Ornamentais Urbanas e Culicídeos")
st.markdown("**Pesquisador:** Flávio Santos (Mestrado Profissional - IOC - Fiocruz) | **Contato:**
  fhsantos@gmail.com")
fhsantos@gmail.com")
  st.caption(f"Última atualização dos dados: {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
  st.markdown("---")

  # --- CARREGAMENTO COM DIAGNÓSTICO ---
  st.info("🔍 Iniciando processo de conexão com Kobo Toolbox...")

  try:
      base_url = kobo_api._get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
      token = kobo_api._get_secret("KOBO_TOKEN")
      uid_campo = kobo_api._get_secret("UID_CAMPO")
      uid_lab = kobo_api._get_secret("UID_LAB")

      st.write("✅ Segredos (Tokens) carregados com sucesso.")

      with st.spinner("Baixando dados do Kobo..."):
          st.write("📡 Tentando conectar ao Kobo (Formulário de Campo)...")
          lista_campo = kobo_api.baixar_formulario(uid_campo, token, base_url)
          st.write(f"✅ Dados do Campo baixados com sucesso! ({len(lista_campo)} registros)")

          st.write("📡 Tentando conectar ao Kobo (Formulário de Lab)...")
          lista_lab = kobo_api.baixar_formulario(uid_lab, token, base_url)
          st.write(f"✅ Dados do Lab baixados com sucesso! ({len(lista_lab)} registros)")

          st.write("⚙️ Processando e cruzando dados...")
          df_plantas, df_dados = kobo_api.preparar_dados_completos(lista_campo, lista_lab)
          st.write("✅ Processamento concluído!")

  except Exception as e:
      st.error(f"❌ Erro crítico durante o carregamento: {e}")
      st.stop()

  if df_plantas.empty:
      st.warning("⚠️ Nenhum dado encontrado nos formulários.")
      st.stop()

  # --- TRATAMENTO ---
  df_dados["resultado_digitado"] = df_dados["resultado_digitado"].astype(str).str.lower().str.strip().replace(["nan",
  "none", ""], "nao_processado")
  df_dados["resultado_real"] = df_dados["resultado_real"].fillna("Nenhum")
  df_dados["soma_contagem"] = pd.to_numeric(df_dados["soma_contagem"], errors="coerce").fillna(0)
  df_dados.loc[df_dados["soma_contagem"] > 200, "soma_contagem"] = 0

  df_erros = df_dados[
      ((df_dados["resultado_real"] == "Positivo (Aedes)") & (df_dados["resultado_digitado"] == "negativo")) |
      ((df_dados["resultado_real"] == "Negativo (Outros)") & (df_dados["resultado_digitado"] == "positivo"))
  ].copy()

  # --- MENU LATERAL ---
  with st.sidebar:
      st.markdown("### 🚨 Auditoria")
      if not df_erros.empty:
          st.error(f"⚠️ Encontrados **{len(df_erros)}** erros.")
          for idx, row in df_erros.iterrows():
              with st.expander(f"🔍 Amostra {row['id_amostra_calc']}"):
                  st.write(f"**Espécie:** {row['especie_identificada'].replace('_', ' ').capitalize()}")
                  st.write(f"**Digitou:** {row['resultado_digitado'].capitalize()} | **Correto:**
  {row['resultado_real']}")
      else:
          st.success("✅ Nenhum erro de seleção.")

      st.markdown("---")
      st.header("🔎 Filtros")
      bairros = sorted(df_plantas["bairro"].dropna().unique())
      bairro_sel = st.multiselect("Bairro", bairros, default=bairros)
      generos = sorted(df_plantas["genero"].dropna().unique())
      genero_sel = st.multiselect("Gênero", generos, default=generos)

      st.markdown("---")
      st.markdown("### 🗺️ Mapa")
      tipo_mapa = st.radio("Selecione:", ["Mapa Base e Raio (100m)", "🔥 Mapa de Calor"])

  df_plantas_filtrado = df_plantas.copy()
  df_dados_filtrado = df_dados.copy()

  if bairro_sel:
      df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["bairro"].isin(bairro_sel)]
      df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["bairro"].isin(bairro_sel)]
  if genero_sel:
      df_plantas_filtrado = df_plantas_filtrado[df_plantas_filtrado["genero"].isin(genero_sel)]
      df_dados_filtrado = df_dados_filtrado[df_dados_filtrado["genero"].isin(genero_sel)]

  df_dados_filtrado["especie_display"] = df_dados_filtrado["especie_identificada"].apply(
      lambda x: f"{str(x).replace('_', ' ').capitalize()}" if pd.notna(x) and str(x).lower() != "nan" else "Não
  informado"
  )

  n_plantas = df_plantas_filtrado["id_bromelia_calc"].nunique()
  n_visitas = df_dados_filtrado["data_visita"].notna().sum()
  n_amostras = df_dados_filtrado["id_amostra_calc"].nunique()

  amostras_com_aedes =
  df_dados_filtrado[df_dados_filtrado["especie_identificada"].astype(str).str.lower().str.contains("aedes")]
  amostras_positivas = amostras_com_aedes["id_amostra_calc"].nunique()
  positividade = (amostras_positivas / n_amostras * 100) if n_amostras > 0 else 0
  total_especimes = df_dados_filtrado["soma_contagem"].sum()

  # --- MAPAS ---
  st.markdown("### 🗺️ Mapas de Risco e Termômetro")
  df_mapa = df_plantas_filtrado.dropna(subset=["latitude", "longitude"])
  ids_positivos = amostras_com_aedes["id_bromelia_calc"].unique()

  col_mapa, col_termo = st.columns([3, 1])
  with col_mapa:
      if not df_mapa.empty:
          if tipo_mapa == "Mapa Base e Raio (100m)":
              m1 = folium.Map(location=[-22.9661, -42.0272], zoom_start=15, tiles="OpenStreetMap")
              for _, row in df_mapa.iterrows():
                  if row["id_bromelia_calc"] in ids_positivos:
                      folium.Circle(location=[row["latitude"], row["longitude"]], radius=100, color="#E63946",
  fill=True, fill_opacity=0.2, weight=2).add_to(m1)
                      folium.Marker(location=[row["latitude"], row["longitude"]], icon=folium.Icon(color="red"),
  popup=f"{row['id_bromelia_calc']}").add_to(m1)
                  else:
                      folium.Marker(location=[row["latitude"], row["longitude"]], icon=folium.Icon(color="blue"),
  popup=f"{row['id_bromelia_calc']}").add_to(m1)
              st_folium(m1, width=None, height=500, key="mapa1")
          else:
              df_calor = df_mapa[df_mapa["id_bromelia_calc"].isin(ids_positivos)]
              if not df_calor.empty:
                  m2 = folium.Map(location=[-22.9661, -42.0272], zoom_start=14, tiles="OpenStreetMap")
                  heat_data = [[r["latitude"], r["longitude"]] for _, r in df_calor.iterrows()]
                  HeatMap(heat_data, radius=50, blur=30).add_to(m2)
                  st_folium(m2, width=None, height=500, key="mapa2")
              else:
                  st.info("Nenhum foco positivo.")

  with col_termo:
      st.markdown("#### 🌡️ Termômetro")
      if positividade < 15: cor, st_risco = "#2E86AB", "BAIXO"
      elif positividade < 40: cor, st_risco = "#F4A261", "MÉDIO"
      else: cor, st_risco = "#E63946", "ALTO"

      fig = go.Figure(go.Indicator(
          mode="gauge+number", value=positividade, number={'suffix': "%"},
          title={'text': st_risco},
          gauge={'axis': {'range': [0, 100]}, 'bar': {'color': cor},
                 'steps': [{'range': [0, 15], 'color': '#D6EAF8'}, {'range': [15, 40], 'color': '#FDEBD0'}, {'range':
  [40, 100], 'color': '#FADBD8'}]}
      ))
      fig.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10))
      st.plotly_chart(fig, width='stretch')

  # --- KPIs ---
  st.markdown("---")
  c1, c2, c3, c4 = st.columns(4)
  c1.metric("Plantas", n_plantas)
  c2.metric("Visitas", n_visitas)
  c3.metric("Amostras", n_amostras)
  c4.metric("Espécimes", int(total_especimes))

  st.markdown("#### 🌡️ Microclima")
  if not df_dados_filtrado.empty:
      m1, m2, m3, m4 = st.columns(4)
      m1.metric("pH Médio", f"{df_dados_filtrado['ph_agua'].astype(float).mean():.2f}")
      m2.metric("Temp. Média", f"{df_dados_filtrado['temp_agua_c'].astype(float).mean():.1f} °C")
      m3.metric("Volume Médio", f"{df_dados_filtrado['volume_agua_ml'].astype(float).mean():.0f} mL")

  # --- ESPÉCIES ---
  st.markdown("---")
  col_esq, col_dir = st.columns([2, 1])
  with col_esq:
      st.markdown("### 🦟 Espécies")
      df_esp = df_dados_filtrado.groupby("especie_display").agg(Total=("soma_contagem", "sum")).reset_index()
      if not df_esp.empty:
          st.plotly_chart(px.bar(df_esp, x="especie_display", y="Total", color="especie_display", text="Total"),
  width='stretch')

  with col_dir:
      st.markdown("### 📋 Totais")
      if not df_esp.empty:
          st.dataframe(df_esp.rename(columns={"especie_display": "Espécie", "Total": "Larvas"}), hide_index=True)

  # --- NOTAS ---
  st.markdown("---")
  st.markdown("### 📝 Notas de Campo")
  df_obs = df_dados_filtrado.dropna(subset=["observacoes_visita"])
  df_obs = df_obs[df_obs["observacoes_visita"].astype(str).str.lower() != "nan"]
  if not df_obs.empty:
      for _, r in df_obs.iterrows():
          st.info(f"**{r['id_bromelia_calc']}**: {r['observacoes_visita']}")
  else:
      st.success("Sem notas de campo.")

  # --- RODAPÉ ---
  st.markdown("---")
  st.caption("Dashboard desenvolvido por Flávio Santos | PPG-VCV / IOC - Fiocruz | Contato: fhsantos@gmail.com")