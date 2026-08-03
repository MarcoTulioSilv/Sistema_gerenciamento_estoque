# SCE — Sistema de Controle de Estoque

Aplicação desktop para gestão de estoque hospitalar/farmacêutico do **Centro de Uronefrologia**, com rastreabilidade de insumos e medicamentos (EAN, lotes, validade e fracionamento), envio automático de relatórios por e-mail e importação de notas fiscais (DANFE) para entrada de produtos.

## Stack tecnológica

- **Python 3.11+**
- **CustomTkinter** + Tkinter (interface gráfica desktop)
- **SQLAlchemy 2.0** + **PyMySQL** (ORM sobre **MySQL**)
- **APScheduler** (notificações e relatórios agendados)
- **OpenPyXL** (geração de planilhas) e **lxml** (parser de XML de NF-e)
- **bcrypt** / **cryptography** (hash de senha e criptografia Fernet)
- **PyInstaller** + **Inno Setup 6** (empacotamento e instalador Windows)

## Estrutura do projeto

```text
Modulo_01_autenticacao/  # RBAC, login e sessão de usuários
Modulo_02_estoque/       # Regras de suprimentos, FEFO, importação de NF-e
Modulo_03_relatorios/    # Orquestração de relatórios e geração de XLSX
Modulo_04_notificacoes/  # E-mail, agendador e auditoria de jobs
Modulo_05_admin/         # Usuários e parâmetros do sistema
Modulo_06_dados/         # Modelos ORM e acesso ao banco
gui/                     # Telas e componentes CustomTkinter
instalador/              # Scripts Inno Setup
backup_script/           # Backup agendado do banco (roda no servidor)
```


## Pré-requisitos

- Windows (a aplicação usa `LOCALAPPDATA` para logs e GUI Tkinter nativa)
- Python 3.11+
- Servidor MySQL acessível
- Inno Setup 6 — apenas se for gerar o instalador

## Instalação / Setup

1. Clone o repositório e crie um ambiente virtual:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Crie o schema no MySQL a partir de `documentacao/DDL_SCE_v1_3.sql` e aplique a view em `documentacao/view_saldo_produto.sql`.

3. Copie `documentacao/.env.example` para um arquivo `.env` na raiz do projeto e preencha os valores (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, etc.). Gere a `FERNET_KEY` com o comando já indicado no próprio `.env.example`:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

4. Rode a aplicação:
   ```bash
   python main.py
   ```

## Build do instalador (opcional)

`build.bat` empacota a aplicação com PyInstaller (`SCE_Uro_v1.spec`) e gera o instalador com Inno Setup 6 (`instalador/SCE_Setup.iss`). Requer o Inno Setup 6 instalado. O caminho de publicação do auto-updater (`SHARE`, no topo do script) é específico do ambiente do Centro e deve ser ajustado para builds fora desse contexto.

## Backup automático

O diretório `backup_script/` contém o script de backup agendado do banco (roda no servidor, fora da aplicação desktop) e os `.bat` para instalar/desinstalar a tarefa agendada no Windows. Veja `backup_script/requirements.txt` para as dependências específicas dele.

## Autor

Criado por: Marco Túlio Silva Oliveira
