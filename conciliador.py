import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# 1. Configuração inicial
st.set_page_config(page_title="Conciliador Contábil", layout="wide")

# Sinônimos ampliados e flexíveis
S_DATA = ['DATA', 'VENDA', 'MOVIMENTO', 'TRANSAÇÃO', 'DT', 'EMISSÃO']
S_BRUTO = ['BRUTO', 'VALOR', 'VLR', 'TOTAL', 'DEBITO', 'DÉBITO']
S_LIQ = ['LIQUIDO', 'LÍQUIDO', 'RECEBIDO', 'PAGAMENTO', 'VALOR_LIQ']

def limpar_valor(valor):
    """Converte valores com R$, pontos e vírgulas para número real."""
    if pd.isna(valor): return 0.0
    s = str(valor).upper().replace('R$', '').replace(' ', '')
    # Se tiver ponto e vírgula, assume formato brasileiro (1.000,00)
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.')
    # Se só tiver vírgula, assume que é o decimal
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(re.sub(r'[^-0-9.]', '', s))
    except:
        return 0.0

def localizar_coluna_fuzzy(df, sinonimos):
    """Procura colunas que contenham as palavras-chave no nome."""
    for col in df.columns:
        c_upper = str(col).strip().upper()
        for s in sinonimos:
            if s in c_upper: return col
    return None

def carregar_dados_inteligente(file):
    try:
        ext = file.name.split('.')[-1].lower()
        df = pd.read_excel(file, engine='pyxlsb', header=None) if ext == 'xlsb' else pd.read_excel(file, header=None)
        
        # Tenta achar a linha onde os dados começam (procura por palavras de data)
        for i, row in df.iterrows():
            if i > 50: break
            vals = [str(v).strip().upper() for v in row.values if pd.notna(v)]
            if any(s in ' '.join(vals) for s in S_DATA):
                df.columns = df.iloc[i]
                df = df.iloc[i+1:].reset_index(drop=True)
                return df.loc[:, df.columns.notna()]
        
        # Se não achou 'DATA' no corpo, assume que a primeira linha é o cabeçalho
        df = pd.read_excel(file, engine='pyxlsb') if ext == 'xlsb' else pd.read_excel(file)
        return df
    except: return None

st.title("⚖️ Conciliador Contábil")

with st.sidebar:
    st.header("1. Arquivos")
    metodo = st.selectbox("Ajuste de Saldo", ["Sem Ajuste", "Dia Seguinte (Cascata)", "Dia Anterior"])
    f_raz = st.file_uploader("📘 Livro Razão", type=['xlsx', 'xls', 'xlsb', 'xlsm'])
    f_carts = st.file_uploader("💳 Máquinas de Cartão (1 ou várias)", type=['xlsx', 'xls', 'xlsb', 'xlsm'], accept_multiple_files=True)
    f_univ = st.file_uploader("🌐 PIX / Outros", type=['xlsx', 'xls', 'csv'])

