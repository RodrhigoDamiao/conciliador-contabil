import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# 1. Configuração inicial
st.set_page_config(page_title="Conciliador Contábil Pro", layout="wide")

# --- DICIONÁRIO DE SINÔNIMOS REVISADO ---
S_DATA = ['DATA DA VENDA', 'DATA DA TRANSAÇÃO', 'DATA DE PAGAMENTO', 'DATA', 'DT. VENDA']
# Prioridade para 'Parcela' para evitar duplicidade em vendas parceladas
S_BRUTO = ['VALOR BRUTO DA PARCELA', 'VALOR PARCELA BRUTO', 'VALOR BRUTO', 'VLR BRUTO', 'VALOR TOTAL']
S_LIQ = ['VALOR LÍQUIDO DA PARCELA/TRANSAÇÃO', 'VALOR PARCELA LIQUIDO', 'VALOR LÍQUIDO', 'LÍQUIDO']
S_TAXA = ['VALOR DA TAXA (MDR)', 'DESCONTO PARCELA', 'TAXA/TARIFA', 'VALOR DA TAXA', 'COMISSÃO']
S_STATUS = ['STATUS', 'SITUAÇÃO', 'STATUS DA VENDA', 'INDICADOR DE CANCELAMENTO']

def limpar_valor(valor, eh_despesa=False):
    if pd.isna(valor): return 0.0
    # Remove R$, espaços e normaliza pontos/vírgulas
    s = str(valor).upper().replace('R$', '').replace(' ', '').strip()
    if '.' in s and ',' in s: s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    
    try:
        num = float(re.sub(r'[^-0-9.]', '', s))
        # REGRA NOVA: Se for despesa, ignora o sinal de negativo (ex: Cielo)
        return abs(num) if eh_despesa else num
    except:
        return 0.0

def localizar_coluna(df, sinonimos):
    cols_reais = {str(c).strip().upper(): c for c in df.columns}
    for s in sinonimos:
        if s in cols_reais: return cols_reais[s]
    return None

def carregar_dados_inteligente(file):
    try:
        ext = file.name.split('.')[-1].lower()
        df = pd.read_excel(file, engine='pyxlsb', header=None) if ext == 'xlsb' else pd.read_excel(file, header=None)
        
        # Procura o cabeçalho real (Data, Valor ou Status)
        for i, row in df.iterrows():
            if i > 50: break
            vals = [str(v).strip().upper() for v in row.values if pd.notna(v)]
            if any(x in ' '.join(vals) for x in ['DATA', 'STATUS', 'VALOR', 'BRUTO']):
                df.columns = df.iloc[i]
                df = df.iloc[i+1:].reset_index(drop=True)
                # Remove linhas de 'TOTAL' (Cabal/Alelo/Cielo)
                df = df[~df.iloc[:, 0].astype(str).str.contains('TOTAL', case=False, na=False)]
                return df.loc[:, df.columns.notna()]
        return df
    except: return None

st.title("⚖️ Conciliador Contábil Pro")
st.markdown("### Processamento de Vendas e Despesas (Normalizado)")

with st.sidebar:
    st.header("⚙️ Configurações")
    metodo = st.selectbox("Estratégia de Ajuste", ["Sem Ajuste", "Dia Seguinte (Cascata)", "Dia Anterior"])
    f_raz = st.file_uploader("📘 1. Livro Razão", type=['xlsx', 'xls', 'xlsb', 'xlsm'])
    f_carts = st.file_uploader("💳 2. Planilhas de Cartão (Múltiplas)", type=['xlsx', 'xls', 'xlsb', 'xlsm'], accept_multiple_files=True)
    f_univ = st.file_uploader("🌐 3. PIX / Universal", type=['xlsx', 'xls', 'csv'])

