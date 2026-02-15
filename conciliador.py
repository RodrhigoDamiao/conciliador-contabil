import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime
from io import BytesIO

# --- CONFIGURAÇÃO DE APARÊNCIA (UI/UX) ---
st.set_page_config(page_title="Auditor Contábil Pro", layout="wide", page_icon="📊")

# Estilo corrigido para evitar erro de sintaxe no Python 3.13
st.markdown("""
<style>
    .main { background-color: #F8F9FA; }
    .stMetric { background-color: #FFFFFF; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    h1, h2, h3 { color: #343A40; }
</style>
""", unsafe_allow_index=True)

# --- CONSTANTES E SINÔNIMOS ---
SINONIMOS_DATA = ['DATA', 'DATA DA VENDA', 'DT. VENDA', 'DATA TRANSAÇÃO', 'DATA MOVIMENTO', 'PERÍODO', 'VENCIMENTO', 'DATA PAGAMENTO']
SINONIMOS_BRUTO = ['VALOR', 'VALOR BRUTO', 'VLR BRUTO', 'VALOR TOTAL', 'VALOR VENDA', 'VALOR TRANSACIONADO', 'BRUTO', 'DÉBITO', 'DEBITO']
SINONIMOS_LIQUIDO = ['VALOR LIQUIDO', 'VLR LIQUIDO', 'VALOR LÍQUIDO', 'LÍQUIDO', 'RECEBIDO', 'VALOR PAGAMENTO']

# --- FUNÇÕES DE PROCESSAMENTO ---

def carregar_excel_inteligente(file):
    """Lê o arquivo e localiza a linha onde o cabeçalho real começa."""
    try:
        # Carrega inicialmente para procurar a linha do cabeçalho
        extensao = file.name.split('.')[-1].lower()
        if extensao == 'xlsb':
            df_raw = pd.read_excel(file, engine='pyxlsb', header=None)
        else:
            df_raw = pd.read_excel(file, header=None)
        
        # Varre as primeiras 20 linhas para achar as colunas DATA e DÉBITO/HISTÓRICO
        for i, row in df_raw.iterrows():
            vals = [str(v).strip().upper() for v in row.values]
            if 'DATA' in vals and ('DÉBITO' in vals or 'DEBITO' in vals or 'HISTÓRICO' in vals or 'VALOR' in vals):
                df_raw.columns = df_raw.iloc[i]
                df_final = df_raw.iloc[i+1:].reset_index(drop=True)
                # Limpa colunas sem nome (NaN)
                df_final = df_final.loc[:, df_final.columns.notna()]
                return df_final
        return df_raw
    except Exception as e:
        st.error(f"Erro ao processar {file.name}: {e}")
        return None

def localizar_coluna(df, sinonimos):
    cols_reais = {str(c).strip().upper(): c for c in df.columns}
    for s in sinonimos:
        if s in cols_reais: return cols_reais[s]
    return None

def aplicar_redistribuicao(df, estrategia):
    df = df.sort_values('DATA').copy()
    cartao = df['CARTAO_TOTAL_BRUTO'].values.astype(float)
    razao = df['RAZAO_BRUTO'].values.astype(float)
    
    if estrategia == "Dia Seguinte (Cascata)":
        for i in range(len(cartao) - 1):
            if cartao[i] > razao[i]:
                excesso = cartao[i] - razao[i]
                cartao[i] = razao[i]
                cartao[i+1] += excesso
    elif estrategia == "Dia Anterior":
        for i in range(len(cartao) - 1, 0, -1):
            if cartao[i] > razao[i]:
                excesso = cartao[i] - razao[i]
                cartao[i] = razao[i]
                cartao[i-1] += excesso
    return cartao

# --- GERADOR DE PDF ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'RELATÓRIO DE AUDITORIA CONTÁBIL', 0, 1, 'C')
        self.ln(5)

def gerar_pdf_analitico(df_final, resumo_maquinas):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '1. RESUMO MENSAL', ln=True)
    pdf.set_font('Arial', '', 10)
    pdf.cell(60, 8, f"Total Razão: R$ {df_final['RAZAO_BRUTO'].sum():,.2f}", ln=True)
    pdf.cell(60, 8, f"Total Cartão/Outros: R$ {df_final['CARTAO_TOTAL_BRUTO'].sum():,.2f}", ln=True)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(60, 8, f"Sobra Caixa (Espécie): R$ {df_final['DIFERENÇA_CAIXA'].sum():,.2f}", ln=True)
    pdf.ln(10)
    
    pdf.cell(0, 10, '2. DETALHAMENTO POR OPERADORA', ln=True)
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(60, 8, 'Máquina', 1); pdf.cell(40, 8, 'Bruto', 1); pdf.cell(40, 8, 'Despesa', 1); pdf.cell(30, 8, '% Taxa', 1); pdf.ln()
    pdf.set_font('Arial', '', 9)
    for maq, dados in resumo_maquinas.items():
        taxa = (dados['despesa']/dados['bruto']*100) if dados['bruto'] > 0 else 0
        pdf.cell(60, 8, str(maq)[:30], 1)
        pdf.cell(40, 8, f"{dados['bruto']:,.2f}", 1)
        pdf.cell(40, 8, f"{dados['despesa']:,.2f}", 1)
        pdf.cell(30, 8, f"{taxa:.2f}%", 1); pdf.ln()
    
    return pdf.output()

