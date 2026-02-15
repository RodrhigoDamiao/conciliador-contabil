import streamlit as st
import pandas as pd
import numpy as np
import io

# 1. Configuração inicial
st.set_page_config(page_title="Conciliador Contábil", layout="wide")

# Sinônimos para as colunas (Para o sistema achar os dados sozinho)
S_DATA = ['DATA', 'DATA DA VENDA', 'DT. VENDA', 'DATA TRANSAÇÃO', 'DATA MOVIMENTO', 'VENCIMENTO', 'DATA OPERAÇÃO']
S_BRUTO = ['VALOR', 'VALOR BRUTO', 'VLR BRUTO', 'VALOR TOTAL', 'VALOR VENDA', 'BRUTO', 'DÉBITO', 'DEBITO']
S_LIQ = ['VALOR LIQUIDO', 'VLR LIQUIDO', 'VALOR LÍQUIDO', 'LÍQUIDO', 'RECEBIDO', 'VALOR PAGAMENTO']

def carregar_dados(file):
    """Busca a linha do cabeçalho automaticamente"""
    try:
        ext = file.name.split('.')[-1].lower()
        if ext == 'xlsb':
            df = pd.read_excel(file, engine='pyxlsb', header=None)
        else:
            df = pd.read_excel(file, header=None)
        
        # Procura a palavra DATA nas primeiras 30 linhas
        for i, row in df.iterrows():
            if i > 30: break
            vals = [str(v).strip().upper() for v in row.values if pd.notna(v)]
            if 'DATA' in vals:
                df.columns = df.iloc[i]
                df = df.iloc[i+1:].reset_index(drop=True)
                return df.loc[:, df.columns.notna()]
        return df
    except: return None

def find_c(df, opts):
    """Localiza a coluna exata baseada nos sinônimos"""
    cols = {str(c).strip().upper(): c for c in df.columns}
    for o in opts:
        if o in cols: return cols[o]
    return None

st.title("⚖️ Conciliador de Cartões e Razão")
st.write("Foco: Processamento de dados e Arquivo de Importação ERP")

with st.sidebar:
    st.header("1. Arquivos")
    metodo = st.selectbox("Ajuste de Saldo", ["Sem Ajuste", "Dia Seguinte (Cascata)", "Dia Anterior"])
    f_raz = st.file_uploader("📘 Suba o Livro Razão", type=['xlsx', 'xls', 'xlsb', 'xlsm'])
    f_carts = st.file_uploader("💳 Suba todos os Cartões", type=['xlsx', 'xls', 'xlsb', 'xlsm'], accept_multiple_files=True)
    f_univ = st.file_uploader("🌐 Planilha Universal (PIX/Outros)", type=['xlsx', 'xls', 'csv'])

