import streamlit as st
import pandas as pd
import numpy as np
from fpdf import FPDF
from datetime import datetime
from io import BytesIO

# --- CONFIGURAÇÃO DE APARÊNCIA (UI/UX) ---
st.set_page_config(page_title="Auditor Contábil Pro", layout="wide", page_icon="📊")

# CSS para deixar o sistema com aspecto "Light & Professional"
st.markdown("""
    <style>
    .main { background-color: #F8F9FA; }
    .stButton>button { 
        background-color: #6C757D; color: white; border-radius: 5px; border: none;
        padding: 10px 24px; transition: 0.3s;
    }
    .stButton>button:hover { background-color: #495057; color: white; }
    .reportview-container .main .block-container { padding-top: 2rem; }
    h1, h2, h3 { color: #343A40; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .stMetric { background-color: #FFFFFF; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_index=True)

# --- CONSTANTES E MAPEAMENTOS ---
SINONIMOS_DATA = ['DATA', 'DATA DA VENDA', 'DT. VENDA', 'DATA TRANSAÇÃO', 'DATA MOVIMENTO', 'PERÍODO', 'VENCIMENTO', 'DATA PAGAMENTO']
SINONIMOS_BRUTO = ['VALOR', 'VALOR BRUTO', 'VLR BRUTO', 'VALOR TOTAL', 'VALOR VENDA', 'VALOR TRANSACIONADO', 'BRUTO']
SINONIMOS_LIQUIDO = ['VALOR LIQUIDO', 'VLR LIQUIDO', 'VALOR LÍQUIDO', 'LÍQUIDO', 'RECEBIDO', 'VALOR PAGAMENTO']

# --- FUNÇÕES CORE ---

def carregar_excel(file):
    try:
        if file.name.endswith('.xlsb'): return pd.read_excel(file, engine='pyxlsb')
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"Erro no arquivo {file.name}: {e}")
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
        self.set_text_color(52, 58, 64)
        self.cell(0, 10, 'RELATÓRIO DE AUDITORIA E CONCILIAÇÃO', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def gerar_pdf_analitico(df_final, resumo_maquinas, titulo_relatorio):
    pdf = PDF()
    pdf.add_page()
    
    # 1. Resumo Executivo
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '1. RESUMO EXECUTIVO (MENSAL)', ln=True)
    pdf.set_font('Arial', '', 10)
    pdf.cell(60, 8, f"Total Livro Razão:", 0)
    pdf.cell(40, 8, f"R$ {df_final['RAZAO_BRUTO'].sum():,.2f}", ln=True)
    pdf.cell(60, 8, f"Total Identificado (Cartões/Outros):", 0)
    pdf.cell(40, 8, f"R$ {df_final['CARTAO_TOTAL_BRUTO'].sum():,.2f}", ln=True)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(60, 8, f"Total Caixa (Espécie):", 0)
    pdf.cell(40, 8, f"R$ {df_final['DIFERENÇA_CAIXA'].sum():,.2f}", ln=True)
    pdf.ln(5)

    # 2. Detalhamento por Máquina/Operação
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '2. DESEMPENHO E TAXAS POR OPERADORA', ln=True)
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(50, 8, 'Operação', 1); pdf.cell(40, 8, 'Venda Bruta', 1); pdf.cell(40, 8, 'Despesa (Taxas)', 1); pdf.cell(30, 8, '% Taxa', 1); pdf.ln()
    
    pdf.set_font('Arial', '', 9)
    for maq, dados in resumo_maquinas.items():
        taxa_perc = (dados['despesa'] / dados['bruto'] * 100) if dados['bruto'] > 0 else 0
        pdf.cell(50, 8, str(maq)[:25], 1)
        pdf.cell(40, 8, f"R$ {dados['bruto']:,.2f}", 1)
        pdf.cell(40, 8, f"R$ {dados['despesa']:,.2f}", 1)
        pdf.cell(30, 8, f"{taxa_perc:.2f}%", 1); pdf.ln()
    pdf.ln(5)

    # 3. Rodapé Analítico (Dia a Dia)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '3. CONFERÊNCIA DIÁRIA', ln=True)
    pdf.set_font('Arial', 'B', 8)
    pdf.cell(25, 8, 'Data', 1); pdf.cell(40, 8, 'Razão', 1); pdf.cell(40, 8, 'Cartão (Total)', 1); pdf.cell(40, 8, 'Sobra Caixa', 1); pdf.ln()
    
    pdf.set_font('Arial', '', 8)
    for _, row in df_final.iterrows():
        pdf.cell(25, 8, str(row['DATA']), 1)
        pdf.cell(40, 8, f"{row['RAZAO_BRUTO']:,.2f}", 1)
        pdf.cell(40, 8, f"{row['CARTAO_TOTAL_BRUTO']:,.2f}", 1)
        pdf.cell(40, 8, f"{row['DIFERENÇA_CAIXA']:,.2f}", 1); pdf.ln()

    return pdf.output()

# --- INTERFACE ---
st.title("⚖️ Auditoria Contábil Inteligente")
st.subheader("Conciliação de Receitas, Despesas e Ajuste de Competência")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2654/2654254.png", width=80)
    st.header("Configurações")
    estrategia = st.selectbox("Estratégia de Ajuste", ["Sem Ajuste", "Dia Seguinte (Cascata)", "Dia Anterior", "Média Mensal / Global"])
    
    st.divider()
    file_razao = st.file_uploader("📘 Livro Razão", type=['xlsx','xls','xlsb','xlsm'])
    files_cartao = st.file_uploader("💳 Planilhas de Cartão/Vouchers", type=['xlsx','xls','xlsb','xlsm'], accept_multiple_files=True)
    file_universal = st.file_uploader("🌐 Planilha Universal (PIX/Novos)", type=['xlsx','xls','csv'])

if file_razao and files_cartao:
    # 1. Processar Razão
    df_r_raw = carregar_excel(file_razao)
    c_data_r = localizar_coluna(df_r_raw, ['DATA'])
    c_debito_r = localizar_coluna(df_r_raw, ['DÉBITO', 'DEBITO', 'VALOR'])
    
    df_r_raw['DATA'] = pd.to_datetime(df_r_raw[c_data_r]).dt.date
    df_r_diario = df_r_raw.groupby('DATA')[c_debito_r].sum().reset_index()
    df_r_diario.columns = ['DATA', 'RAZAO_BRUTO']

    # 2. Processar Cartões e Vouchers
    lista_despesas_erp = []
    resumo_maquinas = {}
    lista_dfs_c = []

    all_files = list(files_cartao)
    if file_universal: all_files.append(file_universal)

    for f in all_files:
        df_tmp = carregar_excel(f)
        if df_tmp is not None:
            c_data = localizar_coluna(df_tmp, SINONIMOS_DATA)
            c_bruto = localizar_coluna(df_tmp, SINONIMOS_BRUTO)
            c_liquido = localizar_coluna(df_tmp, SINONIMOS_LIQUIDO)
            
            if c_data and c_bruto:
                nome_maq = f.name.split('.')[0].upper()
                df_tmp['DATA_LIMPA'] = pd.to_datetime(df_tmp[c_data]).dt.date
                
                # Cálculo de despesa
                if c_liquido:
                    df_tmp['DESPESA'] = df_tmp[c_bruto] - df_tmp[c_liquido]
                else:
                    df_tmp['DESPESA'] = 0.0

                # Acumular para Relatórios
                resumo_maquinas[nome_maq] = {
                    'bruto': df_tmp[c_bruto].sum(),
                    'despesa': df_tmp['DESPESA'].sum()
                }

                # Preparar para Lançamentos ERP
                for _, r in df_tmp.iterrows():
                    if r['DESPESA'] > 0:
                        lista_despesas_erp.append({'data': r['DATA_LIMPA'], 'valor': r['DESPESA'], 'origem': nome_maq})

                lista_dfs_c.append(df_tmp[['DATA_LIMPA', c_bruto]].rename(columns={'DATA_LIMPA': 'DATA', c_bruto: 'VALOR'}))

    # 3. Consolidação Final
    df_c_total = pd.concat(lista_dfs_c).groupby('DATA')['VALOR'].sum().reset_index()
    df_c_total.columns = ['DATA', 'CARTAO_TOTAL_BRUTO']
    
    df_final = pd.merge(df_r_diario, df_c_total, on='DATA', how='outer').fillna(0)
    
    # Aplicar Ajustes
    if estrategia != "Média Mensal / Global":
        df_final['CARTAO_AJUSTADO'] = aplicar_redistribuicao(df_final, estrategia)
    else:
        df_final['CARTAO_AJUSTADO'] = df_final['CARTAO_TOTAL_BRUTO'] # Lógica simplificada

    df_final['DIFERENÇA_CAIXA'] = df_final['RAZAO_BRUTO'] - df_final['CARTAO_AJUSTADO']

    # 4. DASHBOARD DE RESULTADOS
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Faturamento Razão", f"R$ {df_final['RAZAO_BRUTO'].sum():,.2f}")
    m2.metric("Total Cartão/PIX", f"R$ {df_final['CARTAO_TOTAL_BRUTO'].sum():,.2f}")
    m3.metric("Sobra de Caixa", f"R$ {df_final['DIFERENÇA_CAIXA'].sum():,.2f}", delta_color="normal")
    m4.metric("Total Despesas", f"R$ {sum(d['despesa'] for d in resumo_maquinas.values()):,.2f}", delta_color="inverse")

    st.markdown("### Visualização dos Dados")
    st.dataframe(df_final.style.format(precision=2), use_container_width=True)

    # 5. BOTÕES DE EXPORTAÇÃO (PDF & ERP)
    st.divider()
    c1, c2, c3 = st.columns(3)
    
    with c1:
        pdf_bytes = gerar_pdf_analitico(df_final, resumo_maquinas, "Auditoria")
        st.download_button("📄 Baixar PDF de Auditoria", data=pdf_bytes, file_name="auditoria_contabil.pdf", use_container_width=True)
    
    with c2:
        # Gerar CSV ERP
        rows_erp = []
        # Lançamentos de Caixa
        for _, r in df_final.iterrows():
            if r['DIFERENÇA_CAIXA'] > 0.01:
                rows_erp.append([None, 35, 1071, r['DATA'], round(r['DIFERENÇA_CAIXA'], 2), 31, "", "", "", "", ""])
        # Lançamentos de Despesa
        for d in lista_despesas_erp:
            rows_erp.append([None, 7014, 1071, d['data'], round(d['valor'], 2), 201, d['origem'], "", "", "", ""])
        
        df_erp = pd.DataFrame(rows_erp, columns=["Lanc. Automatico", "DEBITO", "CREDITO", "Data Mov.", "VALOR", "CODIGO HISTORICO", "COMPL. HISTORICO", "CCDEBITO", "CCCREDITO", "Nr. Doc.", "COMPLEMENTO"])
        csv_erp = df_erp.to_csv(index=False).encode('utf-8-sig')
        st.download_button("💾 Baixar Arquivo Importação ERP", data=csv_erp, file_name="importar_erp.csv", use_container_width=True)

    with c3:
        st.info("💡 Dica: Verifique os dias negativos no PDF para alertar o cliente.")

else:
    st.warning("Aguardando upload do Livro Razão e ao menos uma planilha de Cartão para iniciar.")
