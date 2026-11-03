# -*- coding: utf-8 -*-
TEMAS = {
    "Data-Dense Dashboard": {
        "label": "📊 Data-Dense Dashboard (BI)", "descricao": "Denso, técnico, cores semânticas claras. Ideal para BI.",
        "bg": "#F5F5F5", "surface": "#FFFFFF", "text": "#333333", "text_muted": "#6B7280",
        "primary": "#22C55E", "warning": "#F59E0B", "danger": "#EF4444", "border": "#E5E7EB",
        "font": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", "font_mono": "'JetBrains Mono', monospace",
        "radius": "8px", "shadow": "0 2px 8px rgba(0,0,0,0.08)",
        "plotly_template": "plotly_white", "map_tiles": "CartoDB positron", "map_tiles_dark": "CartoDB dark_matter",
    },
    "CRM Copper Sand": {
        "label": "🟤 CRM Copper Sand (SaaS)", "descricao": "Quente, areia + cobre, tipografia Geist. SaaS moderno.",
        "bg": "#F2F1ED", "surface": "#FFFFFF", "text": "#111827", "text_muted": "#6B7280",
        "primary": "#C08532", "warning": "#DC2626", "danger": "#DC2626", "border": "#E5E7EB",
        "font": "'Geist', -apple-system, 'Segoe UI', sans-serif", "font_mono": "'JetBrains Mono', monospace",
        "radius": "8px", "shadow": "0 2px 12px rgba(0,0,0,0.06)",
        "plotly_template": "plotly_white", "map_tiles": "CartoDB positron", "map_tiles_dark": "CartoDB dark_matter",
    },
    "Bento Dados Estruturados": {
        "label": "🍱 Bento Dados Estruturados", "descricao": "Bento grid, Roboto Mono, paleta vibrante. Moderno.",
        "bg": "#ECF0F1", "surface": "#FFFFFF", "text": "#2C3E50", "text_muted": "#7F8C8D",
        "primary": "#20B2AA", "warning": "#FF8C00", "danger": "#8A2BE2", "border": "#D5DBDB",
        "font": "'Roboto Mono', 'Courier New', monospace", "font_mono": "'Roboto Mono', monospace",
        "radius": "16px", "shadow": "0 2px 12px rgba(0,0,0,0.06)",
        "plotly_template": "plotly_white", "map_tiles": "CartoDB positron", "map_tiles_dark": "CartoDB dark_matter",
    },
}
TEMA_PADRAO = "Data-Dense Dashboard"

def _hex_para_rgba(hex_cor, alpha):
    h = hex_cor.lstrip("#")
    if len(h) == 3: h = "".join(c * 2 for c in h)
    return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{alpha})"

def css_do_tema(nome_tema, dark=False):
    t = TEMAS[nome_tema].copy()
    if dark and nome_tema == "Data-Dense Dashboard":
        t["bg"], t["surface"], t["text"], t["text_muted"], t["border"], t["shadow"] = "#111827", "#1F2937", "#F9FAFB", "#9CA3AF", "#374151", "0 2px 8px rgba(0,0,0,0.4)"
    primary_rgba = _hex_para_rgba(t["primary"], 0.12)
    warning_rgba = _hex_para_rgba(t["warning"], 0.12)
    danger_rgba = _hex_para_rgba(t["danger"], 0.12)
    return f"""<style>
:root {{ --bg: {t['bg']}; --surface: {t['surface']}; --text: {t['text']}; --text-muted: {t['text_muted']}; --primary: {t['primary']}; --warning: {t['warning']}; --danger: {t['danger']}; --border: {t['border']}; --radius: {t['radius']}; --shadow: {t['shadow']}; --font: {t['font']}; --font-mono: {t['font_mono']}; }}
.stApp {{ background-color: var(--bg); color: var(--text); font-family: var(--font); }}
h1, h2, h3, h4, h5, h6, p, span, div, label {{ font-family: var(--font); color: var(--text); letter-spacing: -0.01em; }}
section[data-testid="stSidebar"] {{ background-color: var(--surface); border-right: 1px solid var(--border); }}
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {{ color: var(--text); }}
div[data-testid="stMetric"] {{ background-color: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 20px; box-shadow: var(--shadow); transition: transform 0.2s ease, box-shadow 0.2s ease; }}
div[data-testid="stMetric"]:hover {{ transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.10); }}
div[data-testid="stMetricLabel"] {{ color: var(--text-muted); font-size: 0.875rem; font-weight: 500; }}
div[data-testid="stMetricValue"] {{ color: var(--text); font-weight: 700; }}
div[data-testid="stDataFrame"] {{ border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }}
button[data-baseweb="tab"] {{ font-family: var(--font); font-weight: 500; color: var(--text-muted); }}
button[data-baseweb="tab"][aria-selected="true"] {{ color: var(--primary); border-bottom-color: var(--primary); }}
.stButton > button {{ font-family: var(--font); border-radius: var(--radius); border: 1px solid var(--border); background-color: var(--surface); color: var(--text); font-weight: 600; transition: all 0.2s ease; }}
.stButton > button:hover {{ border-color: var(--primary); color: var(--primary); transform: translateY(-1px); }}
hr {{ border-color: var(--border); opacity: 0.5; }}
.card-alerta {{ padding: 16px 20px; border-radius: var(--radius); border-left: 5px solid; background-color: var(--surface); box-shadow: var(--shadow); height: 100%; }}
.card-alerta h4 {{ margin-top: 0; margin-bottom: 8px; font-size: 1.1rem; }}
.card-alerta p {{ margin-bottom: 0; font-size: 14px; color: var(--text-muted); }}
.card-alerta.baixo {{ background-color: {_hex_para_rgba(t['primary'], 0.10)}; border-left-color: var(--primary); }}
.card-alerta.baixo h4 {{ color: var(--primary); }}
.card-alerta.medio {{ background-color: {warning_rgba}; border-left-color: var(--warning); }}
.card-alerta.medio h4 {{ color: var(--warning); }}
.card-alerta.alto {{ background-color: {danger_rgba}; border-left-color: var(--danger); }}
.card-alerta.alto h4 {{ color: var(--danger); }}
.card-alerta.sem-dados {{ background-color: {_hex_para_rgba(t['text_muted'], 0.10)}; border-left-color: var(--text-muted); }}
.card-alerta.sem-dados h4 {{ color: var(--text-muted); }}
code, .mono {{ font-family: var(--font-mono); background-color: {_hex_para_rgba(t['text'], 0.05)}; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
.stCaption, small {{ color: var(--text-muted); font-family: var(--font); }}
details {{ border: 1px solid var(--border); border-radius: var(--radius); background-color: var(--surface); padding: 8px 12px; margin-bottom: 8px; }}
details summary {{ font-weight: 500; color: var(--text); }}
.js-plotly-plot .plotly .main-svg {{ background: transparent !important; }}
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: var(--bg); }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 5px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--text-muted); }}
</style>"""

def tokens_plotly(nome_tema, dark=False):
    t = TEMAS[nome_tema]
    return {"template": "plotly_dark" if dark else t["plotly_template"], "paper_bgcolor": t["bg"] if not dark else "#111827", "plot_bgcolor": t["surface"] if not dark else "#1F2937", "font_color": t["text"] if not dark else "#F9FAFB"}

def tiles_folium(nome_tema, dark=False):
    return TEMAS[nome_tema]["map_tiles_dark"] if dark else TEMAS[nome_tema]["map_tiles"]

def cores_status(nome_tema, dark=False):
    t = TEMAS[nome_tema]
    return {"Positivo": t["danger"], "Negativo": t["primary"], "Sem análise": t["text_muted"]}