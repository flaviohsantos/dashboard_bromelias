# -*- coding: utf-8 -*-
"""Temas visuais para o dashboard — baseados em DESIGN.md da biblioteca designmd.app.br.

Cada tema é um dicionário de tokens. A função `css_do_tema()` gera o bloco <style>
que o app.py injeta via st.markdown(unsafe_allow_html=True).

Temas disponíveis:
  - "Data-Dense Dashboard"      → https://designmd.app.br/library/data-dense-dashboard
  - "CRM Copper Sand"           → https://designmd.app.br/library/crm-copper-sand
  - "Bento Dados Estruturados"  → https://designmd.app.br/library/bento-dados-estruturados
"""

TEMAS = {
    # ═══════════════════════════════════════════════════════════════════
    # 1. DATA-DENSE DASHBOARD (BI/Analytics, light + dark)
    # ═══════════════════════════════════════════════════════════════════
    "Data-Dense Dashboard": {
        "label": "📊 Data-Dense Dashboard (BI)",
        "descricao": "Denso, técnico, cores semânticas claras. Ideal para BI.",
        "modo": "light",  # ou "dark" — usuário escolhe no toggle
        # Cores (do DESIGN.md)
        "bg": "#F5F5F5",
        "surface": "#FFFFFF",
        "text": "#333333",
        "text_muted": "#6B7280",
        "primary": "#22C55E",      # verde (sucesso / negativo)
        "warning": "#F59E0B",      # âmbar (atenção)
        "danger": "#EF4444",       # vermelho (positivo / alerta)
        "border": "#E5E7EB",
        # Tipografia
        "font": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "font_mono": "'JetBrains Mono', 'Courier New', monospace",
        "radius": "8px",
        "shadow": "0 2px 8px rgba(0,0,0,0.08)",
        # Integrações
        "plotly_template": "plotly_white",
        "map_tiles": "CartoDB positron",
        "map_tiles_dark": "CartoDB dark_matter",
    },

    # ═══════════════════════════════════════════════════════════════════
    # 2. CRM COPPER SAND (SaaS moderno, light)
    # ═══════════════════════════════════════════════════════════════════
    "CRM Copper Sand": {
        "label": "🟤 CRM Copper Sand (SaaS)",
        "descricao": "Quente, areia + cobre, tipografia Geist. SaaS moderno.",
        "modo": "light",
        "bg": "#F2F1ED",
        "surface": "#FFFFFF",
        "text": "#111827",
        "text_muted": "#6B7280",
        "primary": "#C08532",      # cobre
        "warning": "#DC2626",      # vermelho (alerta)
        "danger": "#DC2626",       # vermelho (positivo)
        "border": "#E5E7EB",
        "font": "'Geist', -apple-system, 'Segoe UI', sans-serif",
        "font_mono": "'JetBrains Mono', monospace",
        "radius": "8px",
        "shadow": "0 2px 12px rgba(0,0,0,0.06)",
        "plotly_template": "plotly_white",
        "map_tiles": "CartoDB positron",
        "map_tiles_dark": "CartoDB dark_matter",
    },

    # ═══════════════════════════════════════════════════════════════════
    # 3. BENTO DADOS ESTRUTURADOS (Bento grid, light)
    # ═══════════════════════════════════════════════════════════════════
    "Bento Dados Estruturados": {
        "label": "🍱 Bento Dados Estruturados",
        "descricao": "Bento grid, Roboto Mono, paleta vibrante. Moderno.",
        "modo": "light",
        "bg": "#ECF0F1",
        "surface": "#FFFFFF",
        "text": "#2C3E50",
        "text_muted": "#7F8C8D",
        "primary": "#20B2AA",      # verde-água (negativo)
        "warning": "#FF8C00",      # laranja (atenção)
        "danger": "#8A2BE2",       # roxo (positivo) — do DESIGN.md
        "border": "#D5DBDB",
        "font": "'Roboto Mono', 'Courier New', monospace",
        "font_mono": "'Roboto Mono', monospace",
        "radius": "16px",
        "shadow": "0 2px 12px rgba(0,0,0,0.06)",
        "plotly_template": "plotly_white",
        "map_tiles": "CartoDB positron",
        "map_tiles_dark": "CartoDB dark_matter",
    },
}

