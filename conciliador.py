import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# 1. Configuração inicial
st.set_page_config(page_title="Auditor Contábil Pro", layout="wide", page_icon="⚖️")

# --- DICIONÁRIO DE SINÔNIMOS ---
S_DATA = ['DATA DA TRANSAÇÃO', 'DATA DA VENDA', 'DATA', 'DT. VENDA', 'DATA DE CREDITAÇÃO (DATE_APPROVED)']
S_BRUTO = ['VALOR PARCELA BRUTO', 'VALOR BRUTO DA PARCELA', 'VL TRANSAÇÃO', 'VALOR BRUTO R$', 'VALOR DO PRODUTO (TRANSACTION_AMOUNT)', 'VALOR', 'VLR BRUTO']
S_TAXA = ['VALOR TOTAL DAS TAXAS DESCONTADAS (MDR+RECEBIMENTO AUTOMÁTICO)', 'VALOR TAXA', 'TAXA/TARIFA', 'CUSTO DA TRANSAÇÃO']
S_STATUS = ['STATUS DA VENDA', 'STATUS', 'SITUAÇÃO']

# Palavras-chave para identificar Vouchers e excluir de máquinas de terceiros
VOUCHER_KEYS = ['TICKET', 'ALELO', 'SODEXO', 'PLUXEE', 'VOUCHER', 'ALIMENTACAO', 'REFEICAO', 'CABAL', 'VR']

def limpar_valor(valor, eh_despesa=False):
    if pd.isna(valor): return 0.0
    s = str(valor).upper().replace('R$', '').replace(' ', '').replace('\xa0', '').strip()
    if '.' in s and ',' in s: s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    try:
        num = float(re.sub(r'[^-0-9.]', '', s))
        return abs(num) if eh_despesa else num
    except: return 0.0

def localizar_coluna(df, sinonimos):
    cols_reais = {str(c).strip().upper(): c for c in df.columns}
    for s in sinonimos:
        if s in cols_reais: return cols_reais[s]
    return None

def carregar_dados_inteligente(file):
    try:
        ext = file.name.split('.')[-1].lower()
        if ext == 'csv':
            try: df = pd.read_csv(file, sep=';', encoding='latin-1', low_memory=False)
            except: df = pd.read_csv(file, sep=',', encoding='utf-8', low_memory=False)
        else:
            df = pd.read_excel(file, engine='pyxlsb', header=None) if ext == 'xlsb' else pd.read_excel(file, header=None)
            for i in range(len(df)):
                if i > 60: break
                vals = [str(v).strip().upper() for v in df.iloc[i].values if pd.notna(v)]
                # Adicionado "VALOR TOTAL" para identificar VR e Ticket que possuem cabeçalhos longos
                if any(x in ' '.join(vals) for x in ['DATA', 'VALOR', 'BRUTO', 'PAGAMENTO *']):
                    df.columns = df.iloc[i]; df = df.iloc[i+1:].reset_index(drop=True); break
        df = df.loc[:, df.columns.notna()]
        # REMOVE LINHAS DE TOTAIS (Crítico para VR e Ticket)
        return df[~df.iloc[:, 0].astype(str).str.contains('TOTAL|EMISSÃO|EMPRESA', case=False, na=False)].dropna(how='all')
    except: return None

st.title("⚖️ Auditoria Contábil Pro")

with st.sidebar:
    st.header("⚙️ Configurações")
    ignorar_vouchers = st.checkbox("Excluir Vouchers de Máquinas de Terceiros", value=True)
    st.divider()
    f_raz = st.file_uploader("📘 1. Livro Razão", type=['xlsx', 'xls', 'xlsb', 'csv'])
    f_carts = st.file_uploader("💳 2. Máquinas (Cielo, Rede, VR, Ticket, etc)", type=['xlsx', 'xls', 'xlsb', 'csv'], accept_multiple_files=True)

