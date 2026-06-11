import streamlit as st
import pandas as pd
import pdfplumber
import re
import io

# ==========================================
# CONFIGURAÇÃO DA PÁGINA (Discreta e Profissional)
# ==========================================
st.set_page_config(
    page_title="NEMPA - Tratamento de Dados",
    page_icon="📊",
    layout="wide"
)

# ==========================================
# REGRAS DE EXTRAÇÃO E CONVERSÃO
# ==========================================
PADRAO_LANCAMENTO = re.compile(r"(22101\.\d{4}\.\d{2}\.\d{7}-\d)(?:\s+(22101\.\d{4}\.\d{2}\.\d{7}-\d)\s+(22101\.\d{4}\.\d{2}\.\d{7}-\d))?\s+([A-Z]{3})\s+(?:(\d{4,5})\s+)?(\d{2}/\d{2}/\d{4})")
PADRAO_PAGINA = re.compile(r"P[áa]gina\s*:?\s*(\d+)\s+de", re.IGNORECASE)
PADRAO_TOTAL_CREDOR = re.compile(r"Total Credor[^\*]*(?:\*\*\*)?\s*([\d\.,]+)", re.IGNORECASE)
PADRAO_TOTAL_GERAL = re.compile(r"Total Geral UO[^\*]*(?:\*\*\*)?\s*([\d\.,]+)", re.IGNORECASE)

def parse_br_currency(v_str):
    v = str(v_str).replace('(', '-').replace(')', '').strip()
    if len(v) >= 3 and v[-3] in ['.', ',']:
        centavos = v[-2:]
        inteiro = v[:-3].replace('.', '').replace(',', '')
        try: return float(f"{inteiro}.{centavos}")
        except: return 0.0
    return 0.0

def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

# ==========================================
# MOTOR DE EXTRAÇÃO
# ==========================================
# Mantém o resultado em cache enquanto os parâmetros de entrada não mudarem.
@st.cache_data(show_spinner=False)
def extrair_mega_pdf(arquivo_bytes, nome_arquivo):
    dados_finais = []
    auditoria_oficial = {"soma_geral_pdf": 0.0, "credores_pdf": {}}
    relatorio_atual_id = 0
    texto_buffer = ""

    # O arquivo é recebido pelo navegador e processado diretamente em memória.
    with pdfplumber.open(io.BytesIO(arquivo_bytes)) as pdf:
        for pagina in pdf.pages:
            txt = pagina.extract_text()
            if not txt: continue
            
            match_pag = PADRAO_PAGINA.search(txt)
            if match_pag and int(match_pag.group(1)) == 1:
                if texto_buffer.strip():
                    processar_bloco_relatorio(texto_buffer, relatorio_atual_id, dados_finais, auditoria_oficial)
                texto_buffer = ""
                relatorio_atual_id += 1
            
            texto_buffer += txt + "\n"
            
        if texto_buffer.strip():
            if relatorio_atual_id == 0: relatorio_atual_id = 1
            processar_bloco_relatorio(texto_buffer, relatorio_atual_id, dados_finais, auditoria_oficial)

    colunas = ["Relatorio_ID", "Cod_Credor", "Nome_Credor", "Empenho", "Liquidacao", "Pagamento", "Tipo", "CBO", "Data_Pagto", "Dotacao", "Valor", "Historico", "Ouro_Negro", "Valor_Numerico"]
    
    if not dados_finais: return None, auditoria_oficial
    return pd.DataFrame(dados_finais, columns=colunas), auditoria_oficial

