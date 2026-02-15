import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from io import BytesIO

# 1. Configuração inicial (Sempre a primeira linha)
st.set_page_config(page_title="Auditor Contábil Pro", layout="wide", page_icon="📊")

# 2. Estilo CSS simplificado em linha única para evitar o erro do Python 3.13
st.markdown("<style>.stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }</style>", unsafe_allow_index=True)

# Sinônimos para as colunas
S_DATA = ['DATA', 'DATA DA VENDA', 'DT. VENDA', 'DATA TRANSAÇÃO', 'DATA MOVIMENTO', 'VENCIMENTO', 'DATA OPERAÇÃO']
S_BRUTO = ['VALOR', 'VALOR BRUTO', 'VLR BRUTO', 'VALOR TOTAL', 'VALOR VENDA', 'BRUTO', 'DÉBITO', 'DEBITO']
S_LIQ = ['VALOR LIQUIDO', 'VLR LIQUIDO', 'VALOR LÍQUIDO', 'LÍQUIDO', 'RECEBIDO', 'VALOR PAGAMENTO']

def carregar_dados(file):
    try:
        ext = file.name.split('.')[-1].lower()
        df = pd.read_excel(file, engine='pyxlsb', header=None) if ext == 'xlsb' else pd.read_excel(file, header=None)
        for i, row in df.iterrows():
            vals = [str(v).strip().upper() for v in row.values if pd.notna(v)]
            if 'DATA' in vals:
                df.columns = df.iloc[i]; df = df.iloc[i+1:].reset_index(drop=True)
                return df.loc[:, df.columns.notna()]
        return df
    except: return None

def find_c(df, opts):
    cols = {str(c).strip().upper(): c for c in df.columns}
    for o in opts:
        if o in cols: return cols[o]
    return None

st.title("⚖️ Auditoria Contábil")

with st.sidebar:
    st.header("Upload")
    metodo = st.selectbox("Ajuste", ["Sem Ajuste", "Dia Seguinte (Cascata)", "Dia Anterior"])
    f_raz = st.file_uploader("📘 Livro Razão", type=['xlsx', 'xls', 'xlsb', 'xlsm'])
    f_carts = st.file_uploader("💳 Planilhas Cartão", type=['xlsx', 'xls', 'xlsb', 'xlsm'], accept_multiple_files=True)
    f_univ = st.file_uploader("🌐 Planilha Universal (PIX/Outros)", type=['xlsx', 'xls', 'csv'])

