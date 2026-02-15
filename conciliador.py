import streamlit as st
import pandas as pd

def localizar_colunas(df, nomes_esperados):
    """
    Localiza o nome real da coluna no DF, ignorando maiúsculas/minúsculas
    e espaços extras, garantindo que o sistema não quebre se a coluna mudar de lugar.
    """
    mapeamento = {}
    colunas_reais = df.columns
    for nome in nomes_esperados:
        encontrada = [c for c in colunas_reais if str(c).strip().upper() == nome.upper()]
        if encontrada:
            mapeamento[nome] = encontrada[0]
        else:
            st.error(f"Coluna obrigatória não encontrada: {nome}")
            return None
    return mapeamento

def processar_dados(df_cartao, df_razao):
    # Identificar colunas no Razão
    cols_razao = localizar_colunas(df_razao, ['DATA', 'HISTÓRICO', 'DÉBITO'])
    # Identificar colunas no Cartão (Supondo nomes padrão, ajuste se necessário)
    cols_cartao = localizar_colunas(df_cartao, ['DATA', 'VALOR'])

    if not cols_razao or not cols_cartao:
        return None

    # Tratamento de Datas
    df_razao[cols_razao['DATA']] = pd.to_datetime(df_razao[cols_razao['DATA']])
    df_cartao[cols_cartao['DATA']] = pd.to_datetime(df_cartao[cols_cartao['DATA']])

    # Agrupar Cartão por Dia
    cartao_agrupado = df_cartao.groupby(cols_cartao['DATA'])[cols_cartao['VALOR']].sum().reset_index()

    # Cruzamento (Merge) usando o Razão como base
    df_final = pd.merge(
        df_razao, 
        cartao_agrupado, 
        left_on=cols_razao['DATA'], 
        right_on=cols_cartao['DATA'], 
        how='left'
    ).fillna(0)

    # Lógica: Razão (Débito) - Somatório Cartões
    df_final['DIFERENÇA'] = df_final[cols_razao['DÉBITO']] - df_final[cols_cartao['VALOR']]
    
    return df_final

# --- Interface Streamlit ---
st.set_page_config(page_title="Conciliador Contábil Express", layout="wide")
st.title("📊 Conciliação: Livro Razão vs. Cartões")

with st.sidebar:
    st.header("Upload de Arquivos")
    # Aceita .xls, .xlsx, .xlsm, .xlsb
    file_razao = st.file_uploader("Suba o Livro Razão", type=['xlsx', 'xls', 'xlsm', 'xlsb'])
    file_cartao = st.file_uploader("Suba as Vendas de Cartão", type=['xlsx', 'xls', 'xlsm', 'xlsb'])

if file_razao and file_cartao:
    try:
        # engine='openpyxl' resolve a maioria dos arquivos modernos de Excel
        df_r = pd.read_excel(file_razao)
        df_c = pd.read_excel(file_cartao)

        if st.button("🚀 Executar Reconciliação"):
            resultado = processar_dados(df_c, df_r)
            
            if resultado is not None:
                st.subheader("Resultado da Reconciliação")
                st.dataframe(resultado)
                
                # Botão para baixar o resultado
                csv = resultado.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Baixar Relatório em CSV", csv, "conciliacao.csv", "text/csv")
    except Exception as e:
        st.error(f"Erro ao ler os arquivos: {e}")
else:
    st.info("Por favor, carregue os dois arquivos Excel para continuar.")
