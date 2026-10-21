import streamlit as st
import requests

st.title("🔍 Teste de Conexão com o Kobo")

# Puxa as credenciais
try:
    token = st.secrets["KOBO_TOKEN"]
    uid_campo = st.secrets["UID_CAMPO"]
    base_url = st.secrets["KOBO_URL"]
    st.success("✅ Credenciais carregadas do secrets.toml")
    st.write(f"Token começa com: {token[:10]}...")
    st.write(f"UID do Campo: {uid_campo}")
except Exception as e:
    st.error(f"❌ Erro ao ler o secrets.toml: {e}")
    st.stop()

# Tenta acessar a API
url = f"{base_url}/api/v2/assets/{uid_campo}/data/"
headers = {"Authorization": f"Token {token}"}

st.write(f"Tentando acessar: {url}")

try:
    r = requests.get(url, headers=headers, timeout=10)
    st.write(f"Código de status da resposta: {r.status_code}")
    
    if r.status_code == 200:
        st.success("✅ Conexão BEM-SUCEDIDA! O token e o UID estão corretos.")
        dados = r.json()
        st.write(f"O Kobo retornou {len(dados.get('results', []))} registros.")
    elif r.status_code == 401:
        st.error("❌ Erro 401: Token inválido ou expirado. Verifique o KOBO_TOKEN.")
    elif r.status_code == 404:
        st.error("❌ Erro 404: UID do formulário não encontrado. Verifique o UID_CAMPO.")
    else:
        st.error(f"❌ Erro {r.status_code}: {r.text}")
        
except Exception as e:
    st.error(f"❌ Erro de conexão: {e}")
