"""
Modulo_02_estoque . fefo_selector.py
Sprint 2B- FEFOselector: algoritmo FEFO multi-lote(RN-08)

calcula o plano de consumo antes de qualquer escrita no banco
O Plano é exibido em T-09 para confirmação antes de gravar.
"""

import logging
from dataclasses import dataclass
from datetime import date
from .lote_repo import LoteRepo

logger= logging.getLogger(__name__)

@dataclass
class ItemPlano:
    # um lote dentro do plano de consumo FEFO.
    lote_id :   int
    num_lote:   str
    data_vencimento: date
    nota_fiscal: str
    saldo_atual: int 
    qtd_a_retirar: int
    saldo_restante: int 
    unidade_estoque: str = "unidade" #pode ser expandido para outras unidades no futuro
    centro_alocacao: str = ""

    @property
    def lote_esgotado(self)-> bool:
        return self.saldo_restante==0

@dataclass
class PlanoConsumo:
    #Resultado do cálculo FEFO- exibido antes da confirmação
    produto_id: int 
    quantidade_pedida: int 
    itens: list[ItemPlano]
    saldo_total_antes: int
    centro_origem: str = ""
    unidade_estoque: str = "unidade"

    @property
    def quantidade_atendida(self)-> int:
        return sum(i.qtd_a_retirar for i in self.itens)
    
    @property
    def atendido_completo(self)-> bool:
        return self.quantidade_atendida>= self.quantidade_pedida
    
    @property
    def quantidade_maxima_disponivel(self)-> int:
        return self.saldo_total_antes

class FEFOSelector:
    """
    Calcula o plano de consumo FEFO
    Fluxo:
      1. calcular_plano() — lê lotes do banco, distribui a quantidade
         entre os lotes em ordem crescente de vencimento. Retorna PlanoConsumo.
      2. A GUI exibe o plano ao Técnico (RF-08).
      3. Após confirmação, EstoqueService.registrar_retirada() executa
         o plano gravando as movimentações atomicamente.
    """
    @staticmethod
    def calcular_plano(
        produto_id:int,
        quantidade: int, 
        apenas_vencidos: bool=False, 
        centro_origem: str|None=None, 
        unidade_estoque: str|None=None
        )->PlanoConsumo:
        """
        Calcula o plano de consumo FEFO sem tocar no banco.
 
        Args:
            produto_id:      id do produto.
            quantidade:      quantidade solicitada.
            apenas_vencidos: se True, usa apenas lotes com data_vencimento < hoje.
            centro_origem:   filtra lotes pelo centro de alocação (valor do enum).
            unidade_estoque: filtra lotes pela unidade de estoque (valor do enum).
 
        Returns:
            PlanoConsumo com os itens a consumir em ordem FEFO.
            Se quantidade > saldo filtrado, atendido_completo será False.
 
        Raises:
            ValueError: quantidade <= 0 ou produto_id inválido.
        """
        if quantidade<=0:
            raise ValueError("Quantidade deve ser maior que zero.")
        

        hoje= date.today()
        lotes= LoteRepo.listar_por_produto(produto_id, apenas_com_saldo=True) 
        #-- Filtro: vencidos ou validos----------------------------------------------
        if apenas_vencidos:
            lotes_ativos=[
                l for l in lotes
                if l.quantidade_atual> 0 
                and l.data_vencimento is not None
                and l.data_vencimento<hoje
            ]
        else:
            lotes_ativos=[
                l for l in lotes
                if l.quantidade_atual> 0 and (l.data_vencimento is None or l.data_vencimento>=hoje)
            ]
        #filtro: centro de alocação ________________________________________________
        if centro_origem:
            lotes_ativos=[
                l for l in lotes_ativos
                if l.centro_alocacao.value== centro_origem
            ]

        #Filtro: unidade de estoque ________________________________________________
        if unidade_estoque:
            lotes_ativos=[
                l for l in lotes_ativos
                if l.unidade_estoque.value== unidade_estoque
            ]
        # Ordenção FEFO_______________________________________________________________

        lotes_ativos.sort(key=lambda l: (l.data_vencimento is None, l.data_vencimento or date.max, getattr(l, 'criado_em', l.id)))
        saldo_total= sum(l.quantidade_atual for l in lotes_ativos)
        itens_plano:list[ItemPlano]=[]
        restante = quantidade

        for lote in lotes_ativos:
            if restante<=0:
                break
            retirar= min(restante, lote.quantidade_atual)
            saldo_resultante= lote.quantidade_atual-retirar

            itens_plano.append(ItemPlano(
                lote_id         = lote.id,
                num_lote        = lote.num_lote,
                data_vencimento = lote.data_vencimento,
                nota_fiscal     = lote.nota_fiscal or "—",
                saldo_atual     = lote.quantidade_atual,
                qtd_a_retirar   = retirar,
                saldo_restante  = saldo_resultante,
                unidade_estoque = lote.unidade_estoque.value,
                centro_alocacao = lote.centro_alocacao.value,
            ))
            restante-= retirar
        
        unidade_plano= itens_plano[0].unidade_estoque if itens_plano else (unidade_estoque or "unidade")
        centro_plano= itens_plano[0].centro_alocacao if itens_plano else (centro_origem or "")
        
        plano= PlanoConsumo(
            produto_id= produto_id,
            quantidade_pedida= quantidade,
            itens= itens_plano,
            saldo_total_antes= saldo_total,
            centro_origem= centro_plano,
            unidade_estoque= unidade_plano
        )

        logger.info(
            "Plano FEFO/FIFO calculado: produto_id=%s qtd=%s lotes=%s atendido=%s centro=%s unidade=%s",  
            produto_id, quantidade, len(itens_plano), plano.atendido_completo, centro_plano, unidade_plano,
        )
        return plano