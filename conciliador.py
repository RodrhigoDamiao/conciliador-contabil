import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="Conciliador Contábil Pro", layout="wide")

def clean_money(val):
    if pd.isna(val) or str(val).lower() == 'nan': return 0.0
    s = str(val).replace('R$', '').replace('\xa0', '').replace(' ', '').strip()
    if ',' in s and '.' in s:
        if s.find('.') < s.find(','): s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

st.title("🏦 Sistema de Conciliação Unificado")
st.markdown("Selecione os arquivos e defina a operadora para cada um.")

uploaded_files = st.file_uploader("Upload de Arquivos (CSV, XLS, XLSX)", accept_multiple_files=True)

if uploaded_files:
    consolidado = []
    st.subheader("⚙️ Configuração por Arquivo")
    
    for f in uploaded_files:
        with st.container():
            col_nome, col_op = st.columns([2, 1])
            col_nome.write(f"📄 {f.name}")
            
            # LISTA ATUALIZADA COM ALELO E TODAS AS OUTRAS
            op_selecionada = col_op.selectbox(
                "Defina a Operadora:",
                ["Selecionar...", "Alelo", "Cabal", "Caixa Pagamentos", "Cielo", "Mercado Pago", "PagBank", "Pagar.me", "Pluxee", "Rede", "Sipag", "Ticket", "VR Benefícios"],
                key=f.name
            )
            
            if op_selecionada != "Selecionar...":
                try:
                    # Leitura flexível
                    if f.name.upper().endswith('.CSV'):
                        try: df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
                        except: df = pd.read_csv(f, sep=',', encoding='utf-8-sig')
                    else:
                        df = pd.read_excel(f)

                    res = pd.DataFrame()

                    # --- LÓGICA ALELO ---
                    if op_selecionada == "Alelo":
                        # Alelo costuma usar colunas como 'Data da Transação' e 'Valor Bruto'
                        df = df.dropna(subset=[df.columns[0]]) # Limpa linhas vazias
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df.iloc[:, 0], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Alelo',
                            'Valor_Bruto': df.iloc[:, 3].apply(clean_money), # Geralmente coluna 4
                            'Despesas': 0.0,
                            'Descricao': 'Venda Alelo'
                        })

                    # --- LÓGICA CAIXA ---
                    elif op_selecionada == "Caixa Pagamentos":
                        df_c = df[df['Status'] == 'Aprovada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_c['Data da venda'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Caixa',
                            'Valor_Bruto': df_c['Valor bruto da parcela'].apply(clean_money),
                            'Despesas': df_c['Valor da taxa (MDR)'].apply(clean_money),
                            'Descricao': 'Venda Caixa'
                        })

                    # --- LÓGICA CIELO ---
                    elif op_selecionada == "Cielo":
                        # Se for Excel da Cielo, pula as 11 linhas de cabeçalho
                        df_cie = df.copy()
                        if len(df_cie) > 11:
                            df_cie = df_cie.iloc[11:].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_cie.iloc[:, 0], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Cielo',
                            'Valor_Bruto': df_cie.iloc[:, 7].apply(clean_money),
                            'Despesas': df_cie.iloc[:, 8].apply(clean_money).abs(),
                            'Descricao': 'Venda Cielo'
                        })

                    # --- LÓGICA MERCADO PAGO ---
                    elif op_selecionada == "Mercado Pago":
                        df_mp = df[df['Status da operação (status)'] == 'approved'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_mp['Data de creditação (date_approved)'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Mercado Pago',
                            'Valor_Bruto': df_mp['Valor do produto (transaction_amount)'].apply(clean_money),
                            'Despesas': df_mp['Tarifa do Mercado Pago (mercadopago_fee)'].apply(clean_money),
                            'Descricao': 'Venda Mercado Pago'
                        })
                        # Adiciona linha de financiamento se houver
                        df_fin = df_mp[df_mp['Custos de parcelamento (financing_fee)'].apply(clean_money).abs() > 0].copy()
                        if not df_fin.empty:
                            fin_res = pd.DataFrame({
                                'Data': pd.to_datetime(df_fin['Data de creditação (date_approved)'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                                'Operadora': 'Mercado Pago', 'Valor_Bruto': 0.0,
                                'Despesas': df_fin['Custos de parcelamento (financing_fee)'].apply(clean_money).abs(),
                                'Descricao': 'Custo de parcelamento - Mercado Pago'
                            })
                            res = pd.concat([res, fin_res])

                    # --- LÓGICA REDE ---
                    elif op_selecionada == "Rede":
                        df_r = df[df['status da venda'] == 'aprovada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_r['data da venda']).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Rede',
                            'Valor_Bruto': df_r['valor da venda atualizado'].apply(clean_money),
                            'Despesas': df_r['valor total das taxas descontadas (MDR+recebimento automático)'].apply(clean_money),
                            'Descricao': 'Venda Rede'
                        })

                    # --- LÓGICA PAGARME ---
                    elif op_selecionada == "Pagar.me":
                        df_pm = df[df['Status'] == 'Pago'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_pm['Data']).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Pagar.me',
                            'Valor_Bruto': df_pm['Valor Capturado (R$)'].apply(clean_money),
                            'Despesas': df_pm['Custo da Transação'].apply(clean_money),
                            'Descricao': 'Venda Pagar.me'
                        })

                    if not res.empty:
                        consolidado.append(res)

                except Exception as e:
                    st.error(f"Erro ao processar {f.name}: Verifique se o arquivo corresponde à operadora selecionada.")

    if consolidado:
        st.divider()
        df_final = pd.concat(consolidado, ignore_index=True)
        df_final['Valor_Liquido'] = df_final['Valor_Bruto'] - df_final['Despesas']
        
        st.success(f"✅ Sucesso! {len(df_final)} registros processados.")
        st.dataframe(df_final)
        
        csv = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 BAIXAR CONSOLIDADO FINAL", data=csv, file_name="CONSOLIDADO_ESCRITORIO.csv", mime="text/csv")
