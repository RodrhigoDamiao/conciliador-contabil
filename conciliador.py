import streamlit as st
import pandas as pd
import io

# Título da Página no Navegador
st.set_page_config(page_title="Conciliador Escritório", layout="wide")

st.title("🏦 Sistema de Conciliação Contábil")
st.info("Arraste os ficheiros das operadoras para processar o consolidado.")

# Função padrão para tratar valores financeiros brasileiros
def clean_money(val):
    if pd.isna(val): return 0.0
    s = str(val).replace('R$', '').replace(' ', '').strip()
    if ',' in s and '.' in s:
        if s.find('.') < s.find(','): s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

# Área de Upload
files = st.file_uploader("Upload de Ficheiros (CSV)", accept_multiple_files=True)

if files:
    lista_final = []
    for f in files:
        nome = f.name.upper()
        # Exemplo simplificado para teste (CAIXA)
        if "CAIXA" in nome:
            df = pd.read_csv(f)
            # Regra: Apenas Aprovadas
            df = df[df['Status'] == 'Aprovada']
            temp = pd.DataFrame({
                'Data': df['Data da venda'],
                'Operadora': 'Caixa',
                'Bruto': df['Valor bruto da parcela'].apply(clean_money),
                'Descricao': 'Venda Caixa'
            })
            lista_final.append(temp)
    
    if lista_final:
        df_consolidado = pd.concat(lista_final)
        st.success("Processamento concluído!")
        st.dataframe(df_consolidado)
        
        # Botão de Download
        csv = df_consolidado.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 Descarregar Consolidado", data=csv, file_name="resultado.csv")
