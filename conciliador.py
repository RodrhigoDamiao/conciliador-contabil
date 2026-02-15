import streamlit as st
import pandas as pd
import numpy as np
import io

# Configuração da Página
st.set_page_config(page_title="Conciliador Contábil", layout="wide")

def clean_money(val):
    if pd.isna(val) or str(val).lower() == 'nan': return 0.0
    s = str(val).replace('R$', '').replace('\xa0', '').replace(' ', '').strip()
    if ',' in s and '.' in s:
        if s.find('.') < s.find(','): s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

st.title("🚀 Sistema de Conciliação - Escritório")
st.markdown("Selecione ou arraste as planilhas das operadoras abaixo.")

# Upload de múltiplos arquivos
uploaded_files = st.file_uploader("Arraste os arquivos .csv ou .xlsx aqui", accept_multiple_files=True)

if uploaded_files:
    consolidado = []
    
    for file in uploaded_files:
        nome = file.name.upper()
        # Leitura binária para funcionar no navegador
        content = file.read()
        
        # Exemplo de lógica para CAIXA (Adaptar para as outras 10 operadoras aqui)
        if "CAIXA" in nome:
            df = pd.read_csv(io.BytesIO(content))
            df = df[df['Status'] == 'Aprovada'].copy()
            res = pd.DataFrame({
                'Data': pd.to_datetime(df['Data da venda'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                'Operadora': 'Caixa',
                'Valor_Bruto': df['Valor bruto da parcela'].apply(clean_money),
                'Despesas': df['Valor da taxa (MDR)'].apply(clean_money),
                'Descricao': 'Venda Caixa'
            })
            consolidado.append(res)
            
        # (Repetir a lógica de identificação para Mercado Pago, Cielo, Rede, etc.)

    if consolidado:
        df_final = pd.concat(consolidado, ignore_index=True)
        st.success(f"Processado com sucesso! {len(df_final)} registros encontrados.")
        
        # Preview dos dados
        st.dataframe(df_final)

        # Botão para baixar o resultado
        csv = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 BAIXAR CONSOLIDADO PARA O ERP",
            data=csv,
            file_name="CONSOLIDADO_ESCRITORIO.csv",
            mime="text/csv",
        )
