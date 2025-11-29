import streamlit as st
import pandas as pd
import requests
import numpy as np
import holidays
from datetime import datetime

# ==========================================
# 1. BACKEND
# ==========================================
@st.cache_data(ttl=3600) 
def get_cdi_data(data_inicio):
    # Data final sempre 'hoje' para garantir dados recentes
    data_fim = datetime.now().strftime('%d/%m/%Y')
    url = f'http://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json&dataInicial={data_inicio}&dataFinal={data_fim}'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=10)
        df = pd.DataFrame(r.json())
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        df['valor'] = pd.to_numeric(df['valor'])
        df = df[df['data'] < pd.to_datetime('today')]
        return df
    except Exception as e:
        st.error(f"Erro ao baixar CDI: {e}")
        return pd.DataFrame()

def calcular_tudo(vne, dt_emissao, tx_emissao, dt_compra, tx_compra, dt_vencimento):
    dt_emissao_str = dt_emissao.strftime('%d/%m/%Y')
    df = get_cdi_data(dt_emissao_str)
    
    if df.empty: return None

    # --- 1. CÁLCULO DO PASSADO (VNA / CURVA) ---
    # Filtra CDI da Emissão até a Data de Compra/Cálculo
    df_periodo = df[(df['data'] >= pd.to_datetime(dt_emissao)) & 
                    (df['data'] < pd.to_datetime(dt_compra))].copy()
    
    # Fator CDI Acumulado
    df_periodo['fator_cdi'] = 1 + (df_periodo['valor'] / 100)
    
    # Fator Spread Diário (Emissão)
    fator_spread_dia = (1 + tx_emissao / 100) ** (1/252)
    
    # Fator Combinado (Regra B3: Arredondar 8 casas dia a dia)
    df_periodo['fator_dia'] = (df_periodo['fator_cdi'] * fator_spread_dia).round(8)
    
    fator_acumulado = 1.0
    for f in df_periodo['fator_dia']:
        fator_acumulado = round(fator_acumulado * f, 8)
        
    vna_calculado = round(vne * fator_acumulado, 6)
    
    # ===============================
    # CÁLCULOs 
    # ===============================
    
    # Lista de Feriados
    anos_envolvidos = range(dt_compra.year, dt_vencimento.year)
    feriados_br = list(holidays.Brazil(years=anos_envolvidos).keys())
    
    dias_uteis_restantes = np.busday_count(
        np.datetime64(dt_compra), 
        np.datetime64(dt_vencimento),
        weekmask='1111100', 
        holidays=feriados_br
    )
    
    # DURATION
    # como é Bullet, Duration = Prazo Restante
    
    duration_anos = dias_uteis_restantes / 252
    
    # Ajuste de Mercado (Deságio/Ágio)
    tx_emissao_fator = (1 + tx_emissao/100)
    tx_mercado_fator = (1 + tx_compra/100)
    
    # Fator de Desconto a Valor Presente
    fator_mtm = (tx_emissao_fator / tx_mercado_fator) ** duration_anos
    
    pu_mercado = vna_calculado * fator_mtm
    
    # DV01 
    # Sensibilidade: Preço * Duration Modificada * 0.0001
    
    duration_modificada = duration_anos / (1 + tx_compra/100)
    dv01 = pu_mercado * duration_modificada * 0.0001
    
    return {
        "Financeiro (PU Mercado)": pu_mercado,
        "VNA (Curva)": vna_calculado,
        "Duration": duration_anos,
        "Dias Úteis": int(dias_uteis_restantes),
        "DV01": dv01,
        "Taxa Emissão": tx_emissao,
        "Taxa Mercado": tx_compra
    }

# ==========================================
# FUNÇÃO UTILITÁRIA DE FORMATAÇÃO (PT-BR)
# ==========================================
def formata_br(valor, prefixo='', casas=2):
    """Transforma 1234.56 em 1.234,56"""
    if valor is None: return "-"
    formato = f"{{:,.{casas}f}}"
    texto = formato.format(valor)
    texto = texto.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"{prefixo} {texto}".strip()

# ==========================================
# 2. FRONTEND (Visual e Interação)
# ==========================================

def formata_br(valor, prefixo='', casas=2):
    """Auxiliar: Transforma 1234.56 em 1.234,56"""
    if valor is None: return "-"
    formato = f"{{:,.{casas}f}}"
    texto = formato.format(valor)
    texto = texto.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"{prefixo} {texto}".strip()