TEMA_PADRAO = "Data-Dense Dashboard"


def _hex_para_rgba(hex_cor, alpha):
    """Converte #RRGGBB para rgba(r,g,b,alpha)."""
    h = hex_cor.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def css_do_tema(nome_tema: str, dark: bool = False) -> str:
    """Gera o bloco <style> completo para o tema escolhido.

    Args:
        nome_tema: chave em TEMAS (ex.: "Data-Dense Dashboard")
        dark: se True, aplica variante escura (só Data-Dense suporta plenamente)
    """
    t = TEMAS[nome_tema].copy()

    # ── Variante dark (só Data-Dense tem suporte pleno) ──
    if dark and nome_tema == "Data-Dense Dashboard":
        t["bg"] = "#111827"
        t["surface"] = "#1F2937"
        t["text"] = "#F9FAFB"
        t["text_muted"] = "#9CA3AF"
        t["border"] = "#374151"
        t["shadow"] = "0 2px 8px rgba(0,0,0,0.4)"
        t["plotly_template"] = "plotly_dark"
        tiles = t["map_tiles_dark"]
    else:
        tiles = t["map_tiles"]

    # ── Tokens derivados ──
    primary_rgba = _hex_para_rgba(t["primary"], 0.12)
    warning_rgba = _hex_para_rgba(t["warning"], 0.12)
    danger_rgba = _hex_para_rgba(t["danger"], 0.12)

    return f"""
<style>
/* ═══════════════════════════════════════════════════════════════════
   TEMA: {nome_tema} {'(dark)' if dark else '(light)'}
   Gerado por themes.py — não edite aqui, edite o dicionário TEMAS
   ═══════════════════════════════════════════════════════════════════ */
:root {{
  --bg: {t['bg']};
  --surface: {t['surface']};
  --text: {t['text']};
  --text-muted: {t['text_muted']};
  --primary: {t['primary']};
  --warning: {t['warning']};
  --danger: {t['danger']};
  --border: {t['border']};
  --radius: {t['radius']};
  --shadow: {t['shadow']};
  --font: {t['font']};
  --font-mono: {t['font_mono']};
  --primary-rgba: {primary_rgba};
  --warning-rgba: {warning_rgba};
  --danger-rgba: {danger_rgba};
}}

/* ── Base ── */
.stApp {{
  background-color: var(--bg);
  color: var(--text);
  font-family: var(--font);
}}
h1, h2, h3, h4, h5, h6 {{
  font-family: var(--font);
  color: var(--text);
  letter-spacing: -0.01em;
}}
p, span, div, label {{
  font-family: var(--font);
}}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {{
  background-color: var(--surface);
  border-right: 1px solid var(--border);
}}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
  color: var(--text);
}}

/* ── Métricas (KPI cards) ── */
div[data-testid="stMetric"] {{
  background-color: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
  box-shadow: var(--shadow);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}}
div[data-testid="stMetric"]:hover {{
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.10);
}}
div[data-testid="stMetricLabel"] {{
  color: var(--text-muted);
  font-family: var(--font);
  font-size: 0.875rem;
  font-weight: 500;
}}
div[data-testid="stMetricValue"] {{
  color: var(--text);
  font-family: var(--font);
  font-weight: 700;
}}

/* ── DataFrames ── */
div[data-testid="stDataFrame"] {{
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}}

/* ── Tabs ── */
button[data-baseweb="tab"] {{
  font-family: var(--font);
  font-weight: 500;
  color: var(--text-muted);
}}
button[data-baseweb="tab"][aria-selected="true"] {{
  color: var(--primary);
  border-bottom-color: var(--primary);
}}

/* ── Botões ── */
.stButton > button {{
  font-family: var(--font);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background-color: var(--surface);
  color: var(--text);
  font-weight: 600;
  transition: all 0.2s ease;
}}
.stButton > button:hover {{
  border-color: var(--primary);
  color: var(--primary);
  transform: translateY(-1px);
}}

/* ── Divisores ── */
hr {{
  border-color: var(--border);
  opacity: 0.5;
}}

/* ── Cards de alerta (substituem o HTML inline do app.py) ── */
.card-alerta {{
  padding: 16px 20px;
  border-radius: var(--radius);
  border-left: 5px solid;
  background-color: var(--surface);
  box-shadow: var(--shadow);
  height: 100%;
}}
.card-alerta h4 {{
  margin-top: 0;
  margin-bottom: 8px;
  font-size: 1.1rem;
}}
.card-alerta p {{
  margin-bottom: 0;
  font-size: 14px;
  color: var(--text-muted);
}}
.card-alerta.baixo {{
  background-color: {_hex_para_rgba(t['primary'], 0.10)};
  border-left-color: var(--primary);
}}
.card-alerta.baixo h4 {{ color: var(--primary); }}
.card-alerta.medio {{
  background-color: {warning_rgba};
  border-left-color: var(--warning);
}}
.card-alerta.medio h4 {{ color: var(--warning); }}
.card-alerta.alto {{
  background-color: {danger_rgba};
  border-left-color: var(--danger);
}}
.card-alerta.alto h4 {{ color: var(--danger); }}
.card-alerta.sem-dados {{
  background-color: {_hex_para_rgba(t['text_muted'], 0.10)};
  border-left-color: var(--text-muted);
}}
.card-alerta.sem-dados h4 {{ color: var(--text-muted); }}

/* ── Código / monoespaçado (códigos de amostra) ── */
code, .mono {{
  font-family: var(--font-mono);
  background-color: {_hex_para_rgba(t['text'], 0.05)};
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
}}

/* ── Caption (texto pequeno) ── */
.stCaption, small {{
  color: var(--text-muted);
  font-family: var(--font);
}}

/* ── Expander ── */
details {{
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background-color: var(--surface);
  padding: 8px 12px;
  margin-bottom: 8px;
}}
details summary {{
  font-family: var(--font);
  font-weight: 500;
  color: var(--text);
}}

/* ── Plotly (garante que o fundo acompanhe o tema) ── */
.js-plotly-plot .plotly .main-svg {{
  background: transparent !important;
}}

/* ── Scrollbar (sutil, opcional) ── */
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: var(--bg); }}
::-webkit-scrollbar-thumb {{
  background: var(--border);
  border-radius: 5px;
}}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-muted); }}
</style>
"""


