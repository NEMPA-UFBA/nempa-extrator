# NEMPA Extrator

Aplicação em Python e Streamlit para converter relatórios FIPLAN em uma base tabular pronta para conferência, exportação em CSV e análise em ferramentas de BI.

## Objetivo

- Ler relatórios PDF sem persistir o arquivo original em disco.
- Extrair lançamentos financeiros com base em regras de texto e expressões regulares.
- Validar os totais do documento com uma camada de auditoria por credor e total geral.

## Principais recursos

- Extração de lançamentos a partir do texto do PDF.
- Classificação de registros associados a "Ouro Negro".
- Filtros por ano e categoria.
- Exportação da tabela tratada em CSV.
- Painel de conferência de integridade dos totais extraídos.

## Requisitos

- Python 3.10 ou superior.
- Dependências instaladas a partir de requirements.txt.

## Execução local

```bash
python3 -m pip install -r requirements.txt
streamlit run app_nempa.py
```

## Dependências principais

- streamlit
- pandas
- pdfplumber

## Segurança

O processamento é feito em memória. PDFs de entrada e arquivos exportados não devem ser versionados no repositório.