if f_raz:
    df_raz_raw = carregar_dados(f_raz)
    if df_raz_raw is not None:
        c_dt_r = find_c(df_raz_raw, ['DATA'])
        c_val_r = find_c(df_raz_raw, ['DÉBITO', 'DEBITO', 'VALOR'])
        
        if c_dt_r and c_val_r:
            # Prepara o Razão
            df_raz_raw['DT'] = pd.to_datetime(df_raz_raw[c_dt_r], errors='coerce').dt.date
            df_raz_raw[c_val_r] = pd.to_numeric(df_raz_raw[c_val_r], errors='coerce').fillna(0)
            df_raz = df_raz_raw.groupby('DT')[c_val_r].sum().reset_index()
            df_raz.columns = ['DATA', 'RAZAO_BRUTO']
            
            st.success(f"✅ Razão processado: {len(df_raz)} dias encontrados.")

            if f_carts or f_univ:
                v_cons = []   # Lista para somar as vendas
                l_desp = []   # Lista para as despesas (taxas)
                
                all_f = list(f_carts) if f_carts else []
                if f_univ: all_f.append(f_univ)
                
                # Processa cada arquivo de cartão/universal
                for f in all_f:
                    df_t = carregar_dados(f)
                    if df_t is not None:
                        c_dt = find_c(df_t, S_DATA)
                        c_bt = find_c(df_t, S_BRUTO)
                        c_lq = find_c(df_t, S_LIQ)
                        
                        if c_dt and c_bt:
                            nome_maq = f.name.split('.')[0].upper()
                            df_t['DT_L'] = pd.to_datetime(df_t[c_dt], errors='coerce').dt.date
                            
                            # Valores Numéricos
                            v_bt = pd.to_numeric(df_t[c_bt], errors='coerce').fillna(0)
                            v_lq = pd.to_numeric(df_t[c_lq], errors='coerce').fillna(v_bt) if c_lq else v_bt
                            
                            # Soma de Despesa por arquivo
                            v_desp = (v_bt - v_lq).sum()
                            if v_desp > 0:
                                # Pega a primeira data válida do arquivo para o lançamento de despesa
                                dt_desp = df_t['DT_L'].iloc[0] if not df_t['DT_L'].empty else None
                                l_desp.append({'data': dt_desp, 'valor': v_desp, 'origem': nome_maq})
                            
                            # Guarda para o somatório bruto diário
                            v_cons.append(df_t[['DT_L', c_bt]].rename(columns={'DT_L': 'DATA', c_bt: 'VALOR'}))

                if v_cons:
                    # Une todos os cartões
                    df_c = pd.concat(v_cons)
                    df_c['VALOR'] = pd.to_numeric(df_c['VALOR'], errors='coerce').fillna(0)
                    df_c = df_c.groupby('DATA')['VALOR'].sum().reset_index()
                    df_c.columns = ['DATA', 'CART_BRUTO']
                    
                    # Faz o De/Para com o Razão
                    df_f = pd.merge(df_raz, df_c, on='DATA', how='outer').fillna(0).sort_values('DATA')
                    
                    # Lógica de Ajuste (Redistribuição)
                    c_aj = df_f['CART_BRUTO'].values.copy()
                    r_vl = df_f['RAZAO_BRUTO'].values
                    
                    if metodo == "Dia Seguinte (Cascata)":
                        for i in range(len(c_aj)-1):
                            if c_aj[i] > r_vl[i]:
                                dif = c_aj[i]-r_vl[i]
                                c_aj[i] = r_vl[i]
                                c_aj[i+1] += dif
                    elif metodo == "Dia Anterior":
                        for i in range(len(c_aj)-1, 0, -1):
                            if c_aj[i] > r_vl[i]:
                                dif = c_aj[i]-r_vl[i]
                                c_aj[i] = r_vl[i]
                                c_aj[i-1] += dif
                    
                    df_f['CART_AJ'] = c_aj
                    df_f['SOBRA_CAIXA'] = df_f['RAZAO_BRUTO'] - c_aj
                    
                    # Exibição
                    st.divider()
                    st.subheader("📋 Resumo da Conciliação")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Razão", f"R$ {df_f['RAZAO_BRUTO'].sum():,.2f}")
                    col2.metric("Total Cartões (Bruto)", f"R$ {df_f['CART_BRUTO'].sum():,.2f}")
                    col3.metric("Sobra p/ Caixa (Espécie)", f"R$ {df_f['SOBRA_CAIXA'].sum():,.2f}")
                    
                    st.dataframe(df_f, use_container_width=True)

                    # Exportação ERP
                    st.divider()
                    st.subheader("💾 Exportação para o ERP")
                    
                    erp_data = []
                    # 1. Lançamentos de Sobra de Caixa (Débito 35, Crédito 1071)
                    for _, r in df_f.iterrows():
                        if r['SOBRA_CAIXA'] > 0.01:
                            erp_data.append(["", 35, 1071, r['DATA'], round(r['SOBRA_CAIXA'], 2), 31, "", "", "", "", ""])
                    
                    # 2. Lançamentos de Despesas (Débito 7014, Crédito 1071)
                    for d in l_desp:
                        if d['data']:
                            erp_data.append(["", 7014, 1071, d['data'], round(d['valor'], 2), 201, d['origem'], "", "", "", ""])
                    
                    if erp_data:
                        df_e = pd.DataFrame(erp_data, columns=["Lanc. Automatico", "DEBITO", "CREDITO", "Data Mov.", "VALOR", "CODIGO HISTORICO", "COMPL. HISTORICO", "CCDEBITO", "CCCREDITO", "Nr. Doc.", "COMPLEMENTO"])
                        st.download_button(
                            label="📥 Baixar Arquivo de Importação (CSV)",
                            data=df_e.to_csv(index=False).encode('utf-8-sig'),
                            file_name="importar_erp.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
            else:
                st.info("ℹ️ Agora suba as planilhas de cartão no menu lateral para ver o resultado.")
