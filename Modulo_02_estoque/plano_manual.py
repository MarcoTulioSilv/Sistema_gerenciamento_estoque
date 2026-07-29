"""
Modulo_02_estoque.plano_manual.py
Estrutura de dados para o plano de retirada/transferência manual por lote.
Substitui o PlanoConsumo gerado pelo FEFOSelector quando o usuário escolhe
os lotes diretamente na interface (T-09).
"""

from dataclasses import dataclass
from datetime import date

@dataclass
class ItemPlanoManual:
    """Representa um lote selecionado manualmente na interface."""
    lote_id: int
    num_lote: str
    qtd_a_retirar: int
    saldo_atual: int
    unidade_estoque: str = "unidade"
    data_vencimento: date | None = None
    nota_fiscal: str | None = None

    @property
    def saldo_restante(self) -> int:
        return self.saldo_atual - self.qtd_a_retirar
    
    @property
    def lote_esgotado(self) -> bool:
        return self.saldo_restante == 0

@dataclass
class PlanoManual:
    """Empacota a seleção manual para ser processada pelo EstoqueService."""
    produto_id: int
    itens: list[ItemPlanoManual]
    unidade_estoque: str = "unidade"
    centro_origem: str = ""

    @property
    def quantidade_pedida(self) -> int:
        return sum(i.qtd_a_retirar for i in self.itens)

    @property
    def quantidade_atendida(self) -> int:
        return self.quantidade_pedida
    
    @property
    def atendido_completo(self) -> bool:
        return True # Se o usuário selecionou na tela, consideramos atendido completo