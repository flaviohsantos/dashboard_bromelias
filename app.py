import streamlit as st
import kobo_api

st.write("# Teste de Conexão")
st.write("Se você está vendo esta mensagem, o app está rodando!")

try:
    base_url = kobo_api._get_secret("KOBO_URL", "https://kf.kobotoolbox.org")
    token = kobo_api._get_secret("KOBO_TOKEN")
    uid_campo = kobo_api._get_secret("UID_CAMPO")
    
    st.write("✅ Token carregado com sucesso.")
    
    with st.spinner("Tentando conectar ao Kobo..."):
        lista_campo = kobo_api.baixar_formulario(uid_campo, token, base_url)
        st.write(f"✅ Conexão bem-sucedida! O Kobo enviou {len(lista_campo)} registros de campo.")
        
except Exception as e:
    st.error(f"❌ Ocorreu um erro: {e}")