def processar_bloco_relatorio(texto_bloco, relatorio_id, dados_finais, auditoria_oficial):
    totais_gerais = PADRAO_TOTAL_GERAL.findall(texto_bloco)
    for tg in totais_gerais:
        auditoria_oficial["soma_geral_pdf"] += parse_br_currency(tg)

    blocos_credor = re.split(r"CREDOR\s*:\s*", texto_bloco)
    for bloco in blocos_credor[1:]:
        match_nome = re.search(r"^(\d+)\s*\n*NOME\s*:\s*([^\n]+)", bloco)
        if not match_nome: continue
        
        credor_code = match_nome.group(1).strip()
        nome_credor = match_nome.group(2).strip()
        
        totais_credor = PADRAO_TOTAL_CREDOR.findall(bloco)
        if totais_credor:
            if credor_code not in auditoria_oficial["credores_pdf"]:
                auditoria_oficial["credores_pdf"][credor_code] = 0.0
            for tc in totais_credor:
                auditoria_oficial["credores_pdf"][credor_code] += parse_br_currency(tc)

        resto_bloco = bloco[match_nome.end():]
        linhas_uteis = [linha.strip() for linha in resto_bloco.split('\n') if linha.strip() and not (linha.startswith("*") or "FIP 680" in linha or "Total Credor" in linha or "Total Geral" in linha or "Página" in linha or "DATA" in linha or "PAGTO" in linha)]

        texto_normalizado = " ".join(linhas_uteis)
        partes = PADRAO_LANCAMENTO.split(texto_normalizado)

        if len(partes) > 1:
            for i in range(1, len(partes), 7):
                if i + 6 >= len(partes): break
                
                empenho = partes[i]
                liquidacao = partes[i+1] if partes[i+1] else "S/I"
                pagamento = partes[i+2] if partes[i+2] else "S/I"
                tipo = partes[i+3]
                cbo = partes[i+4] if partes[i+4] else "S/I"
                data = partes[i+5]
                resto = partes[i+6]

                dotacao_match = re.search(r"(22101\.\d{4}\.\d{2}\.[0-9.]+)", resto)
                dotacao = dotacao_match.group(1) if dotacao_match else ""
                if dotacao: resto = resto.replace(dotacao, "", 1)

                valor_match = re.search(r"(\(?\d{1,3}(?:[\.\,]\d{3})*[\.\,]\d{2}\)?)", resto)
                valor = valor_match.group(1) if valor_match else "0,00"
                if valor_match: resto = resto.replace(valor, "", 1)

                historico = re.sub(r'\s+', ' ', resto.strip())
                indicador_ouro_negro = "SIM" if "OURO NEGRO" in historico.upper() else "NAO"
                valor_num = parse_br_currency(valor)

                dados_finais.append([
                    f"Relat. {relatorio_id:02d}", credor_code, nome_credor,
                    empenho, liquidacao, pagamento, tipo, cbo, data, dotacao, valor, historico, indicador_ouro_negro, valor_num
                ])

# ==========================================
# FRONT-END (STREAMLIT)
# ==========================================
st.title("NEMPA - Tratamento de Dados")
st.markdown("Carregue um relatório em PDF para converter o conteúdo em uma base tabular.")

arquivo_upload = st.file_uploader("Arraste e solte o arquivo PDF aqui", type=["pdf"])

