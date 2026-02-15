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

st.title("🏦 Sistema de Conciliação Unificado (Versão 2.0)")
st.markdown("Arraste as planilhas e identifique cada uma para processar o fechamento.")

uploaded_files = st.file_uploader("Upload de Arquivos (CSV, XLS, XLSX)", accept_multiple_files=True)

if uploaded_files:
    consolidado = []
    st.subheader("⚙️ Configuração de Operadoras")
    
    for f in uploaded_files:
        with st.expander(f"Configurar: {f.name}", expanded=True):
            col_info, col_op = st.columns([2, 1])
            col_info.write(f"Arquivo carregado com sucesso.")
            
            # LISTA COMPLETA E ATUALIZADA
            op = col_op.selectbox(
                "Selecione a Operadora:",
                ["Selecionar...", "Alelo", "Cabal", "Caixa Pagamentos", "Cielo", "Mercado Pago", "PagBank", "Pagar.me", "Pluxee", "Rede", "Sipag", "Stone", "Ticket", "VR Benefícios"],
                key=f.name
            )
            
            if op != "Selecionar...":
                try:
                    # Leitura universal (Excel ou CSV)
                    if f.name.upper().endswith('.CSV'):
                        try: df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
                        except: df = pd.read_csv(f, sep=',', encoding='utf-8-sig')
                    else:
                        df = pd.read_excel(f)

                    res = pd.DataFrame()

                    # --- REGRAS ESPECÍFICAS ---
                    if op == "Caixa Pagamentos":
                        df_c = df[df['Status'] == 'Aprovada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_c['Data da venda'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Caixa', 'Valor_Bruto': df_c['Valor bruto da parcela'].apply(clean_money),
                            'Despesas': df_c['Valor da taxa (MDR)'].apply(clean_money), 'Descricao': 'Venda Caixa'
                        })

                    elif op == "Mercado Pago":
                        df_mp = df[df['Status da operação (status)'] == 'approved'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_mp['Data de creditação (date_approved)'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Mercado Pago', 'Valor_Bruto': df_mp['Valor do produto (transaction_amount)'].apply(clean_money),
                            'Despesas': df_mp['Tarifa do Mercado Pago (mercadopago_fee)'].apply(clean_money), 'Descricao': 'Venda Mercado Pago'
                        })
                        # Custo de Parcelamento como linha extra
                        df_fin = df_mp[df_mp['Custos de parcelamento (financing_fee)'].apply(clean_money).abs() > 0].copy()
                        if not df_fin.empty:
                            fin_res = pd.DataFrame({
                                'Data': pd.to_datetime(df_fin['Data de creditação (date_approved)'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                                'Operadora': 'Mercado Pago', 'Valor_Bruto': 0.0,
                                'Despesas': df_fin['Custos de parcelamento (financing_fee)'].apply(clean_money).abs(), 'Descricao': 'Custo de parcelamento - MP'
                            })
                            res = pd.concat([res, fin_res])

                    elif op == "Cielo":
                        # Tenta ler ignorando o cabeçalho se ele existir
                        df_cie = df.copy()
                        if "Data da venda" not in df_cie.columns:
                            df_cie = pd.read_excel(f, skiprows=11) if not f.name.upper().endswith('.CSV') else pd.read_csv(f, skiprows=11)
                        df_cie = df_cie[df_cie.iloc[:, 10] == 'Aprovada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_cie.iloc[:, 0], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Cielo', 'Valor_Bruto': df_cie.iloc[:, 7].apply(clean_money),
                            'Despesas': df_cie.iloc[:, 8].apply(clean_money).abs(), 'Descricao': 'Venda Cielo'
                        })

                    elif op == "Pagar.me":
                        df_pm = df[df['Status'] == 'Pago'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_pm['Data']).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Pagar.me', 'Valor_Bruto': df_pm['Valor Capturado (R$)'].apply(clean_money),
                            'Despesas': df_pm['Custo da Transação'].apply(clean_money), 'Descricao': 'Venda Pagar.me'
                        })

                    elif op == "Rede":
                        df_r = df[df['status da venda'] == 'aprovada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_r['data da venda']).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Rede', 'Valor_Bruto': df_r['valor da venda atualizado'].apply(clean_money),
                            'Despesas': df_r['valor total das taxas descontadas (MDR+recebimento automático)'].apply(clean_money), 'Descricao': 'Venda Rede'
                        })

                    elif op in ["Alelo", "Ticket", "Pluxee"]:
                        # Lógica para vouchers (Geralmente coluna 1 é data, coluna 4 é valor)
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df.iloc[:, 0], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': op, 'Valor_Bruto': df.iloc[:, 3].apply(clean_money),
                            'Despesas': 0.0, 'Descricao': f'Venda {op}'
                        })

                    # Se conseguiu processar, adiciona à lista
                    if not res.empty:
                        consolidado.append(res)
                        st.success(f"Arquivo de {op} pronto!")

                except Exception as e:
                    st.error(f"Erro no arquivo {f.name}: Verifique se as colunas estão no padrão da {op}.")

    if consolidado:
        st.divider()
        df_final = pd.concat(consolidado, ignore_index=True)
        df_final['Valor_Liquido'] = df_final['Valor_Bruto'] - df_final['Despesas']
        
        st.subheader("📊 Prévia do Fechamento")
        st.dataframe(df_final)
        
        csv = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 BAIXAR CONSOLIDADO PARA O ERP", data=csv, file_name="CONSOLIDADO_ESCRITORIO.csv", mime="text/csv")
