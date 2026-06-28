"""
app.py — Dashboard FII Analyzer
=================================
3 abas: Simulação de Aporte | Carteira | Preço Teto

Scraping via Playwright (browser real) — bypassa Cloudflare/JS do Investidor10.

Execute com:  streamlit run app.py
"""

import math
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from scraper import (
    get_fii_data,
    get_multiplos_fiis,
    IPCA_MAIS_GLOBAL,
)
from utils import (
    fmt_brl, fmt_pct, fmt_pct_dec, fmt_num, fmt_cell, _is_valid,
    simular_aporte, resumo_simulacao,
    montar_carteira, totais_carteira,
    tabela_preco_teto,
    PREMIO_KNOWN, PREMIO_DEFAULT, get_grade_label,
)

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="FII Analyzer",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root {
    --bg:#0d1117; --surface:#161b22; --border:#30363d;
    --accent:#2563eb; --accent-l:#3b82f6;
    --green:#22c55e; --red:#ef4444; --yellow:#f59e0b;
    --text:#e6edf3; --muted:#8b949e;
}
.stApp { background:var(--bg); color:var(--text); }
.block-container { padding:1.5rem 2rem; max-width:1400px; }

.metric-card {
    background:var(--surface); border:1px solid var(--border);
    border-radius:8px; padding:1.1rem 1.2rem; text-align:center;
}
.metric-card .lbl {
    color:var(--muted); font-size:0.72rem; text-transform:uppercase;
    letter-spacing:.06em; margin-bottom:.3rem;
}
.metric-card .val { color:var(--text); font-size:1.45rem; font-weight:700; line-height:1.1; }
.metric-card .val.g { color:var(--green); }
.metric-card .val.r { color:var(--red); }
.metric-card .val.b { color:var(--accent-l); }
.metric-card .val.y { color:var(--yellow); }