if f_raz:
    df_raz_raw = carregar_dados_inteligente(f_raz)
    c_dt_r, c_val_r = localizar_coluna(df_raz_raw, ['DATA']), localizar_coluna(df_raz_raw, ['DÉBITO', 'DEBITO', 'VALOR'])
    
    if c_dt_r and c_val_r:
        df_raz_raw['DT'] = pd.to_datetime(df_raz_raw[c_dt_r], errors='coerce').dt.date
        df_raz_raw['VAL'] = df_raz_raw[c_val_r].apply(limpar_valor)
        df_raz = df_raz_raw.groupby('DT')['VAL'].sum().reset_index().rename(columns={'DT': 'DATA', 'VAL': 'RAZAO_BRUTO'})

        v_cons, l_desp = [], []
        
        for f in (f_carts if f_carts else []):
            df_t = carregar_dados_inteligente(f)
            if df_t is not None:
                nome_arq = f.name.upper()
                
                # --- LÓGICA VR REEMBOLSO (Cálculo de Despesa pelo Recebimento) ---
                if "REEMBOLSO" in nome_arq and "VR" in nome_arq:
                    c_pg = localizar_coluna(df_t, ['PAGAMENTO *'])
                    c_vb = localizar_coluna(df_t, ['VALOR BRUTO'])
                    c_vl = localizar_coluna(df_t, ['VALOR LÍQUIDO'])
                    if c_pg and c_vb and c_vl:
                        df_t['DT_PG'] = pd.to_datetime(df_t[c_pg], errors='coerce').dt.date
                        df_t['TAXA'] = df_t[c_vb].apply(limpar_valor) - df_t[c_vl].apply(limpar_valor)
                        for _, row in df_t.groupby('DT_PG')['TAXA'].sum().reset_index().iterrows():
                            if row['TAXA'] > 0: l_desp.append({'data': row['DT_PG'], 'valor': row['TAXA'], 'origem': 'VR BENEFICIOS', 'compl': '(Taxa Reembolso)'})
                    continue # Não processa como venda bruto aqui

                # --- LÓGICA PADRÃO (VENDA BRUTO) ---
                c_dt, c_bt = localizar_coluna(df_t, S_DATA), localizar_coluna(df_t, S_BRUTO)
                if c_dt and c_bt:
                    # Filtro de Vouchers em máquinas como Rede/Cielo
                    if ignorar_vouchers:
                        c_band = localizar_coluna(df_t, ['BANDEIRA', 'MODALIDADE', 'PRODUTO'])
                        if c_band:
                            df_t = df_t[~df_t[c_band].astype(str).str.contains('|'.join(VOUCHER_KEYS), case=False, na=False)]

                    df_t['DT_L'] = pd.to_datetime(df_t[c_dt], errors='coerce').dt.date
                    df_t['BT_L'] = df_t[c_bt].apply(limpar_valor)
                    
                    # Captura taxas das demais operadoras
                    c_tx = localizar_coluna(df_t, S_TAXA)
                    if c_tx:
                        daily_tx = df_t.groupby('DT_L')[c_tx].apply(lambda x: x.apply(limpar_valor, eh_despesa=True).sum()).reset_index()
                        for _, r in daily_tx.iterrows():
                            if r[c_tx] > 0: l_desp.append({'data': r['DT_L'], 'valor': r[c_tx], 'origem': f.name.split('.')[0], 'compl': ''})

                    v_cons.append(df_t[['DT_L', 'BT_L']].rename(columns={'DT_L': 'DATA', 'BT_L': 'VALOR'}))
                    st.success(f"✅ {f.name} carregado.")

        if v_cons:
            df_c = pd.concat(v_cons).groupby('DATA')['VALOR'].sum().reset_index().rename(columns={'VALOR': 'CART_BRUTO'})
            df_f = pd.merge(df_raz, df_c, on='DATA', how='outer').fillna(0).sort_values('DATA')
            df_f['SOBRA'] = df_f['RAZAO_BRUTO'] - df_f['CART_BRUTO']
            
            st.subheader("📊 Relatório Comparativo")
            st.dataframe(df_f, use_container_width=True)

            # Preparação de Importação ERP (Padrão Questor/Domínio)
            erp_data = []
            for _, r in df_f.iterrows():
                if r['SOBRA'] > 0.01: erp_data.append(["", 35, 1071, r['DATA'], f"{r['SOBRA']:.2f}".replace('.', ','), 31, "SOBRA DE CAIXA", "", "", "", ""])
            for d in l_desp:
                erp_data.append(["", 7014, 1071, d['data'], f"{d['valor']:.2f}".replace('.', ','), 201, f"{d['origem']} {d['compl']}".strip(), "", "", "", ""])
            
            df_e = pd.DataFrame(erp_data, columns=["Lanc. Automatico", "DEBITO", "CREDITO", "Data Mov.", "VALOR", "CODIGO HISTORICO", "COMPL. HISTORICO", "CCDEBITO", "CCCREDITO", "Nr. Doc.", "COMPLEMENTO"])
            st.download_button("📥 Baixar CSV para Importação ERP", data=df_e.to_csv(index=False, sep=';').encode('utf-8-sig'), file_name="importar_contabilidade.csv", use_container_width=True)
