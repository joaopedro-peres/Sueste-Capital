# Calculadora de Precificação de Renda Fixa (CDI+)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red)

Ferramenta desenvolvida em Python para precificação de ativos de RF indexados ao CDI(CDI+) no mercado secundário, como parte da entrega à Suste Capital

Realiza o cálculo do **PU de Curva (VNA)** seguindo a metodologia da B3 e compara com o **PU de Mercado (MtM)**, gerando métricas de risco como **Duration** e **DV01**.

## Funcionalidades

- **Conexão com BACEN:** Busca a série histórica do CDI (Série 12) diretamente da API do Banco Central.
- **Metodologia B3:** Aplicação das regras de arredondamento (8 casas decimais) para fator acumulado.
- **Feriados Bancários:** Utiliza a biblioteca `holidays` para contagem exata de dias úteis (DU/252).
- **Métricas:** VNA, MtM, Duration (Spread), DV01
