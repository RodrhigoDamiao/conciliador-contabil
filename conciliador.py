import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# 1. Configuração inicial
st.set_page_config(page_title="Auditor Contábil Pro", layout="wide", page_icon="⚖️")

# --- DICIONÁRIO DE SINÔNIMOS ATUALIZADO ---
S_DATA = ['DATA DA TRANSAÇÃO', 'DATA DA VENDA', 'DATA', 'DT. VENDA', 'PAGAMENTO *']
S_BRUTO = ['VALOR PARCELA BRUTO', 'VALOR BRUTO DA PARCELA', 'VALOR DA VENDA ATUALIZADO', 'VL TRANSAÇÃO', 'VALOR BRUTO R$', 'VALOR DO PRODUTO (TRANSACTION_AMOUNT)', 'VALOR BRUTO', 'VALOR']
S_TAXA = ['VALOR TOTAL DAS TAXAS DESCONTADAS (MDR+RECEBIMENTO AUTOMÁTICO)', 'VALOR TAXA', 'DESCONTO PARCELA', 'TAXA/TARIFA', 'CUSTO DA TRANSAÇÃO']
S_STATUS = ['STATUS DA VENDA', 'STATUS', 'SITUAÇÃO', 'STATUS DA OPERAÇÃO (STATUS)']
S_CARTAO = ['NÚMERO DO CARTÃO', 'Nº CARTÃO', 'CARTÃO']
S_AUTORIZACAO = ['NÚMERO DA AUTORIZAÇÃO (AUTO)', 'CÓDIGO DE AUTORIZAÇÃO', 'Nº DE AUTORIZAÇÃO', 'AUTORIZAÇÃO']

# Bandeiras de Voucher para exclusão em máquinas de terceiros
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
                if any(x in ' '.join(vals) for x in ['DATA', 'STATUS', 'VALOR', 'BRUTO', 'PAGAMENTO *']):
                    df.columns = df.iloc[i]; df = df.iloc[i+1:].reset_index(drop=True); break
        df = df.loc[:, df.columns.notna()]
        return df[~df.iloc[:, 0].astype(str).str.contains('TOTAL|EMISSÃO|EMPRESA', case=False, na=False)].dropna(how='all')
    except: return None

st.title("⚖️ Auditoria Contábil Pro")

with st.sidebar:
    st.header("⚙️ Configurações")
    metodo = st.selectbox("Estratégia de Ajuste", ["Sem Ajuste", "Dia Seguinte (Cascata)", "Dia Anterior"])
    ignorar_vouchers = st.checkbox("Excluir Vouchers de Máquinas de Terceiros", value=True)
    st.divider()
    f_raz = st.file_uploader("📘 1. Livro Razão", type=['xlsx', 'xls', 'xlsb', 'csv'])
    f_carts = st.file_uploader("💳 2. Máquinas e Vouchers (Selecione todos)", type=['xlsx', 'xls', 'xlsb', 'csv'], accept_multiple_files=True)
    f_univ = st.file_uploader("🌐 3. Lançamento Universal (PIX)", type=['xlsx', 'xls', 'csv'])

