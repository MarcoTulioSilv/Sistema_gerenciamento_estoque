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
    def calcular_plano(produto_id:int, quantidade: int, apenas_vencidos: bool=False)->PlanoConsumo:
        """
        Calcula o plano de consumo FEFO sem tocar no banco.
 
        Args:
            produto_id: id do produto.
            quantidade: quantidade solicitada na retirada.
            apenas_vencidos: se True, considera apenas lotes vencidos.
 
        Returns:
            PlanoConsumo com os itens a consumir em ordem FEFO.
            Se quantidade > saldo total, atendido_completo será False.
 
        Raises:
            ValueError: se produto_id inválido.
        """
        if quantidade<=0:
            raise ValueError("Quantidade deve ser maior que zero.")
        

        hoje= date.today()
        #busca lotes ativos( saldo>0, não vencidos), ordenados por vencimento
        lotes= LoteRepo.listar_por_produto(produto_id, apenas_com_saldo=True) 
        if apenas_vencidos:
            lotes_ativos=[
                l for l in lotes
                if l.quantidade_atual> 0 and l.data_vencimento<hoje
            ]
        else:
            lotes_ativos=[
                l for l in lotes
                if l.quantidade_atual> 0 and l.data_vencimento>=hoje
            ]
        lotes_ativos.sort(key=lambda l: l.data_vencimento)
        saldo_total= sum(l.quantidade_atual for l in lotes_ativos)
        itens_plano=[]
        restante = quantidade

        for lote in lotes_ativos:
            if restante<=0:
                break
            retirar= min(restante,lote.quantidade_atual)
            saldo_resultante= lote.quantidade_atual-retirar
            itens_plano.append(ItemPlano(
                lote_id= lote.id,
                num_lote= lote.num_lote,
                data_vencimento= lote.data_vencimento,
                nota_fiscal= lote.nota_fiscal,
                saldo_atual= lote.quantidade_atual,
                qtd_a_retirar= retirar,
                saldo_restante= saldo_resultante,
                unidade_estoque= lote.unidade_estoque.value
            ))
            restante-= retirar
        
        plano= PlanoConsumo(
            produto_id= produto_id,
            quantidade_pedida= quantidade,
            itens= itens_plano,
            saldo_total_antes= saldo_total,
        )

        logger.info(
            "Plano FEFO calculado: produto_id=%s qtd=%s lotes=%s atendido=%s",
            produto_id,quantidade,len(itens_plano), plano.atendido_completo,
        )
        return plano