.stTabs [data-baseweb="tab-list"] { gap:0; border-bottom:1px solid var(--border); background:transparent; }
.stTabs [data-baseweb="tab"] {
    background:transparent; color:var(--muted); border:none;
    border-bottom:2px solid transparent; padding:.75rem 1.5rem;
    font-size:.9rem; font-weight:500;
}
.stTabs [aria-selected="true"] { color:var(--accent-l) !important; border-bottom-color:var(--accent-l) !important; }
.stButton > button {
    background:var(--accent); color:white; border:none;
    border-radius:6px; font-weight:600; padding:.5rem 1.25rem;
}
.stButton > button:hover { background:var(--accent-l); }
.box-warn  { background:#1a1000; border:1px solid var(--yellow); border-radius:6px; padding:.7rem 1rem; color:var(--yellow); font-size:.84rem; margin:.4rem 0; }
.box-error { background:#1a0000; border:1px solid var(--red);    border-radius:6px; padding:.7rem 1rem; color:var(--red);    font-size:.84rem; margin:.4rem 0; }
.box-info  { background:#001a2a; border:1px solid var(--accent);  border-radius:6px; padding:.7rem 1rem; color:var(--accent-l);font-size:.84rem; margin:.4rem 0; }
.ph { border-bottom:1px solid var(--border); margin-bottom:1.5rem; padding-bottom:1rem; }
.ph h1 { font-size:1.6rem; font-weight:700; color:var(--text); margin:0; }
.ph p  { color:var(--muted); margin:.2rem 0 0; font-size:.9rem; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def mcard(label: str, value: str, color: str = "") -> None:
    st.markdown(
        f'<div class="metric-card"><div class="lbl">{label}</div>'
        f'<div class="val {color}">{value}</div></div>',
        unsafe_allow_html=True,
    )

def box(msg: str, kind: str = "warn") -> None:
    st.markdown(f'<div class="box-{kind}">{msg}</div>', unsafe_allow_html=True)

def plotly_layout(fig, title=""):
    fig.update_layout(
        title=title, template="plotly_dark",
        paper_bgcolor="#161b22", plot_bgcolor="#161b22",
        margin=dict(t=45, b=15, l=10, r=10),
        font=dict(color="#e6edf3"),
    )
    return fig

@st.cache_data(ttl=600, show_spinner=False)
def _buscar_um(ticker, premio_override_frozen, ipca_override_frozen):
    """Cache por ticker + configurações (600s = 10 min)."""
    return get_fii_data(
        ticker,
        premio_override=dict(premio_override_frozen),
        ipca_override=dict(ipca_override_frozen),
    )

def buscar_fii(ticker, premio_override=None, ipca_override=None):
    po = tuple(sorted((premio_override or {}).items()))
    io = tuple(sorted((ipca_override  or {}).items()))
    return _buscar_um(ticker, po, io)


# ── Cabeçalho ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ph">
  <h1>🏢 FII Analyzer</h1>
  <p>Dashboard de análise de FIIs · dados via Investidor10 (Playwright)</p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs([
    "📈  Simulação de Aporte",
    "📦  Carteira",
    "🎯  Preço Teto",
])


# ══════════════════════════════════════════════════════════════════════════════
# JANELA 1 — SIMULAÇÃO DE APORTE MENSAL
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Simulação de Aporte Mensal")
    st.caption(
        "Projeta patrimônio e renda com aportes fixos mensais em um único FII. "
        "**Premissa:** preço e DY constantes. Dividendos não reinvestidos."
    )

    # Inputs
    ca, cb, cc = st.columns([2, 1, 1])
    with ca: t1_ticker = st.text_input("Ticker", value="MXRF11", key="t1t").upper().strip()
    with cb: t1_cotas  = st.number_input("Cotas/mês", min_value=1, max_value=10000, value=10, step=1)
    with cc: t1_meses  = st.number_input("Meses", min_value=1, max_value=600, value=240, step=12)

    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        buscar1 = st.button("🔍 Buscar e Simular", key="btn1")

    if "t1_dados" not in st.session_state: st.session_state.t1_dados = None
    if "t1_manual" not in st.session_state: st.session_state.t1_manual = False

    if buscar1 and t1_ticker:
        with st.spinner(f"Abrindo navegador e coletando {t1_ticker}… (pode levar ~10s)"):
            st.session_state.t1_dados  = buscar_fii(t1_ticker)
            st.session_state.t1_manual = False

    d1 = st.session_state.t1_dados

    def _simular_e_exibir(preco, dy, cotas, meses):
        df_s = simular_aporte(preco, dy, int(cotas), int(meses))
        res  = resumo_simulacao(df_s)

        st.markdown("#### Resultado")
        r1,r2,r3,r4,r5 = st.columns(5)
        with r1: mcard("Cotas Totais",       fmt_num(res["cotas_total"], 0))
        with r2: mcard("Total Investido",    fmt_brl(res["total_investido"]))
        with r3: mcard("Renda Mensal Final", fmt_brl(res["renda_mensal_final"]), "g")
        with r4: mcard("Renda Acumulada",    fmt_brl(res["renda_acumulada"]),    "g")
        with r5: mcard("Patrimônio Final",   fmt_brl(res["patrimonio_final"]),   "b")

        st.divider()
        g1, g2 = st.columns(2)
        with g1:
            fig = px.area(df_s, x="Mês",
                          y=["Total Investido (R$)", "Renda Acumulada (R$)"],
                          color_discrete_map={"Total Investido (R$)":"#2563eb",
                                              "Renda Acumulada (R$)":"#22c55e"})
            st.plotly_chart(plotly_layout(fig, "Patrimônio vs Renda Acumulada"),
                            use_container_width=True)
        with g2:
            fig2 = px.line(df_s, x="Mês", y="Renda Mensal (R$)",
                           color_discrete_sequence=["#22c55e"])
            st.plotly_chart(plotly_layout(fig2, "Renda Mensal ao Longo do Tempo"),
                            use_container_width=True)

        with st.expander("📋 Tabela anual"):
            df_a = df_s[df_s["Mês"] % 12 == 0].copy()
            df_a["Ano"] = (df_a["Mês"] // 12).astype(str) + "º"
            st.dataframe(
                df_a[["Ano","Cotas Acumuladas","Total Investido (R$)",
                      "Renda Mensal (R$)","Renda Acumulada (R$)"]].set_index("Ano"),
                use_container_width=True,
            )

    if d1:
        if d1.get("erro"):
            box(f"⚠️ {d1['erro']}", "error")
            st.session_state.t1_manual = True
        elif not _is_valid(d1.get("preco")) or not _is_valid(d1.get("dy")):
            faltando = [f for f, v in [("Cotação", d1.get("preco")), ("DY", d1.get("dy"))]
                        if not _is_valid(v)]
            box(f"⚠️ <b>{t1_ticker}</b>: {', '.join(faltando)} não encontrados. "
                f"Use a entrada manual abaixo.", "warn")
            st.session_state.t1_manual = True
        else:
            # Sucesso — mostra dados do ativo
            ca2, cb2, cc2, cd2, ce2 = st.columns(5)
            with ca2: mcard("Ticker",      d1["ticker"])
            with cb2: mcard("Cotação",     fmt_brl(d1["preco"]), "b")
            with cc2: mcard("DY 12M",      fmt_pct(d1["dy"]) if _is_valid(d1.get("dy")) else "N/D", "g")
            with cd2: mcard("P/VP",        fmt_num(d1["pvp"])  if _is_valid(d1.get("pvp")) else "N/D")
            with ce2: mcard("Tipo",        d1.get("tipo","Indefinido").capitalize())
            st.divider()
            _simular_e_exibir(d1["preco"], d1["dy"], t1_cotas, t1_meses)

    # Fallback manual
    with st.expander("⚙️ Inserir dados manualmente",
                     expanded=st.session_state.get("t1_manual", False)):
        st.caption("Use quando o scraping não retornar valores ou para testar cenários.")
        ma, mb = st.columns(2)
        with ma: m_preco = st.number_input("Cotação (R$)", 0.01, value=10.00, step=0.01, key="t1mp")
        with mb: m_dy    = st.number_input("DY Anual (%)", 0.01, value=9.00, step=0.01, key="t1md")
        mc, md = st.columns(2)
        with mc: m_cotas = st.number_input("Cotas/mês", 1, value=int(t1_cotas), key="t1mc")
        with md: m_meses = st.number_input("Meses",     1, value=int(t1_meses), key="t1mm")
        if st.button("▶ Simular com dados manuais", key="btn1m"):
            _simular_e_exibir(m_preco, m_dy, m_cotas, m_meses)


# ══════════════════════════════════════════════════════════════════════════════
# JANELA 2 — CARTEIRA COM MÚLTIPLOS FIIs
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Montagem de Carteira")
    st.caption(
        "Adicione múltiplos FIIs e quantidades. "
        "Os dados são coletados em sequência num único browser."
    )

    n = st.number_input("Quantos FIIs?", min_value=1, max_value=20, value=3, step=1)

    st.markdown("---")
    inputs2 = []
    for i in range(int(n)):
        ca, cb = st.columns([2, 1])
        with ca:
            tk = st.text_input(f"Ticker #{i+1}", value="", key=f"ct_{i}",
                               placeholder="Ex: KNRI11").upper().strip()
        with cb:
            qt = st.number_input(f"Cotas #{i+1}", min_value=0, value=100, step=1, key=f"cq_{i}")
        if tk:
            inputs2.append({"ticker": tk, "quantidade": int(qt)})

    buscar2 = st.button("🔍 Montar Carteira", key="btn2")

    if buscar2 and inputs2:
        tickers2 = [x["ticker"] for x in inputs2]
        qtds2    = {x["ticker"]: x["quantidade"] for x in inputs2}

        prog2 = st.progress(0, text="Iniciando coleta…")

        def cb2(ticker, idx, total):
            prog2.progress(idx / total, text=f"Coletado {ticker} ({idx}/{total})")

        with st.spinner("Abrindo navegador… pode levar alguns segundos por FII."):
            resultados2 = get_multiplos_fiis(
                tickers2,
                progress_callback=cb2,
            )
        prog2.progress(1.0, text="Concluído!")
        prog2.empty()

        # Injeta quantidade e exibe avisos
        fiis2 = []
        for d in resultados2:
            d["quantidade"] = qtds2.get(d["ticker"], 0)
            if d.get("erro"):
                box(f"⚠️ <b>{d['ticker']}</b>: {d['erro']}", "error")
            else:
                missing = [f for f, v in [("Preço", d.get("preco")), ("DY", d.get("dy"))]
                           if not _is_valid(v)]
                if missing:
                    box(f"⚠️ <b>{d['ticker']}</b>: {', '.join(missing)} não encontrados — "
                        f"linha exibirá N/D.", "warn")
            fiis2.append(d)

        if fiis2:
            df2  = montar_carteira(fiis2)
            tot2 = totais_carteira(df2)

            st.divider()
            tc1, tc2, tc3 = st.columns(3)
            with tc1: mcard("Investimento Total",  fmt_brl(tot2["total_investido"]),    "b")
            with tc2: mcard("Renda Mensal Total",  fmt_brl(tot2["total_renda_mensal"]), "g")
            with tc3: mcard("DY Médio Ponderado",  fmt_pct(tot2["dy_medio_ponderado"]) if _is_valid(tot2.get("dy_medio_ponderado")) else "N/D", "g")

            st.divider()
            st.markdown("#### Composição da Carteira")

            # Formata para exibição
            df2_show = df2.copy()
            df2_show["Preço (R$)"]          = df2_show["Preço (R$)"].apply(lambda x: fmt_cell(x, "R$ "))
            df2_show["Investimento (R$)"]   = df2_show["Investimento (R$)"].apply(lambda x: fmt_cell(x, "R$ "))
            df2_show["Proventos/cota (R$)"] = df2_show["Proventos/cota (R$)"].apply(lambda x: fmt_cell(x, "R$ ", 4))
            df2_show["Renda Mensal (R$)"]   = df2_show["Renda Mensal (R$)"].apply(lambda x: fmt_cell(x, "R$ "))
            df2_show["DY (%)"]              = df2_show["DY (%)"].apply(
                lambda x: f"{x:.2f}%".replace(".", ",") if _is_valid(x) else "N/D"
            )
            df2_show["P/VP"] = df2_show["P/VP"].apply(
                lambda x: fmt_num(x) if _is_valid(x) else "N/D"
            )
            st.dataframe(df2_show, use_container_width=True, hide_index=True)

            # Gráficos
            df2_num = df2.dropna(subset=["Investimento (R$)", "Renda Mensal (R$)"])
            if not df2_num.empty:
                st.divider()
                g1, g2 = st.columns(2)
                with g1:
                    fig_i = px.pie(df2_num, names="FII", values="Investimento (R$)",
                                   color_discrete_sequence=px.colors.sequential.Blues_r)
                    st.plotly_chart(plotly_layout(fig_i, "Composição por Investimento"),
                                    use_container_width=True)
                with g2:
                    fig_r = px.pie(df2_num, names="FII", values="Renda Mensal (R$)",
                                   color_discrete_sequence=px.colors.sequential.Greens_r)
                    st.plotly_chart(plotly_layout(fig_r, "Composição por Renda Mensal"),
                                    use_container_width=True)

            df2_dy = df2.dropna(subset=["DY (%)"])
            if not df2_dy.empty:
                fig_dy = px.bar(df2_dy.sort_values("DY (%)", ascending=False),
                                x="FII", y="DY (%)", color="DY (%)",
                                color_continuous_scale="Blues", text_auto=".2f")
                st.plotly_chart(plotly_layout(fig_dy, "Dividend Yield por FII (%)"),
                                use_container_width=True)

    # Entrada manual
    with st.expander("⚙️ Adicionar ativo manualmente"):
        ma2, mb2 = st.columns(2)
        with ma2: m2_tk  = st.text_input("Ticker", key="m2tk").upper().strip()
        with mb2: m2_qt  = st.number_input("Cotas", min_value=0, value=100, key="m2qt")
        mc2, md2, me2, mf2 = st.columns(4)
        with mc2: m2_p  = st.number_input("Cotação (R$)",     0.01,  value=10.00, step=0.01,  key="m2p")
        with md2: m2_dy = st.number_input("DY (%)",           0.01,  value=9.00,  step=0.01,  key="m2dy")
        with me2: m2_d  = st.number_input("Dividendo 12M (R$)", 0.01, value=0.90,  step=0.01, key="m2d")
        with mf2: m2_ti = st.selectbox("Tipo", ["papel","tijolo","Indefinido"], key="m2ti")
        if st.button("➕ Calcular", key="btn2m"):
            fii_m = [{"ticker": m2_tk or "MANUAL", "preco": m2_p, "dy": m2_dy,
                      "dividendo_12m": m2_d, "pvp": None, "tipo": m2_ti,
                      "quantidade": int(m2_qt)}]
            df_m = montar_carteira(fii_m)
            tot_m = totais_carteira(df_m)
            xm1, xm2, xm3 = st.columns(3)
            with xm1: mcard("Investimento", fmt_brl(tot_m["total_investido"]),   "b")
            with xm2: mcard("Renda Mensal", fmt_brl(tot_m["total_renda_mensal"]),"g")
            with xm3: mcard("DY Anual",     fmt_pct(tot_m["dy_medio_ponderado"]) if _is_valid(tot_m.get("dy_medio_ponderado")) else "N/D", "g")


# ══════════════════════════════════════════════════════════════════════════════
# JANELA 3 — PREÇO TETO
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Cálculo de Preço Teto")
    st.caption(
        "Baseado na metodologia do **fiis.py**: "
        "**Preço Teto = Dividendo 12M (R$) ÷ (IPCA+ + Prêmio)**"
    )

    with st.expander("📐 Metodologia completa"):
        st.markdown(f"""
**Fórmulas (fiel ao fiis.py):**
```
DIVIDENDO 12M (R$) = PREÇO × DY 12M%
TAXA REQUERIDA     = IPCA+ ({IPCA_MAIS_GLOBAL*100:.0f}%) + PRÊMIO
PREÇO TETO         = DIVIDENDO 12M (R$) / TAXA REQUERIDA
MARGEM DE SEG.     = (PREÇO TETO - PREÇO) / PREÇO × 100
```

**IPCA por tipo de fundo** (informativo — não entra na taxa):

| % FII na carteira | IPCA |
|---|---|
| 0% – 25%  | 0,0% — tijolo puro |
| 25% – 40% | 1,5% |
| 40% – 60% | 2,5% |
| 60% – 75% | 3,5% |
| 75% – 100%| 5,0% — papel puro |

**Prêmio de risco padrão:**

| Grade | Prêmio | Exemplos |
|---|---|---|
| High Grade  | 1% | KNRI11, HGLG11, XPML11, BTLG11 |
| Middle Grade| 3% | GARE11, BTCI11, TRXF11, KNCR11 |
| High Yield  | 5% | MXRF11, RECR11, VGHF11, PORD11 |
        """)

    # Tickers
    tickers_raw3 = st.text_input(
        "Tickers (separados por vírgula)",
        value="MXRF11, KNRI11, XPML11, BTLG11, HGLG11",
        key="t3raw"
    )
    tickers3 = [t.strip().upper() for t in tickers_raw3.split(",") if t.strip()]

    # Configurações por ticker
    if tickers3:
        st.markdown("##### Configurações de Prêmio e IPCA por ativo:")
        st.caption(
            "Prêmio pré-preenchido pelos valores do fiis.py. "
            "Ajuste conforme sua análise. IPCA é detectado automaticamente pelo tipo do fundo."
        )

        configs3 = {}
        # Grid de até 4 colunas
        num_cols = min(len(tickers3), 4)
        cols3 = st.columns(num_cols)

        for i, tk in enumerate(tickers3):
            default_prem = PREMIO_KNOWN.get(tk, PREMIO_DEFAULT)
            default_label = {0.01: "High Grade (1%)", 0.03: "Middle Grade (3%)", 0.05: "High Yield (5%)"}.get(
                default_prem, "High Grade (1%)"
            )
            with cols3[i % num_cols]:
                st.markdown(f"**{tk}**")
                prem_sel = st.selectbox(
                    "Prêmio",
                    options=["High Grade (1%)", "Middle Grade (3%)", "High Yield (5%)"],
                    index=["High Grade (1%)", "Middle Grade (3%)", "High Yield (5%)"].index(default_label),
                    key=f"p3_{tk}",
                )
                ipca_sel = st.selectbox(
                    "IPCA (override)",
                    options=["Auto (pelo tipo)", "0% Tijolo", "1,5%", "2,5%", "3,5%", "5% Papel"],
                    key=f"i3_{tk}",
                )
                configs3[tk] = {
                    "premio": {"High Grade (1%)": 0.01, "Middle Grade (3%)": 0.03, "High Yield (5%)": 0.05}[prem_sel],
                    "ipca_override": {
                        "Auto (pelo tipo)": None, "0% Tijolo": 0.00,
                        "1,5%": 0.015, "2,5%": 0.025, "3,5%": 0.035, "5% Papel": 0.05,
                    }[ipca_sel],
                }

    buscar3 = st.button("🔍 Calcular Preço Teto", key="btn3")

    if buscar3 and tickers3:
        premio_ov3 = {"default": 0.01}
        ipca_ov3   = {}
        for tk, cfg in configs3.items():
            premio_ov3[tk] = cfg["premio"]
            if cfg["ipca_override"] is not None:
                ipca_ov3[tk] = cfg["ipca_override"]

        prog3 = st.progress(0, text="Iniciando…")

        def cb3(ticker, idx, total):
            prog3.progress(idx / total, text=f"Coletado {ticker} ({idx}/{total})")

        with st.spinner("Coletando via Playwright… aguarde."):
            resultados3 = get_multiplos_fiis(
                tickers3,
                premio_override=premio_ov3,
                ipca_override=ipca_ov3,
                progress_callback=cb3,
            )
        prog3.progress(1.0, text="Concluído!")
        prog3.empty()

        erros3 = [d for d in resultados3 if d.get("erro")]
        validos3 = [d for d in resultados3 if not d.get("erro")]

        for d in erros3:
            box(f"⚠️ <b>{d['ticker']}</b>: {d['erro']}", "error")

        if validos3:
            df3 = tabela_preco_teto(validos3)

            st.divider()
            st.markdown("#### Tabela de Preço Teto")

            # Estilização condicional (pandas >= 2.1 usa .map)
            def _cor_margem(v):
                if v is None or (isinstance(v, float) and math.isnan(v)): return "color:#8b949e"
                return "color:#22c55e;font-weight:700" if v >= 0 else "color:#ef4444;font-weight:700"

            def _cor_pvp(v):
                if v is None or (isinstance(v, float) and math.isnan(v)): return ""
                if v < 1.0:  return "color:#22c55e"
                if v <= 1.1: return "color:#f59e0b"
                return "color:#ef4444"

            def _f(x, prefix="", dec=2, suffix=""):
                if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))): return "N/D"
                s = f"{x:,.{dec}f}".replace(",","X").replace(".",",").replace("X",".")
                return f"{prefix}{s}{suffix}"

            styled3 = (
                df3.style
                .map(_cor_margem, subset=["Margem Seg. (%)"])
                .map(_cor_pvp,    subset=["P/VP"])
                .format({
                    "P/VP":               lambda x: _f(x, dec=2),
                    "Preço (R$)":          lambda x: _f(x, "R$ "),
                    "DY 12M (%)":          lambda x: _f(x, dec=2, suffix="%"),
                    "Dividendo 12M (R$)":  lambda x: _f(x, "R$ ", 4),
                    "IPCA":                lambda x: _f(x*100 if _is_valid(x) else x, dec=1, suffix="%"),
                    "IPCA+":               lambda x: _f(x*100 if _is_valid(x) else x, dec=0, suffix="%"),
                    "Prêmio":              lambda x: _f(x*100 if _is_valid(x) else x, dec=0, suffix="%"),
                    "Taxa Req.":            lambda x: _f(x*100 if _is_valid(x) else x, dec=0, suffix="%"),
                    "Preço Teto (R$)":     lambda x: _f(x, "R$ "),
                    "Margem Seg. (%)":     lambda x: (
                        "N/D" if not _is_valid(x)
                        else f"{x:+.2f}%".replace(".", ",")
                    ),
                })
            )
            st.dataframe(styled3, use_container_width=True, hide_index=True)

            # ── Gráfico: Preço Atual vs Preço Teto ───────────────────────────
            df3_plot = df3.dropna(subset=["Preço (R$)", "Preço Teto (R$)"])
            if not df3_plot.empty:
                st.divider()
                fig_bar3 = go.Figure()
                fig_bar3.add_trace(go.Bar(
                    name="Preço Atual", x=df3_plot["FII"], y=df3_plot["Preço (R$)"],
                    marker_color="#2563eb",
                    text=df3_plot["Preço (R$)"].apply(lambda x: f"R$ {x:.2f}" if _is_valid(x) else ""),
                    textposition="outside",
                ))
                fig_bar3.add_trace(go.Bar(
                    name="Preço Teto", x=df3_plot["FII"], y=df3_plot["Preço Teto (R$)"],
                    marker_color="#22c55e",
                    text=df3_plot["Preço Teto (R$)"].apply(lambda x: f"R$ {x:.2f}" if _is_valid(x) else ""),
                    textposition="outside",
                ))
                fig_bar3.update_layout(barmode="group", legend=dict(orientation="h", y=-0.15))
                st.plotly_chart(plotly_layout(fig_bar3, "Preço Atual vs Preço Teto"),
                                use_container_width=True)

            # ── Gráfico de margens ────────────────────────────────────────────
            df3_mg = df3.dropna(subset=["Margem Seg. (%)"])
            if not df3_mg.empty:
                cores_mg = ["#22c55e" if v >= 0 else "#ef4444" for v in df3_mg["Margem Seg. (%)"]]
                fig_mg3 = go.Figure(go.Bar(
                    x=df3_mg["FII"], y=df3_mg["Margem Seg. (%)"],
                    marker_color=cores_mg,
                    text=df3_mg["Margem Seg. (%)"].apply(lambda x: f"{x:+.1f}%"),
                    textposition="outside",
                ))
                fig_mg3.add_hline(y=0, line_dash="dash", line_color="#8b949e")
                fig_mg3.update_layout(yaxis_ticksuffix="%")
                st.plotly_chart(plotly_layout(fig_mg3, "Margem de Segurança (%)"),
                                use_container_width=True)

            # ── Gráfico de IPCA por fundo ─────────────────────────────────────
            df3_ipca = df3.dropna(subset=["IPCA"])
            if not df3_ipca.empty:
                fig_ipca = px.bar(
                    df3_ipca, x="FII",
                    y=df3_ipca["IPCA"] * 100,
                    color="Tipo",
                    color_discrete_map={"papel":"#f59e0b","tijolo":"#2563eb","Indefinido":"#8b949e"},
                    text_auto=".1f",
                    labels={"y": "IPCA (%)"},
                )
                st.plotly_chart(plotly_layout(fig_ipca, "IPCA Estimado por Fundo (%)"),
                                use_container_width=True)

    # Entrada manual preço teto
    with st.expander("⚙️ Calcular preço teto manualmente"):
        pm1, pm2, pm3, pm4 = st.columns(4)
        with pm1: m3_tk  = st.text_input("Ticker", "TICKER",  key="m3tk")
        with pm2: m3_p   = st.number_input("Preço (R$)",       0.01, value=10.00, step=0.01, key="m3p")
        with pm3: m3_d   = st.number_input("Dividendo 12M (R$)", 0.001, value=0.90, step=0.01, key="m3d")
        with pm4: m3_dy  = st.number_input("DY (%)",           0.01, value=9.00, step=0.01, key="m3dy")
        pm5, pm6, pm7 = st.columns(3)
        with pm5: m3_ti  = st.selectbox("Tipo", ["papel","tijolo","Indefinido"], key="m3ti")
        with pm6: m3_pct = st.slider("% FII na carteira", 0, 100, 80, key="m3pct")
        with pm7: m3_gr  = st.selectbox("Grade de risco",
                                        ["High Grade (1%)", "Middle Grade (3%)", "High Yield (5%)"], key="m3gr")

        if st.button("🧮 Calcular", key="btn3m"):
            from scraper import ipca_por_percentual_fii
            prem_m = {"High Grade (1%)": 0.01, "Middle Grade (3%)": 0.03, "High Yield (5%)": 0.05}[m3_gr]
            ipca_m = 0.00 if "tijolo" in m3_ti else ipca_por_percentual_fii(m3_pct / 100)

            fii_m3 = [{
                "ticker": m3_tk.upper(), "preco": m3_p, "dy": m3_dy,
                "dividendo_12m": m3_d, "pvp": None, "tipo": m3_ti,
                "ipca": ipca_m, "ipca_mais": IPCA_MAIS_GLOBAL, "premio": prem_m,
            }]
            df_m3 = tabela_preco_teto(fii_m3)
            row   = df_m3.iloc[0]

            xm1, xm2, xm3, xm4, xm5 = st.columns(5)
            with xm1: mcard("IPCA Estimado", fmt_pct(ipca_m * 100, 1))
            with xm2: mcard("Taxa Req.",     fmt_pct((IPCA_MAIS_GLOBAL + prem_m) * 100, 0))
            with xm3: mcard("Preço Teto",    fmt_brl(row["Preço Teto (R$)"]))
            mg = row["Margem Seg. (%)"]
            cg = "g" if _is_valid(mg) and mg >= 0 else "r"
            with xm4: mcard("Margem Seg.",   fmt_pct(mg) if _is_valid(mg) else "N/D", cg)
            with xm5: mcard("Grade",         m3_gr.split(" ")[0] + " " + m3_gr.split(" ")[1])

# ── Rodapé ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<p style='text-align:center;color:#8b949e;font-size:.78rem;'>"
    "Dados via Investidor10 (Playwright) · Uso educacional · "
    "Não constitui recomendação de investimento"
    "</p>",
    unsafe_allow_html=True,
)
