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

st.title("🏦 Sistema de Conciliação Unificado (Escritório)")
st.markdown("Suba os arquivos e identifique a operadora para processar corretamente.")

# Upload
uploaded_files = st.file_uploader("Arraste os arquivos aqui (CSV, XLS, XLSX)", accept_multiple_files=True)

if uploaded_files:
    consolidado = []
    
    for f in uploaded_files:
        # Criamos um container visual para cada arquivo
        with st.expander(f"Configurar: {f.name}", expanded=True):
            c1, c2 = st.columns([2, 1])
            
            # MENU DE SELEÇÃO COMPLETO
            op = c2.selectbox(
                "Qual é a operadora deste arquivo?",
                ["Selecionar...", "Alelo", "Cabal", "Caixa Pagamentos", "Cielo", "Mercado Pago", "PagBank", "Pagar.me", "Pluxee", "Rede", "Sipag", "Stone", "Ticket", "VR Benefícios"],
                key=f.name
            )
            
            if op != "Selecionar...":
                try:
                    # Leitura flexível (Excel ou CSV)
                    if f.name.upper().endswith('.CSV'):
                        try: df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
                        except: df = pd.read_csv(f, sep=',', encoding='utf-8-sig')
                    else:
                        df = pd.read_excel(f)

                    res = pd.DataFrame()

                    # --- LÓGICA POR OPERADORA ---
                    if op == "Alelo":
                        # Alelo costuma ter a data na 1ª coluna e valor na 4ª
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df.iloc[:, 0], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Alelo', 'Valor_Bruto': df.iloc[:, 3].apply(clean_money),
                            'Despesas': 0.0, 'Descricao': 'Venda Alelo'
                        })

                    elif op == "Caixa Pagamentos":
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
                        # Custo de parcelamento separado
                        df_fin = df_mp[df_mp['Custos de parcelamento (financing_fee)'].apply(clean_money).abs() > 0].copy()
                        if not df_fin.empty:
                            fin_res = pd.DataFrame({
                                'Data': pd.to_datetime(df_fin['Data de creditação (date_approved)'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                                'Operadora': 'Mercado Pago', 'Valor_Bruto': 0.0,
                                'Despesas': df_fin['Custos de parcelamento (financing_fee)'].apply(clean_money).abs(), 'Descricao': 'Custo de parcelamento - MP'
                            })
                            res = pd.concat([res, fin_res])

                    elif op == "Cielo":
                        # Ignora as 11 linhas iniciais se for o relatório padrão
                        df_cie = df.copy()
                        if "Data da venda" not in df_cie.columns:
                            df_cie = df_cie.iloc[11:].copy()
                        df_cie = df_cie[df_cie.iloc[:, 10] == 'Aprovada'].copy()
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df_cie.iloc[:, 0], dayfirst=True).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Cielo', 'Valor_Bruto': df_cie.iloc[:, 7].apply(clean_money),
                            'Despesas': df_cie.iloc[:, 8].apply(clean_money).abs(), 'Descricao': 'Venda Cielo'
                        })

                    elif op == "Stone":
                        # Mapeamento Stone (Ajustar colunas conforme seu arquivo)
                        res = pd.DataFrame({
                            'Data': pd.to_datetime(df.iloc[:, 0]).dt.strftime('%d/%m/%Y'),
                            'Operadora': 'Stone', 'Valor_Bruto': df.iloc[:, 5].apply(clean_money),
                            'Despesas': df.iloc[:, 6].apply(clean_money), 'Descricao': 'Venda Stone'
                        })

                    if not res.empty:
                        consolidado.append(res)
                        st.success(f"✅ {op} lido com sucesso!")

                except Exception as e:
                    st.error(f"❌ Erro ao processar {f.name} como {op}. Verifique o modelo.")

    if consolidado:
        st.divider()
        df_final = pd.concat(consolidado, ignore_index=True)
        df_final['Valor_Liquido'] = df_final['Valor_Bruto'] - df_final['Despesas']
        
        st.subheader("📋 Prévia do Consolidado Final")
        st.dataframe(df_final)
        
        csv = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 BAIXAR ARQUIVO PARA O ERP", data=csv, file_name="CONSOLIDADO_ESCRITORIO.csv")