if f_raz:
    # Mostra os arquivos carregados antes de processar
    if f_carts:
        st.write(f"📂 {len(f_carts)} arquivos de cartões prontos para análise.")
    
    # BOTÃO DE EXECUÇÃO
    if st.button("🚀 Executar Auditoria Contábil", use_container_width=True):
        df_raz_raw = carregar_dados_inteligente(f_raz)
        c_dt_r, c_val_r = localizar_coluna(df_raz_raw, ['DATA']), localizar_coluna(df_raz_raw, ['DÉBITO', 'DEBITO', 'VALOR'])
        
        if c_dt_r and c_val_r:
            df_raz_raw['DT'] = pd.to_datetime(df_raz_raw[c_dt_r], errors='coerce').dt.date
            df_raz_raw['VAL'] = df_raz_raw[c_val_r].apply(limpar_valor)
            df_raz = df_raz_raw.groupby('DT')['VAL'].sum().reset_index().rename(columns={'DT': 'DATA', 'VAL': 'Faturamento Total'})

            v_cons, l_desp = [], []
            all_files = (f_carts if f_carts else []) + ([f_univ] if f_univ else [])
            
            for f in all_files:
                df_t = carregar_dados_inteligente(f)
                if df_t is not None:
                    nome_arq = f.name.upper()
                    
                    # Lógica VR Reembolso (Taxa)
                    if "REEMBOLSO" in nome_arq and "VR" in nome_arq:
                        c_pg, c_vb, c_vl = localizar_coluna(df_t, ['PAGAMENTO *']), localizar_coluna(df_t, ['VALOR BRUTO']), localizar_coluna(df_t, ['VALOR LÍQUIDO'])
                        if c_pg:
                            df_t['DT_PG'] = pd.to_datetime(df_t[c_pg], errors='coerce').dt.date
                            df_t['TX'] = df_t[c_vb].apply(limpar_valor) - df_t[c_vl].apply(limpar_valor)
                            for _, row in df_t.groupby('DT_PG')['TX'].sum().reset_index().iterrows():
                                if row['TX'] > 0: l_desp.append({'data': row['DT_PG'], 'valor': row['TX'], 'origem': 'VR BENEFICIOS', 'compl': '(Taxa Reembolso)'})
                        continue

                    c_dt, c_bt, c_st = [localizar_coluna(df_t, x) for x in [S_DATA, S_BRUTO, S_STATUS]]
                    if c_dt and c_bt:
                        # Filtros de Status e Vouchers
                        if c_st:
                            df_t = df_t[df_t[c_st].astype(str).str.contains('APROVADA|PROCESSADA|PAGO|CONCLUIDA|APPROVED', case=False, na=True)]
                            df_t = df_t[~df_t[c_st].astype(str).str.contains('CANCELADO|ESTORNADO|NEGADO', case=False, na=False)]
                        
                        if ignorar_vouchers:
                            c_band = localizar_coluna(df_t, ['BANDEIRA', 'MODALIDADE', 'PRODUTO'])
                            if c_band: df_t = df_t[~df_t[c_band].astype(str).str.contains('|'.join(VOUCHER_KEYS), case=False, na=False)]

                        # Deduplicação Segura (Exceto se for planilha de parcelas Sipag/Cabal/Caixa)
                        c_card, c_auth = localizar_coluna(df_t, S_CARTAO), localizar_coluna(df_t, S_AUTORIZACAO)
                        if c_card and c_auth and "PARCELA" not in str(c_bt).upper():
                            df_t = df_t.drop_duplicates(subset=[c_card, c_auth])

                        df_t['DT_L'] = pd.to_datetime(df_t[c_dt], errors='coerce').dt.date
                        df_t['BT_L'] = df_t[c_bt].apply(limpar_valor)
                        
                        # Taxas/Despesas
                        c_mp1, c_mpf = localizar_coluna(df_t, ['TARIFA DO MERCADO PAGO (MERCADOPAGO_FEE)']), localizar_coluna(df_t, ['CUSTOS DE PARCELAMENTO (FINANCING_FEE)'])
                        if c_mp1:
                            v_tar = df_t[c_mp1].apply(lambda x: limpar_valor(x, True)).sum()
                            if v_tar > 0: l_desp.append({'data': df_t['DT_L'].dropna().iloc[0], 'valor': v_tar, 'origem': nome_arq, 'compl': ''})
                            if c_mpf:
                                v_fin = df_t[c_mpf].apply(lambda x: limpar_valor(x, True)).sum()
                                if v_fin > 0: l_desp.append({'data': df_t['DT_L'].dropna().iloc[0], 'valor': v_fin, 'origem': nome_arq, 'compl': '(Custos de parcelamento)'})
                        else:
                            c_tx = localizar_coluna(df_t, S_TAXA)
                            if c_tx:
                                v_tx = df_t[c_tx].apply(lambda x: limpar_valor(x, True)).sum()
                                if v_tx > 0: l_desp.append({'data': df_t['DT_L'].dropna().iloc[0], 'valor': v_tx, 'origem': f.name.split('.')[0], 'compl': ''})

                        v_cons.append(df_t[['DT_L', 'BT_L']].rename(columns={'DT_L': 'DATA', 'BT_L': 'VALOR'}))

            if v_cons:
                df_c = pd.concat(v_cons).groupby('DATA')['VALOR'].sum().reset_index().rename(columns={'VALOR': 'Cartões Total'})
                df_f = pd.merge(df_raz, df_c, on='DATA', how='outer').fillna(0).sort_values('DATA')
                
                # Ajuste Cascata
                c_aj = df_f['Cartões Total'].values.copy(); r_vl = df_f['Faturamento Total'].values
                if metodo == "Dia Seguinte (Cascata)":
                    for i in range(len(c_aj)-1):
                        if c_aj[i] > r_vl[i]: dif = c_aj[i]-r_vl[i]; c_aj[i]=r_vl[i]; c_aj[i+1]+=dif
                
                df_f['Cartões Total'] = c_aj
                df_f['Venda à Vista'] = df_f['Faturamento Total'] - c_aj
                
                st.divider()
                st.subheader("📋 Conferência de Caixa")
                st.dataframe(df_f, use_container_width=True)

                # Exportação ERP
                erp_data = []
                for _, r in df_f.iterrows():
                    if r['Venda à Vista'] > 0.01: erp_data.append(["", 35, 1071, r['DATA'], f"{r['Venda à Vista']:.2f}".replace('.', ','), 31, "VENDA A VISTA", "", "", "", ""])
                for d in l_desp:
                    erp_data.append(["", 7014, 1071, d['data'], f"{d['valor']:.2f}".replace('.', ','), 201, f"{d['origem']} {d['compl']}".strip(), "", "", "", ""])
                
                df_e = pd.DataFrame(erp_data, columns=["Lanc. Automatico", "DEBITO", "CREDITO", "Data Mov.", "VALOR", "CODIGO HISTORICO", "COMPL. HISTORICO", "CCDEBITO", "CCCREDITO", "Nr. Doc.", "COMPLEMENTO"])
                st.download_button("📥 Baixar Importação ERP", data=df_e.to_csv(index=False, sep=';').encode('utf-8-sig'), file_name="importar.csv", use_container_width=True)
