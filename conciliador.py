import streamlit as st
import pandas as pd
import numpy as np
import io

# Configuração da Página
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
st.markdown("Arraste os arquivos e selecione a operadora correspondente para processar.")

uploaded_files = st.file_uploader("Upload de Arquivos (CSV, XLS, XLSX)", accept_multiple_files=True)

if uploaded_files:
    consolidado = []
    st.subheader("⚙️ Configuração por Arquivo")
    
    for f in uploaded_files:
        with st.container():
            col_nome, col_op = st.columns([2, 1])
            col_nome.write(f"📄 {f.name}")
            
            # LISTA COMPLETA DE OPERADORAS
            op_selecionada = col_op.selectbox(
                "Defina a Operadora:",
                ["Selecionar...", "Cabal", "Caixa Pagamentos", "Cielo", "Mercado Pago", "PagBank", "Pagar.me", "Pluxee", "Rede", "Sipag", "Ticket", "VR Benefícios"],
                key=f.name
            )
            
            if op_selecionada != "Selecionar...":
                try:
                    # Leitura flexível do formato
                    if f.name.upper().endswith('.CSV'):
                        try: df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
                        except: df = pd.read_csv(f, sep=',', encoding='utf-8-sig')
                    else:
                        df = pd.read_excel(f)

                    # --- LÓGICA POR OPERADORA ---
                    
                    if op_selecionada == "Caixa Pagamentos":
                        df_c = df[df['Status'] == 'Aprovada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_c['Data da venda'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Caixa', 'Valor_Bruto': df_c['Valor bruto da parcela'].apply(clean_money),
                            'Despesas': df_c['Valor da taxa (MDR)'].apply(clean_money), 'Descricao': 'Venda Caixa'
                        })
                        consolidado.append(res)

                    elif op_selecionada == "Cielo":
                        # Pula 11 linhas padrão do relatório detalhado
                        df_cie = pd.read_excel(f, skiprows=11) if not f.name.upper().endswith('.CSV') else pd.read_csv(f, skiprows=11)
                        df_cie = df_cie[df_cie.iloc[:, 10] == 'Aprovada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_cie.iloc[:, 0], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Cielo', 'Valor_Bruto': df_cie.iloc[:, 7].apply(clean_money),
                            'Despesas': df_cie.iloc[:, 8].apply(clean_money).abs(), 'Descricao': 'Venda Cielo'
                        })
                        consolidado.append(res)

                    elif op_selecionada == "Rede":
                        df_r = df[df['status da venda'] == 'aprovada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_r['data da venda']).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Rede', 'Valor_Bruto': df_r['valor da venda atualizado'].apply(clean_money),
                            'Despesas': df_r['valor total das taxas descontadas (MDR+recebimento automático)'].apply(clean_money), 'Descricao': 'Venda Rede'
                        })
                        consolidado.append(res)

                    elif op_selecionada == "Mercado Pago":
                        df_mp = df[df['Status da operação (status)'] == 'approved'].copy()
                        # Linha de Venda
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_mp['Data de creditação (date_approved)'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Mercado Pago', 'Valor_Bruto': df_mp['Valor do produto (transaction_amount)'].apply(clean_money),
                            'Despesas': df_mp['Tarifa do Mercado Pago (mercadopago_fee)'].apply(clean_money), 'Descricao': 'Venda Mercado Pago'
                        })
                        consolidado.append(res)
                        # Linha de Financiamento
                        df_fin = df_mp[df_mp['Custos de parcelamento (financing_fee)'].apply(clean_money).abs() > 0].copy()
                        if not df_fin.empty:
                            finan = pd.DataFrame({
                                'Data': pd.to_datetime(df_fin['Data de creditação (date_approved)'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                                'Operadora': 'Mercado Pago', 'Valor_Bruto': 0.0,
                                'Despesas': df_fin['Custos de parcelamento (financing_fee)'].apply(clean_money).abs(), 'Descricao': 'Custo de parcelamento - Mercado Pago'
                            })
                            consolidado.append(finan)

                    elif op_selecionada == "Pagar.me":
                        df_pm = df[df['Status'] == 'Pago'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_pm['Data']).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Pagar.me', 'Valor_Bruto': df_pm['Valor Capturado (R$)'].apply(clean_money),
                            'Despesas': df_pm['Custo da Transação'].apply(clean_money), 'Descricao': 'Venda Pagar.me'
                        })
                        consolidado.append(res)
                    
                    elif op_selecionada in ["Sipag", "Cabal"]:
                        df_s = df[df['Status'] == 'Transação Processada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_s['Data da transação'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': op_selecionada, 'Valor_Bruto': df_s['Valor parcela bruto'].apply(clean_money),
                            'Despesas': df_s['Desconto parcela'].apply(clean_money), 'Descricao': f'Venda {op_selecionada}'
                        })
                        consolidado.append(res)

                    elif op_selecionada == "PagBank":
                        df_pb = df[df['Status'] == 'Aprovada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_pb['Data da Transação'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'PagBank', 'Valor_Bruto': df_pb['Valor Bruto'].apply(clean_money),
                            'Despesas': df_pb['Valor Taxa'].apply(clean_money), 'Descricao': 'Venda PagBank'
                        })
                        consolidado.append(res)

                    elif op_selecionada == "VR Benefícios":
                        # Identifica se é Venda ou Reembolso
                        if 'Pagamento *' in df.columns:
                            df_r = df[df['Pagamento *'].notna()].copy()
                            res = pd.DataFrame({
                                'Data': pd.to_datetime(df_r['Pagamento *'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                                'Operadora': 'VR', 'Valor_Bruto': 0.0,
                                'Despesas': df_r['Valor Bruto'].apply(clean_money) - df_r['Valor Líquido'].apply(clean_money), 'Descricao': 'Despesa Reembolso VR'
                            })
                        else:
                            res = pd.DataFrame({
                                'Data': pd.to_datetime(df['Data'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                                'Operadora': 'VR', 'Valor_Bruto': df['Valor'].apply(clean_money),
                                'Despesas': 0.0, 'Descricao': 'Venda VR'
                            })
                        consolidado.append(res)

                except Exception as e:
                    st.error(f"Erro ao processar {f.name}: Verifique se selecionou a operadora correta.")

    if consolidado:
        st.divider()
        df_final = pd.concat(consolidado, ignore_index=True)
        # Cálculo do Líquido final para conferência
        df_final['Valor_Liquido'] = df_final['Valor_Bruto'] - df_final['Despesas']
        
        st.success("✅ Tudo pronto! Veja a prévia abaixo:")
        st.dataframe(df_final)
        
        csv = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 BAIXAR CONSOLIDADO PARA O ERP", data=csv, file_name="CONSOLIDADO_ESCRITORIO.csv", mime="text/csv")