if f_raz:
    df_raz_raw = carregar_dados(f_raz)
    if df_raz_raw is not None:
        c_dt_r = find_c(df_raz_raw, ['DATA'])
        c_val_r = find_c(df_raz_raw, ['DÉBITO', 'DEBITO', 'VALOR'])
        
        if c_dt_r and c_val_r:
            df_raz_raw['DT'] = pd.to_datetime(df_raz_raw[c_dt_r], errors='coerce').dt.date
            df_raz = df_raz_raw.groupby('DT')[c_val_r].sum().reset_index()
            df_raz.columns = ['DATA', 'RAZAO_BRUTO']
            
            v_cons = []; res_maq = {}; l_desp = []
            all_f = list(f_carts) if f_carts else []
            if f_univ: all_f.append(f_univ)
            
            for f in all_f:
                df_t = carregar_dados(f)
                if df_t is not None:
                    c_dt, c_bt, c_lq = find_c(df_t, S_DATA), find_c(df_t, S_BRUTO), find_c(df_t, S_LIQ)
                    if c_dt and c_bt:
                        nome = f.name.split('.')[0].upper()
                        df_t['DT_L'] = pd.to_datetime(df_t[c_dt], errors='coerce').dt.date
                        bt_t = pd.to_numeric(df_t[c_bt], errors='coerce').sum()
                        lq_t = pd.to_numeric(df_t[c_lq], errors='coerce').sum() if c_lq else bt_t
                        ds_t = bt_t - lq_t
                        res_maq[nome] = {'bruto': bt_t, 'despesa': ds_t}
                        if ds_t > 0: l_desp.append({'data': df_t['DT_L'].iloc[0], 'valor': ds_t, 'origem': nome})
                        v_cons.append(df_t[['DT_L', c_bt]].rename(columns={'DT_L': 'DATA', c_bt: 'VALOR'}))

            if v_cons:
                df_c = pd.concat(v_cons).groupby('DATA')['VALOR'].sum().reset_index()
                df_c.columns = ['DATA', 'CART_BRUTO']
                df_f = pd.merge(df_raz, df_c, on='DATA', how='outer').fillna(0).sort_values('DATA')
                
                c_aj = df_f['CART_BRUTO'].values.copy(); r_vl = df_f['RAZAO_BRUTO'].values
                if metodo == "Dia Seguinte (Cascata)":
                    for i in range(len(c_aj)-1):
                        if c_aj[i] > r_vl[i]: dif = c_aj[i]-r_vl[i]; c_aj[i]=r_vl[i]; c_aj[i+1]+=dif
                elif metodo == "Dia Anterior":
                    for i in range(len(c_aj)-1, 0, -1):
                        if c_aj[i] > r_vl[i]: dif = c_aj[i]-r_vl[i]; c_aj[i]=r_vl[i]; c_aj[i-1]+=dif
                
                df_f['CART_AJ'], df_f['SOBRA'] = c_aj, df_f['RAZAO_BRUTO'] - c_aj
                
                st.subheader("📊 Resumo do Mês")
                col1, col2, col3 = st.columns(3)
                col1.metric("Faturamento Razão", f"R$ {df_f['RAZAO_BRUTO'].sum():,.2f}")
                col2.metric("Total Identificado", f"R$ {df_f['CART_BRUTO'].sum():,.2f}")
                col3.metric("Venda em Dinheiro", f"R$ {df_f['SOBRA'].sum():,.2f}")
                st.dataframe(df_f, use_container_width=True)
                
                st.divider()
                if st.button("Gerar Relatório PDF"):
                    pdf = FPDF(); pdf.add_page(); pdf.set_font('Arial', 'B', 14)
                    pdf.cell(0, 10, 'AUDITORIA CONTABIL', 0, 1, 'C'); pdf.ln(5)
                    pdf.set_font('Arial', 'B', 10); pdf.cell(0, 10, '1. RESUMO GERAL', ln=1)
                    pdf.set_font('Arial', '', 10)
                    pdf.cell(0, 8, f"Razao: R$ {df_f['RAZAO_BRUTO'].sum():,.2f}", ln=1)
                    pdf.cell(0, 8, f"Identificado: R$ {df_f['CART_BRUTO'].sum():,.2f}", ln=1)
                    pdf.cell(0, 8, f"Dinheiro: R$ {df_f['SOBRA'].sum():,.2f}", ln=1); pdf.ln(5)
                    
                    pdf.set_font('Arial', 'B', 10); pdf.cell(60, 8, 'Operacao', 1); pdf.cell(40, 8, 'Bruto', 1); pdf.cell(40, 8, 'Despesa', 1); pdf.cell(30, 8, '% Taxa', 1); pdf.ln()
                    pdf.set_font('Arial', '', 9)
                    for k, v in res_maq.items():
                        tx = (v['despesa']/v['bruto']*100) if v['bruto'] > 0 else 0
                        pdf.cell(60, 8, k[:25], 1); pdf.cell(40, 8, f"{v['bruto']:.2f}", 1); pdf.cell(40, 8, f"{v['despesa']:.2f}", 1); pdf.cell(30, 8, f"{tx:.2f}%", 1); pdf.ln()
                    
                    pdf_out = pdf.output(dest='S').encode('latin-1')
                    st.download_button("📥 Baixar PDF", data=pdf_out, file_name="auditoria.pdf", mime="application/pdf")

                # Exportação ERP
                erp_data = []
                for _, r in df_f.iterrows():
                    if r['SOBRA'] > 0.01: erp_data.append(["", 35, 1071, r['DATA'], round(r['SOBRA'], 2), 31, "", "", "", "", ""])
                for d in l_desp: erp_data.append(["", 7014, 1071, d['data'], round(d['valor'], 2), 201, d['origem'], "", "", "", ""])
                df_e = pd.DataFrame(erp_data, columns=["Lanc. Automatico", "DEBITO", "CREDITO", "Data Mov.", "VALOR", "CODIGO HISTORICO", "COMPL. HISTORICO", "CCDEBITO", "CCCREDITO", "Nr. Doc.", "COMPLEMENTO"])
                st.download_button("💾 Exportar ERP (CSV)", data=df_e.to_csv(index=False).encode('utf-8-sig'), file_name="importar.csv", mime="text/csv")
