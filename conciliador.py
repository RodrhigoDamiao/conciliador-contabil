import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Conciliador Contábil Pro", layout="wide")

# Função de limpeza financeira que definimos
def clean_money(val):
    if pd.isna(val): return 0.0
    s = str(val).replace('R$', '').replace(' ', '').strip()
    if ',' in s and '.' in s:
        if s.find('.') < s.find(','): s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

st.title("🏦 Sistema de Conciliação por Operadora")
st.markdown("1. Suba os arquivos | 2. Selecione a Operadora | 3. Baixe o Consolidado")

# Área de Upload
uploaded_files = st.file_uploader("Arraste todos os arquivos (CSV, XLS, XLSX)", accept_multiple_files=True)

if uploaded_files:
    consolidado = []
    st.subheader("Configuração de Arquivos")
    
    # Criamos colunas para a interface ficar organizada
    col1, col2 = st.columns([2, 1])
    
    for f in uploaded_files:
        with st.container():
            c1, c2 = st.columns([2, 1])
            c1.write(f"📄 {f.name}")
            # O usuário escolhe quem é a operadora deste arquivo
            operadora = c2.selectbox(
                "Qual é a operadora?",
                ["Selecionar...", "Caixa", "Mercado Pago", "Cielo", "Rede", "PagBank", "Pagar.me", "Sipag", "Cabal", "Ticket", "Pluxee", "VR"],
                key=f.name
            )
            
            if operadora != "Selecionar...":
                try:
                    # Leitura flexível
                    if f.name.upper().endswith('.CSV'):
                        try: df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
                        except: df = pd.read_csv(f, sep=',', encoding='utf-8-sig')
                    else:
                        df = pd.read_excel(f)

                    # --- PROCESSAMENTO POR OPERADORA ---
                    if operadora == "Caixa":
                        df_c = df[df['Status'] == 'Aprovada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_c['Data da venda'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Caixa',
                            'Valor_Bruto': df_c['Valor bruto da parcela'].apply(clean_money),
                            'Despesas': df_c['Valor da taxa (MDR)'].apply(clean_money),
                            'Descricao': 'Venda Caixa'
                        })
                        consolidado.append(res)

                    elif operadora == "Mercado Pago":
                        df_mp = df[df['Status da operação (status)'] == 'approved'].copy()
                        # Venda e Tarifa Base
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_mp['Data de creditação (date_approved)'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Mercado Pago',
                            'Valor_Bruto': df_mp['Valor do produto (transaction_amount)'].apply(clean_money),
                            'Despesas': df_mp['Tarifa do Mercado Pago (mercadopago_fee)'].apply(clean_money),
                            'Descricao': 'Venda Mercado Pago'
                        })
                        consolidado.append(res)
                        # Linha de Financiamento extra
                        df_fin = df_mp[df_mp['Custos de parcelamento (financing_fee)'].apply(clean_money).abs() > 0].copy()
                        if not df_fin.empty:
                            finan = pd.DataFrame({
                                'Data': pd.to_datetime(df_fin['Data de creditação (date_approved)'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                                'Operadora': 'Mercado Pago', 'Valor_Bruto': 0.0,
                                'Despesas': df_fin['Custos de parcelamento (financing_fee)'].apply(clean_money).abs(),
                                'Descricao': 'Custo de parcelamento - Mercado Pago'
                            })
                            consolidado.append(finan)

                    elif operadora == "Pagar.me":
                        df_pm = df[df['Status'] == 'Pago'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_pm['Data']).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Pagar.me',
                            'Valor_Bruto': df_pm['Valor Capturado (R$)'].apply(clean_money),
                            'Despesas': df_pm['Custo da Transação'].apply(clean_money),
                            'Descricao': 'Venda Pagar.me'
                        })
                        consolidado.append(res)

                    # [Adicionar os demais ELIF para as outras operadoras conforme mapeado...]

                except Exception as e:
                    st.error(f"Erro no arquivo {f.name}: Verifique se o formato interno corresponde à operadora selecionada.")

    if consolidado:
        st.divider()
        df_final = pd.concat(consolidado, ignore_index=True)
        st.success("✅ Processamento finalizado com sucesso!")
        st.dataframe(df_final)
        
        csv = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 BAIXAR CONSOLIDADO PARA O ERP",
            data=csv,
            file_name="CONSOLIDADO_ESCRITORIO.csv",
            mime="text/csv"
        )
