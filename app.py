# 2. MAPAS (COM ABAS: BASE E CALOR)
st.markdown("### 🗺️ Mapas de Risco Georreferenciados")
df_mapa = df_final.dropna(subset=["lat", "lon"])

if not df_mapa.empty:
    centro_lat = df_mapa["lat"].mean()
    centro_lon = df_mapa["lon"].mean()
    
    # Cria as abas
    tab1, tab2 = st.tabs(["📍 Mapa Base e Raio (100m)", "🔥 Mapa de Calor (Apenas Focos)"])
    
    # --- ABA 1: MAPA BASE COM RAIO ---
    with tab1:
        m1 = folium.Map(location=[centro_lat, centro_lon], zoom_start=16, tiles="OpenStreetMap")
        for _, row in df_mapa.iterrows():
            if row["positivo"]:
                folium.Circle(location=[row["lat"], row["lon"]], radius=100, color="#E63946", fill=True, fill_opacity=0.2, weight=2).add_to(m1)
                folium.Marker(location=[row["lat"], row["lon"]], icon=folium.Icon(color="red", icon="info-sign"), popup=f"<b>{row['id_bromelia']}</b><br>POSITIVO").add_to(m1)
            else:
                folium.Marker(location=[row["lat"], row["lon"]], icon=folium.Icon(color="blue", icon="info-sign"), popup=f"<b>{row['id_bromelia']}</b><br>Negativo").add_to(m1)
        st_folium(m1, width=None, height=500, key="mapa1")
        
    # --- ABA 2: MAPA DE CALOR ---
    with tab2:
        # Usa um fundo escuro para o calor brilhar mais
        m2 = folium.Map(location=[centro_lat, centro_lon], zoom_start=15, tiles="CartoDB dark_matter")
        
        # Filtra apenas as plantas positivas para gerar o calor
        df_calor = df_mapa[df_mapa["positivo"]]
        
        if not df_calor.empty:
            from folium.plugins import HeatMap
            heat_data = [[r["lat"], r["lon"]] for _, r in df_calor.iterrows()]
            HeatMap(heat_data, radius=40, blur=25, min_opacity=0.8).add_to(m2)
            st_folium(m2, width=None, height=500, key="mapa2")
        else:
            st.info("✅ Nenhuma planta positiva para gerar o mapa de calor no momento.")
else:
    st.info("Sem coordenadas para o mapa.")
