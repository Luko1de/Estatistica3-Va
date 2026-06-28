# 🏢 FII Analyzer — Dashboard Python de Análise de FIIs

Dashboard interativo em Streamlit para análise de FIIs, com dados coletados
via **Playwright (browser real)** do [Investidor10](https://investidor10.com.br).
Lógica de cálculo integrada do `fiis.py` (scraping + prêmio por grade + IPCA por tipo).

---

## 📁 Estrutura do Projeto

```
fii_dashboard/
├── app.py            # Dashboard Streamlit (3 abas)
├── scraper.py        # Scraping via Playwright + classificação IPCA
├── utils.py          # Cálculos financeiros, formatação, prêmios
├── requirements.txt  # Dependências
└── README.md
```

---

## ⚙️ Instalação

```bash
# 1. Ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows

# 2. Dependências Python
pip install -r requirements.txt

# 3. Navegador Chromium (passo obrigatório — só precisa rodar uma vez)
playwright install chromium

# 4. Rodar o dashboard
streamlit run app.py
```

---

## 🔍 Por que Playwright?

O Investidor10 usa **React + Cloudflare**. Os cards de indicadores (cotação, DY,
P/VP) são renderizados via JavaScript *após* o carregamento da página.
`requests + BeautifulSoup` só enxerga o HTML estático — sem esses dados.

O Playwright abre um Chromium real (headless), espera o JavaScript executar
completamente e só então extrai o texto. É a mesma abordagem do `fiis.py` original.

---

## 📐 Lógica de Cálculo (fiel ao fiis.py)

### Preço Teto

```
DIVIDENDO 12M (R$) = PREÇO × DY 12M%
TAXA REQUERIDA     = IPCA+ (7%) + PRÊMIO
PREÇO TETO         = DIVIDENDO 12M (R$) / TAXA REQUERIDA
MARGEM DE SEG.     = (PREÇO TETO - PREÇO) / PREÇO × 100
```

> **Nota:** O IPCA do fundo (papel/tijolo) é informativo — representa a
> proteção inflacionária do ativo — mas não entra diretamente na taxa requerida,
> seguindo o fiis.py original.

### IPCA por % de FII na carteira do fundo

| % FII  | IPCA  |
|--------|-------|
| 0–25%  | 0,0%  |
| 25–40% | 1,5%  |
| 40–60% | 2,5%  |
| 60–75% | 3,5%  |
| 75–100%| 5,0%  |

### Prêmio de Risco

| Grade        | Prêmio | Tickers pré-configurados              |
|--------------|--------|---------------------------------------|
| High Grade   | 1%     | KNRI11, HGLG11, XPML11, BTLG11, LVBI11, HSLG11 |
| Middle Grade | 3%     | GARE11, GGRC11, BTCI11, TRXF11, RBVA11, KNCR11, SNAG11 |
| High Yield   | 5%     | MXRF11, RECR11, VGHF11, PORD11       |

Tickers não listados recebem High Grade (1%) por padrão. Tudo ajustável na interface.

### Simulação de Aporte (Aba 1)

```
Dividendo mensal/cota = Preço × (DY_anual% / 100 / 12)
Renda mensal          = Cotas_acumuladas × Dividendo_mensal/cota
```

Premissas: preço e DY constantes, dividendos não reinvestidos.

### Carteira (Aba 2)

```
Investimento    = Preço × Quantidade
Proventos/cota  = Dividendo_12M (R$) / 12
Renda Mensal    = Proventos/cota × Quantidade
DY médio pond.  = (Renda_total × 12 / Investimento_total) × 100
```

---

## ⚠️ Aviso Legal

Uso exclusivamente educacional. Não constitui recomendação de investimento.
