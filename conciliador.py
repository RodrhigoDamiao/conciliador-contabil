import streamlit as st
import pandas as pd

def process_reconciliation(df_cartoes, df_razao, col_valor_cartao, col_data):
    # 1. Agrupar vendas de cartão por dia
    vendas_diarias = df_cartoes.groupby(col_data)[col_valor_cartao].sum().reset_index()
    
    # 2. Cruzar com o Livro Razão (considerando que o razão também esteja por data)
    # Supondo que o Razão tenha uma coluna 'Valor' e 'Data'
    df_final = pd.merge(vendas_diarias, df_razao, on=col_data, how='outer').fillna(0)
    
    # 3. Lógica de Subtração: Razão - Vendas Cartão
    df_final['Diferença'] = df_final['Valor_Razao'] - df_final[col_valor_cartao]
    
    return df_final

def main():
    st.set_page_config(page_title="Reconciliador Contábil", layout="wide")
    st.title("🚀 Sistema de Reconciliação Cartão vs. Razão")

    st.sidebar.header("Upload de Arquivos")
    file_cartao = st.sidebar.file_uploader("Planilha de Vendas Cartão (Excel/CSV)", type=['xlsx', 'csv'])
    file_razao = st.sidebar.file_uploader("Planilha Livro Razão (Excel/CSV)", type=['xlsx', 'csv'])

    if file_cartao and file_razao:
        # Carregamento dos dados
        df_c = pd.read_excel(file_cartao) if file_cartao.name.endswith('xlsx') else pd.read_csv(file_cartao)
        df_r = pd.read_excel(file_razao) if file_razao.name.endswith('xlsx') else pd.read_csv(file_razao)

        st.subheader("Prévia dos Dados")
        col1, col2 = st.columns(2)
        col1.write("Vendas Cartão", df_c.head())
        col2.write("Livro Razão", df_r.head())

        if st.button("Executar Reconciliação"):
            # Aqui entrará a chamada da função de processamento
            st.success("Processamento concluído!")
            # Exibição do resultado e botão de download
            
    else:
        st.info("Aguardando o upload das duas planilhas para iniciar.")

if __name__ == "__main__":
    main()