# --- INTERFACE ---
st.title("⚖️ Auditoria Contábil Inteligente")

with st.sidebar:
    st.header("Upload de Arquivos")
    estrategia = st.selectbox("Ajuste de Saldo", ["Sem Ajuste", "Dia Seguinte (Cascata)", "Dia Anterior", "Média Mensal"])
    file_razao = st.file_uploader("📘 Livro Razão", type=['xlsx','xls','xlsb','xlsm'])
    files_cartao = st.file_uploader("💳 Planilhas de Cartão (Múltiplas)", type=['xlsx','xls','xlsb','xlsm'], accept_multiple_files=True)
    file_universal = st.file_uploader("🌐 Planilha Universal / PIX", type=['xlsx','xls','csv'])

if file_razao:
    df_r_raw = carregar_excel_inteligente(file_razao)
    if df_r_raw is not None:
        c_data_r = localizar_coluna(df_r_raw, ['DATA'])
        c_debito_r = localizar_coluna(df_r_raw, ['DÉBITO', 'DEBITO', 'VALOR'])
        
        if c_data_r and c_debito_r:
            df_r_raw['DATA'] = pd.to_datetime(df_r_raw[c_data_r], errors='coerce').dt.date
            df_r_diario = df_r_raw.groupby('DATA')[c_debito_r].sum().reset_index()
            df_r_diario.columns = ['DATA', 'RAZAO_BRUTO']
            st.success("✅ Livro Razão pronto.")

            if files_cartao or file_universal:
                lista_dfs_c = []
                resumo_maquinas = {}
                lista_despesas_erp = []

                all_files = list(files_cartao)
                if file_universal: all_files.append(file_universal)

                for f in all_files:
                    df_tmp = carregar_excel_inteligente(f)
                    if df_tmp is not None:
                        c_data = localizar_coluna(df_tmp, SINONIMOS_DATA)
                        c_bruto = localizar_coluna(df_tmp, SINONIMOS_BRUTO)
                        c_liq = localizar_coluna(df_tmp, SINONIMOS_LIQUIDO)
                        
                        if c_data and c_bruto:
                            nome = f.name.split('.')[0].upper()
                            df_tmp['DATA_LIMPA'] = pd.to_datetime(df_tmp[c_data], errors='coerce').dt.date
                            df_tmp['DESPESA'] = (df_tmp[c_bruto] - df_tmp[c_liq]) if c_liq else 0.0
                            
                            resumo_maquinas[nome] = {'bruto': df_tmp[c_bruto].sum(), 'despesa': df_tmp['DESPESA'].sum()}
                            
                            for _, r in df_tmp.iterrows():
                                if r['DESPESA'] > 0:
                                    lista_despesas_erp.append({'data': r['DATA_LIMPA'], 'valor': r['DESPESA'], 'origem': nome})
                            
                            lista_dfs_c.append(df_tmp[['DATA_LIMPA', c_bruto]].rename(columns={'DATA_LIMPA': 'DATA', c_bruto: 'VALOR'}))

                if lista_dfs_c:
                    df_c_total = pd.concat(lista_dfs_c).groupby('DATA')['VALOR'].sum().reset_index()
                    df_c_total.columns = ['DATA', 'CARTAO_TOTAL_BRUTO']
                    
                    df_final = pd.merge(df_r_diario, df_c_total, on='DATA', how='outer').fillna(0)
                    
                    if estrategia != "Média Mensal":
                        df_final['CARTAO_AJUSTADO'] = aplicar_redistribuicao(df_final, estrategia)
                    else:
                        df_final['CARTAO_AJUSTADO'] = df_final['CARTAO_TOTAL_BRUTO']

                    df_final['DIFERENÇA_CAIXA'] = df_final['RAZAO_BRUTO'] - df_final['CARTAO_AJUSTADO']
                    
                    # Dashboard
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Razão", f"R$ {df_final['RAZAO_BRUTO'].sum():,.2f}")
                    col2.metric("Total Cartão", f"R$ {df_final['CARTAO_TOTAL_BRUTO'].sum():,.2f}")
                    col3.metric("Sobra Caixa", f"R$ {df_final['DIFERENÇA_CAIXA'].sum():,.2f}")
                    
                    st.dataframe(df_final, use_container_width=True)

                    # Botões
                    btn1, btn2 = st.columns(2)
                    with btn1:
                        pdf_data = gerar_pdf_analitico(df_final, resumo_maquinas)
                        st.download_button("📄 Baixar PDF Auditoria", data=pdf_data, file_name="auditoria.pdf")
                    with btn2:
                        st.info("Arquivo ERP pronto para exportação.")
        else:
            st.warning("Aguardando as planilhas de cartões...")
