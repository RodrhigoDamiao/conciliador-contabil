import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Conciliador Pro", layout="wide")

def clean_money(val):
    if pd.isna(val): return 0.0
    s = str(val).replace('R$', '').replace(' ', '').strip()
    if ',' in s and '.' in s:
        if s.find('.') < s.find(','): s = s.replace('.', '').replace(',', '.')
    elif ',' in s: s = s.replace(',', '.')
    try: return float(s)
    except: return 0.0

st.title("🏦 Conciliador Multiformato (CSV, XLS, XLSX)")
st.info("Arraste qualquer arquivo de operadora abaixo.")

uploaded_files = st.file_uploader("Upload", accept_multiple_files=True)

if uploaded_files:
    consolidado = []
    
    for f in uploaded_files:
        nome = f.name.upper()
        try:
            # DETECÇÃO DE FORMATO
            if nome.endswith('.CSV'):
                # Tenta detectar separador (ponto e vírgula ou vírgula)
                try: df = pd.read_csv(f, sep=';', encoding='utf-8-sig')
                except: df = pd.read_csv(f, sep=',', encoding='utf-8-sig')
            else:
                # Trata XLS e XLSX (Excel)
                df = pd.read_excel(f)

            # LÓGICA DE IDENTIFICAÇÃO (Exemplo simplificado de 3 tipos)
            # CAIXA
            if "CAIXA" in nome or "STATUS" in df.columns:
                df_c = df[df['Status'] == 'Aprovada'].copy()
                res = pd.DataFrame({
                    'Data': df_c.iloc[:, 2], # Ajustado para posição se coluna mudar
                    'Operadora': 'Caixa',
                    'Valor_Bruto': df_c.iloc[:, 12].apply(clean_money),
                    'Descricao': 'Venda Caixa'
                })
                consolidado.append(res)
            
            # MERCADO PAGO
            elif "MERCADO" in nome or "date_approved" in df.columns:
                df_mp = df[df.iloc[:, 13] == 'approved'].copy()
                res = pd.DataFrame({
                    'Data': df_mp.iloc[:, 1],
                    'Operadora': 'Mercado Pago',
                    'Valor_Bruto': df_mp.iloc[:, 16].apply(clean_money),
                    'Descricao': 'Venda Mercado Pago'
                })
                consolidado.append(res)
                
            # PAGARME
            elif "PAGARME" in nome or "Valor Capturado" in df.columns:
                df_pm = df[df['Status'] == 'Pago'].copy()
                res = pd.DataFrame({
                    'Data': df_pm['Data'],
                    'Operadora': 'Pagar.me',
                    'Valor_Bruto': df_pm['Valor Capturado (R$)'].apply(clean_money),
                    'Descricao': 'Venda Pagar.me'
                })
                consolidado.append(res)

        except Exception as e:
            st.error(f"Erro ao ler {f.name}: Certifique-se que o formato está correto.")

    if consolidado:
        df_final = pd.concat(consolidado, ignore_index=True)
        st.success("Arquivos processados!")
        st.dataframe(df_final)
        
        csv = df_final.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button("📥 Baixar Consolidado", data=csv, file_name="CONSOLIDADO_TOTAL.csv")
    else:
        st.warning("Nenhum dado reconhecido. Verifique se o nome do arquivo contém o nome da operadora.")
