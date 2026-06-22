"""
Modulo_02_estoque . estoque_service.py
EstoqueService- casos de uso UC-02, UC-03, UC-04 (Sprint 2).
Orquestra ProdutoRepo, FornecedoresRepo  e LoteRepo.
"""
import logging
import threading
from datetime import date, datetime as _dt, datetime
from decimal import Decimal
from sqlalchemy import select
from Modulo_04_notificacoes.notificacao_service import NotificacaoService
from Modulo_06_dados import TipoMovimentacaoEnum, CentroAlocacaoEnum,UnidadeEstoqueEnum, get_session, Lote, Movimentacao, get_read_session, Produto, VwSaldoProduto
from .produto_repo import ProdutoRepo
from .lote_repo import LoteRepo
from .fefo_selector import FEFOSelector

logger= logging.getLogger(__name__)

class EstoqueService:
    #__________ Fornecedores __________________________________________________________________

    def listar_fornecedores_unicos()->list[str]:
        return ProdutoRepo.listar_fornecedore_unicos()
    
    def listar_nomes_unicos()-> list[str]:
        return ProdutoRepo.listar_nomes_unicos()
    #__________ Produtos_________________________________________________________________________
    @staticmethod
    def listar_produtos(apenas_ativos: bool |None=None):
        if apenas_ativos== True:
            return ProdutoRepo.listar(apenas_ativos)
        elif apenas_ativos== False:  
            return ProdutoRepo.listar(apenas_ativos)
        else:
            return ProdutoRepo.listar()
        
    @staticmethod
    def buscar_produto_por_ean(ean: str):
        """Usado pela leitura de código de barras. Retorna None se não encontrado."""
        return ProdutoRepo.buscar_por_ean(ean)
 
    @staticmethod
    def buscar_produto_por_nome(nome:str):
        return ProdutoRepo.buscar_por_nome(nome)
    
    @staticmethod
    def criar_produto(
        nome: str,
        ean: str,
        estoque_minimo: int   = 0,
        descricao: str        = None,
        marca: str            = None,
        fornecedor: str    = None,
    ):
        # Validações
        if not nome or not nome.strip():
            raise ValueError("Nome do produto é obrigatório.")
        if not ean or not ean.strip():
            raise ValueError("Código de barras (EAN) é obrigatório.")
        if ProdutoRepo.ean_existe(ean):
            raise ValueError(f"EAN '{ean}' já cadastrado para outro produto.")
        if estoque_minimo < 0:
            raise ValueError("Estoque mínimo não pode ser negativo.")
 
        dados = dict(
            nome            = nome.strip(),
            ean             = ean.strip(),
            estoque_minimo  = estoque_minimo,
            descricao       = descricao.strip() if descricao else None,
            marca           = marca.strip() if marca else None,
            fornecedor   = fornecedor,
            ativo           = True,
        )
        produto = ProdutoRepo.criar(dados)
        logger.info("Produto criado: %s [EAN %s]", produto.nome, produto.ean)
        return produto
 
    @staticmethod
    def atualizar_produto(id_: int, **campos):
        if "ean" in campos and ProdutoRepo.ean_existe(campos["ean"], excluir_id=id_):
            raise ValueError(f"EAN '{campos['ean']}' já cadastrado para outro produto.")
        if "estoque_minimo" in campos and campos["estoque_minimo"] < 0:
            raise ValueError("Estoque mínimo não pode ser negativo.")
        produto = ProdutoRepo.atualizar(id_, campos)
        logger.info("Produto atualizado: id=%s", id_)
        return produto
    
    #_________ Lotes/ Entradas____________________________________________________________________
    @staticmethod
    def listar_lotes(produto_id: int, apenas_com_saldo: bool = True):
        return LoteRepo.listar_por_produto(produto_id, apenas_com_saldo)
 
    @staticmethod
    def registrar_entrada_manual(
        produto_id:      int,
        num_lote:        str,
        data_vencimento: date,
        quantidade:      int,
        valor_unitario:  Decimal,
        usuario_id:      int,
        data_fabricacao: date = None,
        nota_fiscal:     str= None,
        unidade_estoque: str="",
        centro_alocacao: str = "deposito",
        
    ):
        """
        UC-04 — Registrar entrada manual.
        Cria lote + movimentação de entrada na mesma transação (RN-07).
        """
        # Validações — RN-07: NF obrigatória
        if quantidade <= 0:
            raise ValueError("Quantidade deve ser maior que zero.")
        if valor_unitario <= 0:
            raise ValueError("Valor unitário deve ser maior que zero.")
 
        valor_total = Decimal(str(valor_unitario)) * quantidade
        nf_limpa= nota_fiscal.strip() if nota_fiscal and nota_fiscal.strip() else None

        dados = dict(
            produto_id         = produto_id,
            num_lote           = num_lote.strip(),
            nota_fiscal        = nf_limpa,
            chave_acesso       = None,
            data_vencimento    = data_vencimento,
            data_fabricacao    = data_fabricacao,
            unidade_estoque    = unidade_estoque,
            centro_alocacao    = centro_alocacao,
            quantidade_inicial = quantidade,
            quantidade_atual   = quantidade,
            valor_unitario     = Decimal(str(valor_unitario)),
            valor_total        = valor_total,
            usuario_id         = usuario_id,
            tipo               = TipoMovimentacaoEnum.entrada_manual,
        )
        lote = LoteRepo.criar(dados)
        logger.info(
            "Entrada manual registrada: produto_id=%s lote=%s qtd=%s nf=%s",
            produto_id, num_lote, quantidade, nf_limpa or "(sem NF)",
        )
        return lote
    
    @staticmethod
    def registrar_entrada_danfe(
        produto_id:      int,
        num_lote:        str,
        nota_fiscal:     str,        # obrigatória — extraída da chave automaticamente
        chave_acesso:    str,        # 44 dígitos validados pelo DanfeEntryAssistant
        data_vencimento: date,
        quantidade:      int,
        valor_unitario:  Decimal,
        usuario_id:      int,
        data_fabricacao: date = None,
        unidade_estoque: str="cx",
        centro_alocacao: str = "deposito",
    ):
        """
        RF-04b — Entrada assistida por chave de acesso DANFE.
        nota_fiscal e chave_acesso são obrigatórias (extraídas automaticamente
        pelo DanfeEntryAssistant antes de chegar aqui).
        """
        if not nota_fiscal or not nota_fiscal.strip():
            raise ValueError("Número da NF é obrigatório no fluxo DANFE (extraído da chave).")
        if not chave_acesso or len(chave_acesso.strip()) != 44:
            raise ValueError("Chave de acesso inválida (deve ter 44 dígitos).")
        if quantidade <= 0:
            raise ValueError("Quantidade deve ser maior que zero.")
        if valor_unitario <= 0:
            raise ValueError("Valor unitário deve ser maior que zero.")

        valor_total = Decimal(str(valor_unitario)) * quantidade

        dados = dict(
            produto_id         = produto_id,
            num_lote           = num_lote.strip(),
            nota_fiscal        = nota_fiscal.strip(),
            chave_acesso       = chave_acesso.strip(),
            data_vencimento    = data_vencimento,
            data_fabricacao    = data_fabricacao,
            unidade_estoque    = unidade_estoque,
            centro_alocacao    = centro_alocacao,
            quantidade_inicial = quantidade,
            quantidade_atual   = quantidade,
            valor_unitario     = Decimal(str(valor_unitario)),
            valor_total        = valor_total,
            usuario_id         = usuario_id,
            tipo               = TipoMovimentacaoEnum.entrada_danfe,
        )
        lote = LoteRepo.criar(dados)
        logger.info(
            "Entrada DANFE: produto_id=%s lote=%s qtd=%s nf=%s chave=...%s",
            produto_id, num_lote, quantidade, nota_fiscal, chave_acesso[-4:],
        )
        return lote

    @staticmethod
    def calcular_plano_fefo(
        produto_id:      int,
        quantidade:      int,
        apenas_vencidos: bool = False,
        centro_origem:   str | None = None,
        unidade_estoque: str | None = None,
    ):
        """
        RF-08 — Calcula e retorna o plano de consumo FEFO sem gravar no banco.
        O plano é exibido em T-09 antes da confirmação.

        Args:
            produto_id:      id do produto.
            quantidade:      quantidade solicitada.
            apenas_vencidos: se True, usa apenas lotes com data_vencimento < hoje.
            centro_origem:   filtra lotes pelo centro de alocação (valor do enum).
            unidade_estoque: filtra lotes pela unidade de estoque (valor do enum).
        """
        return FEFOSelector.calcular_plano(
            produto_id,
            quantidade,
            apenas_vencidos  = apenas_vencidos,
            centro_origem    = centro_origem,
            unidade_estoque  = unidade_estoque,
        )
    
    @staticmethod
    def registrar_retirada(plano, usuario_id: int, observacao: str=None, baixa_vencido: bool=False):
        """
        RF-07, RN-08- executa o plano FEFO confirmado.
        grava N movimantações (uma por lote) na mesma transação InnoDB.
        lotes esgotados são zerados atomicamente.

        Args: 
            plano: PlanoConsumo retornado por calular_plano_fefo().
            usuario_id: id do usuário que está executando a retirada.
            observacao: texto opcional replicado em todos os registros(RN-05).

        Raises:
            raise ValueError(
                f"Estoque insuficiente. Quantidade máxima disponível:"
                f" {plano['quantidade_total_disponivel']} unidades."
            )
        """
    
        with get_session() as session:
            for item in plano.itens:
                # Atualiza saldo do lote
                lote= session.get(Lote, item.lote_id)
                if lote is None:
                    raise ValueError(f"Lote {item.lote_id} não encontrado.")
                
                lote.quantidade_atual = item.saldo_restante
                if lote.quantidade_atual == 0:
                    logger.info("Lote esgotado: id=%s produto_id=%s num_lote=%s, ", lote.id, lote.produto_id, lote.num_lote)

                #Registra movimentação de saida
                if baixa_vencido== True:
                    tipo_registro = TipoMovimentacaoEnum.baixa_vencido 
                else:
                    tipo_registro = TipoMovimentacaoEnum.saida

                mov= Movimentacao(
                    lote_id = item.lote_id,
                    usuario_id = usuario_id,
                    tipo= tipo_registro,
                    quantidade = item.qtd_a_retirar,
                    numero_nf= None,
                    observacao= observacao or None,
                    data_hora= datetime.utcnow(),
                )
                session.add(mov)
            if baixa_vencido == True:
                logger.info(
                    "Baixa por vencimento: produto_id=%s qtd=%s lotes=%s usuario=%s",
                    plano.produto_id, plano.quantidade_pedida, len(plano.itens), usuario_id,
                )
            else:
                logger.info(
                    "Retirada registrada: produto_id=%s qtd=%s lotes=%s usuario=%s",
                    plano.produto_id, plano.quantidade_pedida, len(plano.itens), usuario_id,
                )

            #verifica estoque minimo apos commit e sinaliza para alerta(RF-13)
            try:
                saldo_pos= LoteRepo.saldo_total_produto(plano.produto_id)-plano.quantidade_atendida
                with get_read_session() as s:
                    prod= s.get(Produto, plano.produto_id)
                    if prod and prod.estoque_minimo> 0 and saldo_pos <= prod.estoque_minimo:
                        logger.warning(
                            "ESTOQUE BAIXO: produto_id = %s saldo= %s minimo= %s",
                            plano.produto_id, saldo_pos, prod.estoque_minimo,
                        ) 
                        # Dispara alerta por e-mail de forma assíncrona (não bloqueia a GUI)
                        threading.Thread(
                            target=_disparar_alerta_estoque_baixo,
                            args=(plano.produto_id,),
                            daemon=True,
                        ).start()
                        return True # sinaliza estoque baixo para a GUI disparar alerta
            except Exception as exc:
                logger.error("Erro ao verificar estoque minimo pós-retirada: %s", exc)

            return False # estoque ok, sem alerta

    @staticmethod
    def registrar_transferencia( plano, usuario_id: int, destino_centro: str, fator_fracionamento: int = 1, unidade_destino: str | None = None, observacao: str | None = None) -> None:
        """
        Transfere as unidades do PlanoConsumo para outro centro de alocação,
        com fracionamento opcional de embalagem.

        Regras:
          - O FEFO escolhe o lote (o primeiro lote com saldo suficiente).
          - O técnico define a quantidade — pode ser parcial; o restante
            do lote permanece no centro original, na unidade original.
          - Se fator_fracionamento == 1: apenas debita o lote origem e
            cria movimentação de transferência. O cria novo lote no destino,
            caso o lote seja esgotado, a muda o centro de alocação do lote original para o destino.
          - Se fator_fracionamento > 1: além do débito no lote origem,
            cria um novo Lote espelho no banco representando as unidades
            fracionadas. O valor_unitario é recalculado (original / fator).
            A unidade_estoque do produto NÃO é alterada globalmente —
            o novo lote representa as unidades menores; o produto continua
            com a unidade original para os lotes que ficaram no depósito.

        Raises:
            ValueError: fator < 1, ou fator > 1 sem unidade_destino.
        """
        if fator_fracionamento < 1:
            raise ValueError("O fator de fracionamento deve ser maior ou igual a 1.")
        if fator_fracionamento > 1 and not unidade_destino:
            raise ValueError(
                "Informe a unidade de destino ao fracionar (ex: 'unidade').")
        now = _dt.utcnow()

        with get_session() as session:
            for item in plano.itens:
                lote_origem = session.get(Lote, item.lote_id)
                if lote_origem is None:
                    raise ValueError(f"Lote {item.lote_id} não encontrado.")

                # 1. Debita do lote origem
                lote_origem.quantidade_atual = item.saldo_restante

                obs_mov = observacao or f"Transferência {lote_origem.centro_alocacao} -> {destino_centro}"

                # 2. Movimentação de saída no lote origem
                session.add(Movimentacao(
                    lote_id    = item.lote_id,
                    usuario_id = usuario_id,
                    tipo       = TipoMovimentacaoEnum.transferencia,
                    quantidade = item.qtd_a_retirar,
                    numero_nf  = None,
                    observacao = obs_mov,
                    data_hora  = now,
                ))

                # 3. Preparação das variáveis do lote de destino
                criar_espelho = True
                
                if fator_fracionamento > 1:
                    qtd_dest = item.qtd_a_retirar * fator_fracionamento
                    val_unit_dest = lote_origem.valor_unitario / fator_fracionamento
                    unidade_dest_enum = UnidadeEstoqueEnum(unidade_destino)
                    num_lote_dest = f"{lote_origem.num_lote}-F{fator_fracionamento}{destino_centro[:3].upper()}"
                    obs_entrada = (
                        f"{obs_mov} | "
                        f"{item.qtd_a_retirar} {lote_origem.unidade_estoque.value}"
                        f" x{fator_fracionamento} = {qtd_dest} {unidade_destino}"
                    )
                else:
                    if item.saldo_restante == 0:
                        # Lote 100% esgotado na origem: apenas muda o centro de alocação (sem criar espelho)
                        lote_origem.centro_alocacao = CentroAlocacaoEnum(destino_centro)
                        criar_espelho = False
                    else:
                        # Transferência parcial: Preparação para criar o sufixo -T
                        qtd_dest = item.qtd_a_retirar
                        val_unit_dest = lote_origem.valor_unitario
                        unidade_dest_enum = lote_origem.unidade_estoque
                        num_lote_dest = f"{lote_origem.num_lote}-T{destino_centro[:3].upper()}"
                        obs_entrada = obs_mov

                # 4. Criação ou Incremento no Destino
                if criar_espelho:
                    val_tot_dest = round(val_unit_dest * qtd_dest, 2)
                    
                    # Consulta se este lote derivado (-F ou -T) já foi transferido para cá antes
                    lote_existente = session.query(Lote).filter_by(
                        produto_id=lote_origem.produto_id,
                        num_lote=num_lote_dest
                    ).first()

                    if lote_existente:
                        # A MÁGICA AQUI: Apenas soma as quantidades e valores (incremental)
                        lote_existente.quantidade_atual += qtd_dest
                        lote_existente.quantidade_inicial += qtd_dest
                        lote_existente.valor_total += val_tot_dest
                        lote_dest_id = lote_existente.id
                    else:
                        # Cria o lote derivado pela primeira vez
                        lote_dest = Lote(
                            produto_id         = lote_origem.produto_id,
                            num_lote           = num_lote_dest,
                            nota_fiscal        = lote_origem.nota_fiscal,
                            data_fabricacao    = lote_origem.data_fabricacao,
                            data_vencimento    = lote_origem.data_vencimento,
                            unidade_estoque    = unidade_dest_enum,
                            centro_alocacao    = CentroAlocacaoEnum(destino_centro),
                            quantidade_inicial = qtd_dest,
                            quantidade_atual   = qtd_dest,
                            valor_unitario     = round(val_unit_dest, 4),
                            valor_total        = val_tot_dest,
                            criado_em          = now
                        )
                        session.add(lote_dest)
                        session.flush() # Salva temporariamente para gerar o ID
                        lote_dest_id = lote_dest.id

                    # Registra a movimentação de entrada vinculada ao lote correto (novo ou existente)
                    session.add(Movimentacao(
                        lote_id    = lote_dest_id,
                        usuario_id = usuario_id,
                        tipo       = TipoMovimentacaoEnum.entrada_manual,
                        quantidade = qtd_dest,
                        numero_nf  = lote_origem.nota_fiscal,
                        observacao = obs_entrada,
                        data_hora  = now,
                    ))

            logger.info(
                "Transferência: produto_id=%s destino=%s fator=%s usuario=%s",
                plano.produto_id, destino_centro, fator_fracionamento, usuario_id,
            )

    @staticmethod 
    def importar_nfe(dados_nfe, usuario_id: int):
        """
        RF-04, RN-06- Importa NF-e: cria lotes para todos os itens cadastrados.
        atomicidade total: tudo ou nada(uma transação por NF-e).

        Args:
            dados_nfe: DadosNFe com todos os itens .cadastrado==True.
            usuario_id: id do usuário que está realizando a importação.
        
        Raises:
            ValueError: se houver itens não cadastrados.
        """
        if dados_nfe.itens_nao_cadastrados:
            nomes=[f"EAN{i.ean}-{i.descricao}" for i in dados_nfe.itens_nao_cadastrados]
            raise ValueError(
                f"Há{len(nomes)} produto(s) não cadastrado(s)."
                f"Cadastre-os antes de importar: \n"+"\n".join(nomes)
            )
        
        from datetime import date as _date
        lotes_criados= []

        with get_session() as session:
            for item in dados_nfe.itens:
                if not item.produto_id:
                    continue # item sem produto cadastrado, já sinalizado no erro acima

                lote= Lote(
                    produto_id = item.produto_id,
                    num_lote = item.num_lote or f"NFE-{dados_nfe.numero_nf}-{item.numero_item}",
                    nota_fiscal = dados_nfe.numero_nf,
                    data_fabricacao= item.data_fabricacao,
                    data_vencimento= item.data_vencimento or _date(9999,12,31),
                    unidade_estoque    = UnidadeEstoqueEnum.unidade.value,
                    centro_alocacao    = CentroAlocacaoEnum.deposito.value,
                    quantidade_inicial= int(item.quantidade),
                    quantidade_atual= int(item.quantidade),
                    valor_unitario = item.valor_unitario,
                    valor_total= item.valor_total,
                    criado_em= datetime.utcnow(),
                )
                session.add(lote)
                session.flush() # para obter o id do lote criado

                mov= Movimentacao(
                lote_id= lote.id,
                usuario_id= usuario_id,
                tipo = TipoMovimentacaoEnum.entrada_nfe,
                quantidade = int(item.quantidade),
                numero_nf = dados_nfe.numero_nf,
                observacao= f"Importação NF-e{dados_nfe.numero_nf}",
                data_hora= datetime.utcnow(),
                )
                session.add(mov)
                lotes_criados.append(lote.id)
        logger.info(
            "NF-e importada nº %s . %d lotes criados . usuario= %s",
            dados_nfe.numero_nf, len(lotes_criados), usuario_id,
        )

        return lotes_criados
    
    @classmethod
    def listar_view_produtos(cls):
        """Busca os produtos e seus saldos totais consumindo o Modelo ORM da View."""
        try:
            # Usando a sessão read-only do seu database.py
            with get_read_session() as session:
                query = select(VwSaldoProduto)
                # scalars().all() desembrulha o resultado e devolve uma lista limpa de objetos VwSaldoProduto
                resultados = session.execute(query).scalars().all()
                return resultados
        except Exception as e:
            logger.error("Erro ao buscar view de saldos via ORM: %s", e)
            return []
    
    # ── Helper fora da classe para uso em thread separada ────────────────────────
 
def _disparar_alerta_estoque_baixo(produto_id: int) -> None:
    """
    Chamado em thread daemon após retirada que aciona estoque mínimo.
    Importação local evita circular import com MOD-04.
    """
    try:
        NotificacaoService.alertar_estoque_baixo(produto_id)
    except Exception as exc:
        logger.error("Erro ao disparar alerta de estoque baixo (produto %s): %s", produto_id, exc)