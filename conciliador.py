import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from io import BytesIO

# --- CONFIGURAÇÃO DE APARÊNCIA ---
st.set_page_config(page_title="Auditor Contábil Pro", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
    h1, h2 { color: #2C3E50; }
    </style>
    """, unsafe_allow_index=True)

# --- FUNÇÕES DE TRATAMENTO ---

def carregar_excel_inteligente(file):
    """Lê o arquivo e localiza automaticamente a linha onde o cabeçalho começa."""
    try:
        # Carrega sem cabeçalho inicialmente para procurar a linha correta
        if file.name.endswith('.xlsb'):
            df = pd.read_excel(file, engine='pyxlsb', header=None)
        else:
            df = pd.read_excel(file, header=None)
        
        # Procura a linha que contém 'DATA' e 'DÉBITO' ou 'HISTÓRICO'
        for i, row in df.iterrows():
            vals = [str(v).strip().upper() for v in row.values]
            if 'DATA' in vals and ('DÉBITO' in vals or 'DEBITO' in vals or 'HISTÓRICO' in vals):
                df.columns = df.iloc[i] # Define os nomes das colunas
                df = df.iloc[i+1:].reset_index(drop=True) # Remove o lixo acima
                return df
        return df
    except Exception as e:
        st.error(f"Erro ao processar {file.name}: {e}")
        return None

def localizar_coluna(df, sinonimos):
    cols_reais = {str(c).strip().upper(): c for c in df.columns}
    for s in sinonimos:
        if s in cols_reais: return cols_reais[s]
    return None

# --- INTERFACE PRINCIPAL ---

st.title("⚖️ Sistema de Reconciliação Contábil")
st.info("O sistema está pronto. Suba o Livro Razão e as planilhas de cartão para processar.")

with st.sidebar:
    st.header("Configurações")
    estrategia = st.selectbox("Forma de Ajuste", ["Sem Ajuste", "Dia Seguinte (Cascata)", "Dia Anterior", "Média Mensal"])
    
    st.divider()
    file_razao = st.file_uploader("1. Suba o Livro Razão", type=['xlsx', 'xls', 'xlsb', 'xlsm'])
    files_cartao = st.file_uploader("2. Suba os Cartões (Múltiplos)", type=['xlsx', 'xls', 'xlsb', 'xlsm'], accept_multiple_files=True)
    file_universal = st.file_uploader("3. Planilha Universal / PIX", type=['xlsx', 'xls', 'csv'])

# Lógica de Execução
if file_razao:
    df_r = carregar_excel_inteligente(file_razao)
    if df_r is not None:
        st.success("✅ Livro Razão carregado e cabeçalho identificado!")
        
        if files_cartao or file_universal:
            st.write("---")
            st.subheader("Processando Conciliação...")
            # Aqui entrará a lógica de cálculo quando você subir os cartões
        else:
            st.warning("⚠️ Aguardando as planilhas de cartão para realizar a soma e o confronto.")