st.set_page_config(page_title="Calculadora Renda Fixa", layout="wide", page_icon="📈")

# Cabeçalho
st.header("Calculadora - Renda Fixa")
st.caption("Cálculo de PU e Risco para títulos indexados ao CDI+")

# --- SEÇÃO 1: DADOS DO PAPEL (CADASTRO) ---
with st.expander("Dados do Título - Emissão)", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        vne = st.number_input("VNE / PU Emissão", value=50000.00, step=1000.00, format="%.2f")
    with c2:
        dt_emissao = st.date_input("Data Emissão", value=pd.to_datetime("2024-01-24"), format="DD/MM/YYYY")
    with c3:
        tx_emissao = st.number_input("Spread Emissão (CDI +)", value=1.00, step=0.1, format="%.2f")
    with c4:
        dt_vencimento = st.date_input("Vencimento", value=pd.to_datetime("2030-01-28"), format="DD/MM/YYYY")

# --- SEÇÃO 2: BOLETA DE CÁLCULO ---
st.markdown("### Parâmetros da Operação")

with st.container():
    col_neg1, col_neg2, col_neg3, col_neg4 = st.columns([1.5, 1.5, 1.5, 1.5])
    
    with col_neg1:
        dt_calculo = st.date_input("Data Base (Cálculo)", value=pd.to_datetime("2025-11-27"), format="DD/MM/YYYY")
    
    with col_neg2:
        qtd = st.number_input("Quantidade", value=1, min_value=1, step=1)
    
    with col_neg3:
        tx_compra = st.number_input("Taxa de Mercado (Spread %)", value=1.50, step=0.01, format="%.2f")
    
    with col_neg4:
        st.write("") # Espaçamento
        st.write("") 
        calcular_btn = st.button("CALCULAR PREÇO", type="primary", use_container_width=True)

st.markdown("---")

# --- RESULTADOS ---
if calcular_btn:
    # 1. Validações
    if dt_vencimento <= dt_calculo:
        st.error("Erro: Vencimento deve ser posterior à data de cálculo.")
    elif dt_calculo < dt_emissao:
        st.error("Erro: Data de cálculo anterior à emissão.")
    else:
        # 2. Execução
        with st.spinner('Consultando Curvas e Calculando...'):
            res = calcular_tudo(vne, dt_emissao, tx_emissao, dt_calculo, tx_compra, dt_vencimento)
        
        # 3. Exibição
        if res:
            pu_unitario = res['Financeiro (PU Mercado)']
            financeiro_total = pu_unitario * qtd
            
            # --- CARD PRINCIPAL ---
            st.subheader("Resultado da Precificação")
            
            kpi1, kpi2, kpi3 = st.columns([1, 1, 2])
            
            with kpi1:
                st.markdown("**PU Unitário (Calculado)**")
                st.markdown(f"### {formata_br(pu_unitario, 'R$')}")
            
            with kpi2:
                st.markdown("**Taxa Aplicada**")
                st.markdown(f"### {formata_br(tx_compra, '', 2)}%")
            
            with kpi3:
                st.info(f"**Financeiro Total ({qtd} qtd):** \n# {formata_br(financeiro_total, 'R$')}")

            st.markdown("") 

            # --- DETALHES TÉCNICOS ---
            st.markdown("#### Detalhes de Risco e Curva")
            
            d1, d2, d3, d4 = st.columns(4)
            
            with d1:
                st.metric("VNA (Curva)", formata_br(res['VNA (Curva)'], "R$"))
                st.caption("Saldo devedor contábil")
                
            with d2:
                st.metric("Duration", f"{formata_br(res['Duration'], casas=2)} anos")
                st.caption("Prazo médio ponderado")

            with d3:
                st.metric("DV01 (Unitário)", formata_br(res['DV01'], "R$", 4))
                st.caption("Risco p/ 1 bp (0.01%)")

            with d4:
                st.metric("Dias Úteis", res['Dias Úteis'])
                st.caption(f"Até {dt_vencimento.strftime('%d/%m/%Y')}")

        # 4. TRATAMENTO DE ERRO (ELSE)
        else:
            st.error("Não foi possível realizar o cálculo.")
            st.markdown("""
            **Verifique:**
            1. Conexão com a internet (API do BC).
            2. Se a Data de Emissão cai em dia útil.
            3. Tente novamente em alguns segundos.
            """)