if f_raz:
    df_raz_raw = carregar_dados_inteligente(f_raz)
    c_dt_r = localizar_coluna_fuzzy(df_raz_raw, ['DATA'])
    c_val_r = localizar_coluna_fuzzy(df_raz_raw, ['DÉBITO', 'DEBITO', 'VALOR'])
    
    if c_dt_r and c_val_r:
        df_raz_raw['DT'] = pd.to_datetime(df_raz_raw[c_dt_r], errors='coerce').dt.date
        df_raz_raw['VAL_LIMPO'] = df_raz_raw[c_val_r].apply(limpar_valor)
        df_raz = df_raz_raw.groupby('DT')['VAL_LIMPO'].sum().reset_index()
        df_raz.columns = ['DATA', 'RAZAO_BRUTO']
        
        st.success(f"✅ Livro Razão carregado ({len(df_raz)} dias).")

        # Processamento das Máquinas
        v_cons = []
        l_desp = []
        
        all_f = list(f_carts) if f_carts else []
        if f_univ: all_f.append(f_univ)
        
        if all_f:
            for f in all_f:
                df_t = carregar_dados_inteligente(f)
                if df_t is not None:
                    c_dt = localizar_coluna_fuzzy(df_t, S_DATA)
                    c_bt = localizar_coluna_fuzzy(df_t, S_BRUTO)
                    c_lq = localizar_coluna_fuzzy(df_t, S_LIQ)
                    
                    if c_dt and c_bt:
                        nome_maq = f.name.split('.')[0].upper()
                        df_t['DT_L'] = pd.to_datetime(df_t[c_dt], errors='coerce').dt.date
                        df_t['BT_LIMPO'] = df_t[c_bt].apply(limpar_valor)
                        df_t['LQ_LIMPO'] = df_t[c_lq].apply(limpar_valor) if c_lq else df_t['BT_LIMPO']
                        
                        # Soma despesas
                        desp_tot = (df_t['BT_LIMPO'] - df_t['LQ_LIMPO']).sum()
                        if desp_tot > 0:
                            l_desp.append({'data': df_t['DT_L'].dropna().iloc[0] if not df_t['DT_L'].dropna().empty else None, 
                                           'valor': desp_tot, 'origem': nome_maq})
                        
                        v_cons.append(df_t[['DT_L', 'BT_LIMPO']].rename(columns={'DT_L': 'DATA', 'BT_LIMPO': 'VALOR'}))
                        st.info(f"📂 Arquivo reconhecido: {f.name} (R$ {df_t['BT_LIMPO'].sum():,.2f})")
                    else:
                        st.warning(f"⚠️ Ignorado: {f.name} (Colunas de Data ou Valor não identificadas)")

            if v_cons:
                df_c = pd.concat(v_cons).groupby('DATA')['VALOR'].sum().reset_index()
                df_c.columns = ['DATA', 'CART_BRUTO']
                
                df_f = pd.merge(df_raz, df_c, on='DATA', how='outer').fillna(0).sort_values('DATA')
                
                # Ajuste de Redistribuição
                c_aj = df_f['CART_BRUTO'].values.copy()
                r_vl = df_f['RAZAO_BRUTO'].values
                if metodo == "Dia Seguinte (Cascata)":
                    for i in range(len(c_aj)-1):
                        if c_aj[i] > r_vl[i]:
                            dif = c_aj[i]-r_vl[i]; c_aj[i]=r_vl[i]; c_aj[i+1]+=dif
                elif metodo == "Dia Anterior":
                    for i in range(len(c_aj)-1, 0, -1):
                        if c_aj[i] > r_vl[i]:
                            dif = c_aj[i]-r_vl[i]; c_aj[i]=r_vl[i]; c_aj[i-1]+=dif
                
                df_f['CART_AJ'], df_f['SOBRA'] = c_aj, df_f['RAZAO_BRUTO'] - c_aj
                
                st.subheader("📋 Resumo")
                st.dataframe(df_f, use_container_width=True)

                # Exportação
                erp_data = []
                for _, r in df_f.iterrows():
                    if r['SOBRA'] > 0.01: erp_data.append(["", 35, 1071, r['DATA'], round(r['SOBRA'], 2), 31, "", "", "", "", ""])
                for d in l_desp:
                    if d['data']: erp_data.append(["", 7014, 1071, d['data'], round(d['valor'], 2), 201, d['origem'], "", "", "", ""])
                
                df_e = pd.DataFrame(erp_data, columns=["Lanc. Automatico", "DEBITO", "CREDITO", "Data Mov.", "VALOR", "CODIGO HISTORICO", "COMPL. HISTORICO", "CCDEBITO", "CCCREDITO", "Nr. Doc.", "COMPLEMENTO"])
                st.download_button("📥 Baixar Arquivo ERP", data=df_e.to_csv(index=False).encode('utf-8-sig'), file_name="importar.csv", mime="text/csv")
        else:
            st.info("ℹ️ Agora suba ao menos uma planilha de cartão ou PIX.")
