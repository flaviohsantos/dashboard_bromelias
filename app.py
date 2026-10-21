if not df_esp_chart.empty and df_esp_chart["Total"].sum() > 0:
    st.plotly_chart(px.bar(df_esp_chart, x="especie", y="Total", color="especie", text="Total"), use_container_width=True)
    
    st.markdown("#### 📋 Totais")
    # Correção visual da tabela
    df_tabela = df_esp_chart.rename(columns={"especie": "Espécie", "Total": "Larvas"})
    
    # Exibe a tabela com largura controlada
    st.dataframe(
        df_tabela, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Espécie": st.column_config.TextColumn(width="medium"),
            "Larvas": st.column_config.NumberColumn(width="small")
        }
    )
else:
    st.info("Nenhuma larva registrada.")