def tokens_plotly(nome_tema: str, dark: bool = False) -> dict:
    """Retorna o dict de configuração visual para Plotly conforme o tema."""
    t = TEMAS[nome_tema]
    if dark and nome_tema == "Data-Dense Dashboard":
        return {
            "template": "plotly_dark",
            "paper_bgcolor": t["bg"],
            "plot_bgcolor": t["surface"],
            "font_color": t["text"],
        }
    return {
        "template": t["plotly_template"],
        "paper_bgcolor": t["bg"],
        "plot_bgcolor": t["surface"],
        "font_color": t["text"],
    }


def tiles_folium(nome_tema: str, dark: bool = False) -> str:
    """Retorna o nome do tiles Folium conforme o tema."""
    t = TEMAS[nome_tema]
    if dark and nome_tema == "Data-Dense Dashboard":
        return t["map_tiles_dark"]
    return t["map_tiles"]


def cores_status(nome_tema: str, dark: bool = False) -> dict:
    """Retorna o dict STATUS_CORES conforme o tema (positivo = danger, negativo = primary)."""
    t = TEMAS[nome_tema].copy()
    if dark and nome_tema == "Data-Dense Dashboard":
        # No dark, mantém as mesmas cores semânticas (verde/vermelho)
        pass
    return {
        "Positivo": t["danger"],
        "Negativo": t["primary"],
        "Sem análise": t["text_muted"],
    }