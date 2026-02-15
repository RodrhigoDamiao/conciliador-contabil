import pandas as pd
import numpy as np
import os

class ConciliadorContabil:
    def __init__(self):
        self.consolidado = []

    def clean_money(self, val):
        if pd.isna(val) or str(val).lower() == 'nan':
            return 0.0
        s = str(val).replace('R$', '').replace('\xa0', '').replace(' ', '').strip()
        # Trata formato BR (1.234,56)
        if ',' in s and '.' in s:
            if s.find('.') < s.find(','):
                s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            s = s.replace(',', '.')
        try:
            return float(s)
        except:
            return 0.0

    def processar_arquivos(self):
        # 1. CABAL
        if os.path.exists('CABAL-VOUCHER.csv'):
            df = pd.read_csv('CABAL-VOUCHER.csv', sep=';', skiprows=2)
            df = df[df['Status'] == 'Transação Processada'].copy()
            df['Data_C'] = pd.to_datetime(df['Data da transação'], dayfirst=True).dt.strftime('%d/%m/%Y')
            self.consolidado.append(pd.DataFrame({
                'Data': df['Data_C'], 'Operadora': 'Cabal', 'Bandeira': df['Bandeira'],
                'Valor_Bruto': df['Valor parcela bruto'].apply(self.clean_money),
                'Despesas': df['Desconto parcela'].apply(self.clean_money),
                'Valor_Liquido': df['Valor parcela liquido'].apply(self.clean_money),
                'Numero_Cartao': df['Número do cartão'], 'Descricao': 'Venda Cabal'
            }))

        # 2. CIELO
        if os.path.exists('CIELO.xlsx - vendas_cielo_historico_detalhe1.csv'):
            df = pd.read_csv('CIELO.xlsx - vendas_cielo_historico_detalhe1.csv', skiprows=11)
            df = df[df.iloc[:, 10] == 'Aprovada'].copy()
            df['Data_C'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True).dt.strftime('%d/%m/%Y')
            self.consolidado.append(pd.DataFrame({
                'Data': df['Data_C'], 'Operadora': 'Cielo', 'Bandeira': df.iloc[:, 6],
                'Valor_Bruto': df.iloc[:, 7].apply(self.clean_money),
                'Despesas': df.iloc[:, 8].apply(self.clean_money).abs(),
                'Valor_Liquido': df.iloc[:, 9].apply(self.clean_money),
                'Numero_Cartao': df.iloc[:, 23], 'Descricao': 'Venda Cielo'
            }))

        # 3. REDE
        if os.path.exists('REDE.xlsx - vendas.csv'):
            df = pd.read_csv('REDE.xlsx - vendas.csv', skiprows=1)
            df = df[df['status da venda'] == 'aprovada'].copy()
            df['Card'] = np.where((df['número do cartão'] == '-') | (df['número do cartão'].isna()), df['id carteira digital'], df['número do cartão'])
            self.consolidado.append(pd.DataFrame({
                'Data': pd.to_datetime(df['data da venda']).dt.strftime('%d/%m/%Y'),
                'Operadora': 'Rede', 'Bandeira': df['bandeira'],
                'Valor_Bruto': df['valor da venda atualizado'].apply(self.clean_money),
                'Despesas': df['valor total das taxas descontadas (MDR+recebimento automático)'].apply(self.clean_money),
                'Valor_Liquido': df['valor líquido'].apply(self.clean_money),
                'Numero_Cartao': df['Card'], 'Descricao': 'Venda Rede'
            }))

        # 4. CAIXA (Lógica de Parcelas)
        if os.path.exists('CAIXA PAGAMENTOS.xlsx - Sheet1.csv'):
            df = pd.read_csv('CAIXA PAGAMENTOS.xlsx - Sheet1.csv')
            df = df[df['Status'] == 'Aprovada'].copy()
            self.consolidado.append(pd.DataFrame({
                'Data': pd.to_datetime(df['Data da venda'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                'Operadora': 'Caixa Pagamentos', 'Bandeira': df['Bandeira'],
                'Valor_Bruto': df['Valor bruto da parcela'].apply(self.clean_money),
                'Despesas': df['Valor da taxa (MDR)'].apply(self.clean_money),
                'Valor_Liquido': df['Valor líquido da parcela/transação'].apply(self.clean_money),
                'Numero_Cartao': df['Número do cartão'], 'Descricao': 'Venda Caixa'
            }))

        # 5. MERCADO PAGO (Despesas Separadas)
        if os.path.exists('MERCADO PAGO.xls - export-activities.csv'):
            df = pd.read_csv('MERCADO PAGO.xls - export-activities.csv')
            df = df[df['Status da operação (status)'] == 'approved'].copy()
            data_c = pd.to_datetime(df['Data de creditação (date_approved)'], dayfirst=True).dt.strftime('%d/%m/%Y')
            
            # Linha de Venda
            self.consolidado.append(pd.DataFrame({
                'Data': data_c, 'Operadora': 'Mercado Pago', 'Bandeira': df['Meio de pagamento (payment_type)'],
                'Valor_Bruto': df['Valor do produto (transaction_amount)'].apply(self.clean_money),
                'Despesas': df['Tarifa do Mercado Pago (mercadopago_fee)'].apply(self.clean_money),
                'Valor_Liquido': df['Valor do produto (transaction_amount)'].apply(self.clean_money) - df['Tarifa do Mercado Pago (mercadopago_fee)'].apply(self.clean_money),
                'Numero_Cartao': '', 'Descricao': 'Venda Mercado Pago'
            }))
            # Linha de Financiamento
            df_fin = df[df['Custos de parcelamento (financing_fee)'].apply(self.clean_money).abs() > 0].copy()
            if not df_fin.empty:
                self.consolidado.append(pd.DataFrame({
                    'Data': pd.to_datetime(df_fin['Data de creditação (date_approved)'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                    'Operadora': 'Mercado Pago', 'Bandeira': df_fin['Meio de pagamento (payment_type)'],
                    'Valor_Bruto': 0.0, 'Despesas': df_fin['Custos de parcelamento (financing_fee)'].apply(self.clean_money).abs(),
                    'Valor_Liquido': -df_fin['Custos de parcelamento (financing_fee)'].apply(self.clean_money).abs(),
                    'Numero_Cartao': '', 'Descricao': 'Custo de parcelamento - Mercado Pago'
                }))

        # FINALIZAÇÃO
        if self.consolidado:
            final_df = pd.concat(self.consolidado, ignore_index=True)
            final_df.to_csv('CONSOLIDADO-ESCRITORIO.csv', index=False, sep=';', encoding='utf-8-sig')
            print("Sistema: Sucesso! Arquivo CONSOLIDADO-ESCRITORIO.csv gerado.")
        else:
            print("Sistema: Nenhum arquivo compatível encontrado no diretório.")

if __name__ == "__main__":
    app = ConciliadorContabil()
    app.processar_arquivos()