if f_raz:
    df_raz_raw = carregar_dados_inteligente(f_raz)
    c_dt_r = localizar_coluna(df_raz_raw, ['DATA'])
    c_val_r = localizar_coluna(df_raz_raw, ['DÉBITO', 'DEBITO', 'VALOR'])
    
    if c_dt_r and c_val_r:
        df_raz_raw['DT'] = pd.to_datetime(df_raz_raw[c_dt_r], errors='coerce').dt.date
        df_raz_raw['VAL'] = df_raz_raw[c_val_r].apply(limpar_valor)
        df_raz = df_raz_raw.groupby('DT')['VAL'].sum().reset_index()
        df_raz.columns = ['DATA', 'RAZAO_BRUTO']

        v_cons = []; l_desp = []
        all_f = list(f_carts) if f_carts else []
        if f_univ: all_f.append(f_univ)
        
        for f in all_f:
            df_t = carregar_dados_inteligente(f)
            if df_t is not None:
                c_dt, c_bt, c_lq, c_st, c_tx = [localizar_coluna(df_t, x) for x in [S_DATA, S_BRUTO, S_LIQ, S_STATUS, S_TAXA]]
                
                if c_dt and c_bt:
                    # FILTRO DE STATUS: Apenas o que foi aprovado/pago
                    if c_st:
                        df_t = df_t[df_t[c_st].astype(str).str.contains('APROVADA|PROCESSADA|PAGO|CONCLUIDA', case=False, na=True)]
                    
                    df_t['DT_L'] = pd.to_datetime(df_t[c_dt], errors='coerce').dt.date
                    df_t['BT_L'] = df_t[c_bt].apply(limpar_valor)
                    
                    # REGRA DA DESPESA (ABS): Trata sinal negativo da Cielo
                    if c_tx:
                        df_t['TX_L'] = df_t[c_tx].apply(lambda x: limpar_valor(x, eh_despesa=True))
                    else:
                        v_liq = df_t[c_lq].apply(limpar_valor) if c_lq else df_t['BT_L']
                        df_t['TX_L'] = (df_t['BT_L'] - v_liq).abs()
                    
                    # Soma despesas por operadora
                    v_desp = df_t['TX_L'].sum()
                    if v_desp > 0 and not df_t['DT_L'].dropna().empty:
                        l_desp.append({'data': df_t['DT_L'].dropna().iloc[0], 'valor': v_desp, 'origem': f.name.split('.')[0]})
                    
                    v_cons.append(df_t[['DT_L', 'BT_L']].rename(columns={'DT_L': 'DATA', 'BT_L': 'VALOR'}))
                    st.info(f"📂 Processado: {f.name} (Bruto: R$ {df_t['BT_L'].sum():,.2f})")

        if v_cons:
            df_c = pd.concat(v_cons).groupby('DATA')['VALOR'].sum().reset_index()
            df_c.columns = ['DATA', 'CART_BRUTO']
            df_f = pd.merge(df_raz, df_c, on='DATA', how='outer').fillna(0).sort_values('DATA')
            
            # Redistribuição
            c_aj = df_f['CART_BRUTO'].values.copy(); r_vl = df_f['RAZAO_BRUTO'].values
            if metodo == "Dia Seguinte (Cascata)":
                for i in range(len(c_aj)-1):
                    if c_aj[i] > r_vl[i]: dif = c_aj[i]-r_vl[i]; c_aj[i]=r_vl[i]; c_aj[i+1]+=dif
            elif metodo == "Dia Anterior":
                for i in range(len(c_aj)-1, 0, -1):
                    if c_aj[i] > r_vl[i]: dif = c_aj[i]-r_vl[i]; c_aj[i]=r_vl[i]; c_aj[i-1]+=dif
            
            df_f['CART_AJ'], df_f['SOBRA'] = c_aj, df_f['RAZAO_BRUTO'] - c_aj
            
            st.divider()
            st.subheader("📋 Conferência de Caixa")
            st.dataframe(df_f, use_container_width=True)

            # Exportação ERP
            erp_data = []
            for _, r in df_f.iterrows():
                if r['SOBRA'] > 0.01: erp_data.append(["", 35, 1071, r['DATA'], round(r['SOBRA'], 2), 31, "", "", "", "", ""])
            for d in l_desp:
                erp_data.append(["", 7014, 1071, d['data'], round(d['valor'], 2), 201, d['origem'], "", "", "", ""])
            
            df_e = pd.DataFrame(erp_data, columns=["Lanc. Automatico", "DEBITO", "CREDITO", "Data Mov.", "VALOR", "CODIGO HISTORICO", "COMPL. HISTORICO", "CCDEBITO", "CCCREDITO", "Nr. Doc.", "COMPLEMENTO"])
            st.download_button("📥 Baixar Arquivo Importação ERP", data=df_e.to_csv(index=False).encode('utf-8-sig'), file_name="importar.csv", use_container_width=True)
