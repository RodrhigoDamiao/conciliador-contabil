import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os

class SistemaConciliador:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Conciliação Contábil - Escritório")
        self.root.geometry("600x400")
        
        self.arquivos_selecionados = []
        self.consolidado = []

        # Interface
        self.label = tk.Label(root, text="Selecione os arquivos das operadoras para processar:", font=("Arial", 10, "bold"))
        self.label.pack(pady=10)

        # Listbox para mostrar arquivos selecionados
        self.listbox = tk.Listbox(root, selectmode=tk.MULTIPLE, width=80, height=10)
        self.listbox.pack(pady=5)

        # Botões
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        self.btn_add = tk.Button(btn_frame, text="Selecionar Arquivos", command=self.selecionar_arquivos, bg="#e1e1e1")
        self.btn_add.grid(row=0, column=0, padx=5)

        self.btn_run = tk.Button(btn_frame, text="RODAR PROCESSO", command=self.executar_processo, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        self.btn_run.grid(row=0, column=1, padx=5)

        self.btn_clear = tk.Button(btn_frame, text="Limpar Lista", command=self.limpar_lista)
        self.btn_clear.grid(row=0, column=2, padx=5)

    def selecionar_arquivos(self):
        files = filedialog.askopenfilenames(title="Escolha os arquivos", filetypes=[("CSV Files", "*.csv"), ("Excel Files", "*.xlsx")])
        for f in files:
            if f not in self.arquivos_selecionados:
                self.arquivos_selecionados.append(f)
                self.listbox.insert(tk.END, os.path.basename(f))

    def limpar_lista(self):
        self.arquivos_selecionados = []
        self.listbox.delete(0, tk.END)

    def clean_money(self, val):
        if pd.isna(val) or str(val).lower() == 'nan': return 0.0
        s = str(val).replace('R$', '').replace('\xa0', '').replace(' ', '').strip()
        if ',' in s and '.' in s:
            if s.find('.') < s.find(','): s = s.replace('.', '').replace(',', '.')
        elif ',' in s: s = s.replace(',', '.')
        try: return float(s)
        except: return 0.0

    def identificar_e_processar(self, caminho):
        nome = os.path.basename(caminho).upper()
        
        # Lógica de identificação por nome do arquivo conforme os modelos mapeados
        if "CABAL" in nome:
            df = pd.read_csv(caminho, sep=';', skiprows=2)
            df = df[df['Status'] == 'Transação Processada'].copy()
            df['Data_C'] = pd.to_datetime(df['Data da transação'], dayfirst=True).dt.strftime('%d/%m/%Y')
            return pd.DataFrame({
                'Data': df['Data_C'], 'Operadora': 'Cabal', 'Bandeira': df['Bandeira'],
                'Valor_Bruto': df['Valor parcela bruto'].apply(self.clean_money),
                'Despesas': df['Desconto parcela'].apply(self.clean_money),
                'Valor_Liquido': df['Valor parcela liquido'].apply(self.clean_money),
                'Numero_Cartao': df['Número do cartão'], 'Descricao': 'Venda Cabal'
            })

        elif "CAIXA" in nome:
            df = pd.read_csv(caminho)
            df = df[df['Status'] == 'Aprovada'].copy()
            return pd.DataFrame({
                'Data': pd.to_datetime(df['Data da venda'], dayfirst=True).dt.strftime('%d/%m/%Y'),
                'Operadora': 'Caixa', 'Bandeira': df['Bandeira'],
                'Valor_Bruto': df['Valor bruto da parcela'].apply(self.clean_money),
                'Despesas': df['Valor da taxa (MDR)'].apply(self.clean_money),
                'Valor_Liquido': df['Valor líquido da parcela/transação'].apply(self.clean_money),
                'Numero_Cartao': df['Número do cartão'], 'Descricao': 'Venda Caixa'
            })

        # ... (O código incluiria as demais 9 operadoras com as mesmas regras de status aprovado)
        return None

    def executar_processo(self):
        if not self.arquivos_selecionados:
            messagebox.showwarning("Aviso", "Selecione ao menos um arquivo!")
            return

        self.consolidado = []
        for caminho in self.arquivos_selecionados:
            res = self.identificar_e_processar(caminho)
            if res is not None:
                self.consolidado.append(res)

        if self.consolidado:
            final_df = pd.concat(self.consolidado, ignore_index=True)
            save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
            if save_path:
                final_df.to_csv(save_path, index=False, sep=';', encoding='utf-8-sig')
                messagebox.showinfo("Sucesso", f"Processamento concluído!\nSalvo em: {save_path}")
        else:
            messagebox.showerror("Erro", "Não foi possível processar os arquivos selecionados. Verifique os nomes.")

if __name__ == "__main__":
    root = tk.Tk()
    app = SistemaConciliador(root)
    root.mainloop()
