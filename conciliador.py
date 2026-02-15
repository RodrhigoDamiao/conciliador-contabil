import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
import io

# 1. Configuração inicial (Obrigatório ser a primeira linha)
st.set_page_config(page_title="Auditor Contábil Pro", layout="wide")

# Sinônimos para busca de colunas
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
                        bt_v = pd.to_numeric(df_t[c_bt], errors='coerce').fillna(0)
                        lq_v = pd.to_numeric(df_t[c_lq], errors='coerce').fillna(bt_v) if c_lq else bt_v
                        bt_t = bt_v.sum(); ds_t = bt_t - lq_v.sum()
                        res_maq[nome] = {'bruto': bt_t, 'despesa': ds_t}
                        if ds_t > 0: l_desp.append({'data': df_t['DT_L'].iloc[0], 'valor': ds_t, 'origem': nome})
                        v_cons.append(df_t[['DT_L', c_bt]].rename(columns={'DT_L': 'DATA', c_bt: 'VALOR'}))

            if v_cons:
                df_c = pd.concat(v_cons)
                df_c['VALOR'] = pd.to_numeric(df_c['VALOR'], errors='coerce').fillna(0)
                df_c = df_c.groupby('DATA')['VALOR'].sum().reset_index()
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
                
                st.subheader("📊 Resultados")
                st.dataframe(df_f, use_container_width=True)
                
                c_pdf, c_erp = st.columns(2)
                with c_pdf:
                    # NOVA LÓGICA DE PDF COM BUFFER DE MEMÓRIA
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 14)
                    pdf.cell(0, 10, 'RELATORIO DE AUDITORIA', align='C', ln=True)
                    pdf.ln(5)
                    
                    pdf.set_font('Arial', 'B', 10)
                    pdf.cell(0, 10, 'RESUMO POR MAQUINA', ln=True)
                    for k, v in res_maq.items():
                        tx = (v['despesa']/v['bruto']*100) if v['bruto'] > 0 else 0
                        pdf.set_font('Arial', '', 9)
                        pdf.cell(0, 8, f"{k}: Bruto R$ {v['bruto']:,.2f} | Taxa: {tx:.2f}%", ln=True)
                    
                    # Transformando o PDF em Bytes puros (Solução para o Unsupported Error)
                    output_pdf = io.BytesIO()
                    pdf_content = pdf.output(dest='S').encode('latin-1')
                    output_pdf.write(pdf_content)
                    output_pdf.seek(0)
                    
                    st.download_button(
                        label="📥 Baixar PDF",
                        data=output_pdf,
                        file_name="auditoria.pdf",
                        mime="application/pdf"
                    )
                
                with c_erp:
                    erp_data = []
                    for _, r in df_f.iterrows():
                        if r['SOBRA'] > 0.01: erp_data.append(["", 35, 1071, r['DATA'], round(r['SOBRA'], 2), 31, "", "", "", "", ""])
                    for d in l_desp: erp_data.append(["", 7014, 1071, d['data'], round(d['valor'], 2), 201, d['origem'], "", "", "", ""])
                    df_e = pd.DataFrame(erp_data, columns=["Lanc. Automatico", "DEBITO", "CREDITO", "Data Mov.", "VALOR", "CODIGO HISTORICO", "COMPL. HISTORICO", "CCDEBITO", "CCCREDITO", "Nr. Doc.", "COMPLEMENTO"])
                    st.download_button("💾 Exportar ERP", data=df_e.to_csv(index=False).encode('utf-8-sig'), file_name="importar.csv", mime="text/csv")
