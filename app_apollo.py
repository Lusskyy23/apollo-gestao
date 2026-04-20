import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURAÇÕES DA APOLLO ---
TAXA_VENDA_REAL = 361.405
TAXA_COMPRA_USD = 2500
TAXA_ADM_USD = 2100
NOME_PLANILHA = "Caixa Apollo" 

# Função para formatar dinheiro no padrão Brasil (R$ 1.234,56)
def formata_brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- CONEXÃO COM GOOGLE SHEETS ---
def conectar_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Se o app estiver na nuvem, ele pega a senha do Cofre Secreto
    if "gcp_service_account" in st.secrets:
        credenciais = dict(st.secrets["gcp_service_account"])
        from oauth2client.service_account import ServiceAccountCredentials
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credenciais, scope)
    # Se o app estiver no seu PC, ele lê o arquivo json normalmente
    else:
        from oauth2client.service_account import ServiceAccountCredentials
        creds = ServiceAccountCredentials.from_json_keyfile_name("chave_google.json", scope)
        
    client = gspread.authorize(creds)
    return client.open(NOME_PLANILHA)

# --- INTERFACE ---
st.set_page_config(page_title="Apollo - Gestão de Moedas", page_icon="🪙")
st.title("🪙 Apollo - Controle de Fluxo")

try:
    planilha = conectar_sheets()
    aba_atual = get_ou_criar_aba(planilha)
    st.sidebar.success("✅ Conectado à Planilha")
except Exception as e:
    st.sidebar.error("❌ Erro ao conectar. Verifique o arquivo JSON e o nome da planilha.")
    st.stop()

menu = st.sidebar.selectbox("Menu", ["Lançar Turno", "Compras e Fiados", "Relatório Diário"])

if menu == "Lançar Turno":
    st.header("📊 Fechamento de Turno")
    data = st.date_input("Data", datetime.now()).strftime("%d/%m/%Y")
    
    # NOVOS TURNOS ADICIONADOS AQUI
    turno = st.selectbox("Turno", ["08:00 as 17:00", "17:00 as 00:00", "00:00 as 02:00", "02:00 as 08:00"])
    
    s_inicial = st.number_input("Saldo Inicial", min_value=0)
    s_final = st.number_input("Saldo Final", min_value=0)
    
    if st.button("Salvar Turno"):
        moedas = s_inicial - s_final
        if moedas >= 0:
            valor_rs = moedas / TAXA_VENDA_REAL
            valor_rs_planilha = str(round(valor_rs, 2)).replace(".", ",")
            
            aba_atual.append_row(
                [data, "Venda Turno", turno, moedas, valor_rs_planilha, 0, "Fechamento"],
                value_input_option="USER_ENTERED"
            )
            st.success(f"Salvo! Venda de {moedas:,.0f} moedas ({formata_brl(valor_rs)})")
        else:
            st.error("Saldo final maior que o inicial!")

elif menu == "Compras e Fiados":
    st.header("💸 Compras e Dívidas")
    tipo = st.radio("Operação", ["Compra (Estoque)", "Fiado Normal", "Fiado ADM"])
    data = datetime.now().strftime("%d/%m/%Y")
    
    if tipo == "Compra (Estoque)":
        usd = st.number_input("Valor em Dólar (USD)", min_value=0.0)
        if st.button("Registrar Compra"):
            moedas = usd * TAXA_COMPRA_USD
            usd_planilha = str(usd).replace(".", ",")
            
            aba_atual.append_row(
                [data, "Compra Estoque", "-", moedas, 0, usd_planilha, "Entrada"],
                value_input_option="USER_ENTERED"
            )
            st.success(f"Estoque abastecido com {moedas:,.0f} moedas!")
            
    else:
        cliente = st.text_input("Nome do Cliente")
        moedas = st.number_input("Moedas no Fiado", min_value=0)
        if st.button("Registrar Fiado"):
            v_rs = round(moedas / TAXA_VENDA_REAL, 2) if tipo == "Fiado Normal" else 0
            v_usd = round(moedas / TAXA_ADM_USD, 2) if tipo == "Fiado ADM" else 0
            
            v_rs_planilha = str(v_rs).replace(".", ",")
            v_usd_planilha = str(v_usd).replace(".", ",")
            
            aba_atual.append_row(
                [data, tipo, "-", moedas, v_rs_planilha, v_usd_planilha, cliente],
                value_input_option="USER_ENTERED"
            )
            st.success(f"Dívida de {cliente} anotada!")

elif menu == "Relatório Diário":
    st.header("📋 Resumo do Dia")
    data_sel = st.date_input("Escolha o dia", datetime.now()).strftime("%d/%m/%Y")
    
    dados = pd.DataFrame(aba_atual.get_all_records())
    if not dados.empty:
        dia_filtrado = dados[dados['Data'] == data_sel]
        vendas = dia_filtrado[dia_filtrado['Tipo'] == 'Venda Turno'].copy()
        
        # CÁLCULO À PROVA DE FALHAS:
        # Usa apenas a quantidade de moedas (que nunca falha) para calcular o Real na hora
        # e ignora o que o Google Sheets acha que é o valor em R$.
        vendas['Moedas'] = pd.to_numeric(vendas['Moedas'], errors='coerce').fillna(0)
        total_m = vendas['Moedas'].sum()
        total_rs_calculado = total_m / TAXA_VENDA_REAL
        
        c1, c2 = st.columns(2)
        c1.metric("Moedas Vendidas", f"{total_m:,.0f}")
        c2.metric("Total em R$", formata_brl(total_rs_calculado))
        
        st.write("---")
        st.write("**Detalhamento de Turnos:**")
        
        # Recalcula a linha de cada turno para exibir bonito na tabela
        vendas_exibicao = vendas[['Turno', 'Moedas']].copy()
        vendas_exibicao['Valor (R$)'] = (vendas_exibicao['Moedas'] / TAXA_VENDA_REAL).apply(formata_brl)
        st.table(vendas_exibicao)
    else:
        st.warning("Ainda não há dados nesta aba do mês.")