if arquivo_upload is not None:
    with st.spinner('Processando o documento. Isso pode levar alguns minutos em arquivos grandes.'):
        arquivo_bytes = arquivo_upload.read()
        df_master, auditoria = extrair_mega_pdf(arquivo_bytes, arquivo_upload.name)

    if df_master is None:
        st.error("Falha estrutural. O documento não possui o formato esperado.")
    else:
        st.success(f"Base carregada com sucesso: {len(df_master)} pagamentos mapeados.")

        # --- FILTROS GLOBAIS DA APLICAÇÃO ---
        df_master['Ano'] = df_master['Data_Pagto'].str[-4:]
        
        with st.expander("🔎 Filtros Globais da Base", expanded=False):
            col_f1, col_f2 = st.columns(2)
            anos_disponiveis = sorted(list(df_master['Ano'].unique()))
            anos_selecionados = col_f1.multiselect("Filtrar por Ano:", anos_disponiveis, default=anos_disponiveis)
            ouro_selecionado = col_f2.multiselect("Filtro Ouro Negro:", ["SIM", "NAO"], default=["SIM", "NAO"])
            
        # Mantém uma visão derivada da base para aplicar os filtros globais.
        df_filtrado = df_master[(df_master['Ano'].isin(anos_selecionados)) & (df_master['Ouro_Negro'].isin(ouro_selecionado))]

        aba1, aba2, aba3 = st.tabs(["📥 Exportação de Tabela", "🛡️ Compliance e Integridade", "🧮 Agrupamentos Dinâmicos"])

        # --- ABA 1: EXPORTAÇÃO (Usa dados filtrados) ---
        with aba1:
            st.subheader("Base de Dados Sanitizada")
            modo_exportacao = st.radio("Escolha o layout da tabela:", ("Padrão (Foco em Análise)", "Completo (Com dotações e códigos do sistema)"))
            
            if modo_exportacao == "Padrão (Foco em Análise)":
                df_exibicao = df_filtrado[["Relatorio_ID", "Cod_Credor", "Nome_Credor", "Data_Pagto", "Valor", "Historico", "Ouro_Negro"]]
            else:
                df_exibicao = df_filtrado.drop(columns=["Valor_Numerico", "Ano"], errors='ignore')
                
            df_exibicao.index = range(1, len(df_exibicao) + 1)
            st.dataframe(df_exibicao, use_container_width=True)
            
            csv = df_exibicao.to_csv(index=False, sep=';', encoding='utf-8-sig')
            st.download_button(label="📥 Baixar CSV", data=csv, file_name="Base_Sanitizada_NEMPA.csv", mime="text/csv")

        # --- ABA 2: AUDITORIA (Usa dados MESTRES, imunes a filtros) ---
        with aba2:
            st.subheader("Compliance e Integridade")
            st.info("A auditoria sempre avalia o documento em sua totalidade, ignorando os filtros aplicados, para garantir a precisão matemática do PDF original.")
            
            somas_python = df_master.groupby('Cod_Credor')['Valor_Numerico'].sum()
            erros = []
            total_credores_oficial = 0.0
            
            for cod, total_py in somas_python.items():
                total_pdf = auditoria["credores_pdf"].get(cod, 0.0)
                total_credores_oficial += total_pdf
                diff = total_py - total_pdf
                if abs(diff) > 0.01:
                    nome = df_master[df_master['Cod_Credor'] == cod]['Nome_Credor'].iloc[0]
                    erros.append({"Credor": nome, "Esperado (PDF)": formatar_moeda(total_pdf), "Extraído": formatar_moeda(total_py), "Diferença": formatar_moeda(diff)})
            
            if erros:
                st.warning(f"Atenção: {len(erros)} credores apresentaram divergência. Verifique lançamentos manuais no PDF.")
                df_erros = pd.DataFrame(erros)
                df_erros.index = range(1, len(df_erros) + 1)
                st.table(df_erros)
            else:
                st.success("✅ Integridade Nível 2 confirmada: Todos os credores batem 100%.")

            st.markdown("#### Resumo Global (Nível 3)")
            col1, col2, col3 = st.columns(3)
            col1.metric("1. Extraído pelo Sistema", formatar_moeda(df_master['Valor_Numerico'].sum()))
            col2.metric("2. Impresso nos Credores", formatar_moeda(total_credores_oficial))
            col3.metric("3. Impresso no 'Total UO'", formatar_moeda(auditoria["soma_geral_pdf"]))

        # --- ABA 3: EXPLORADOR (Usa dados filtrados) ---
        with aba3:
            st.subheader("Agrupamentos Dinâmicos")
            eixos = st.multiselect("Como você deseja agrupar os dados?", ["Ano", "Ouro_Negro", "Nome_Credor", "Relatorio_ID"], default=["Ano", "Ouro_Negro"])
            
            if eixos:
                resumo = df_filtrado.groupby(eixos)['Valor_Numerico'].sum().reset_index()
                resumo['Total_R$'] = resumo['Valor_Numerico'].apply(formatar_moeda)
                
                df_resumo_exibicao = resumo.drop(columns=['Valor_Numerico'])
                df_resumo_exibicao.index = range(1, len(df_resumo_exibicao) + 1)
                
                st.dataframe(df_resumo_exibicao, use_container_width=True)
                
                csv_resumo = df_resumo_exibicao.to_csv(index=False, sep=';', encoding='utf-8-sig')
                st.download_button(label="📥 Baixar resumo em CSV", data=csv_resumo, file_name="Resumo_Agrupado.csv", mime="text/csv")