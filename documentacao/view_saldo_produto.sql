-- ============================================================
-- SCE — Correção de bug: vw_saldo_produtos zerava produtos de consumo
-- Rodar manualmente contra o MySQL de produção.
-- ============================================================
USE sce_db;

-- Bug: o JOIN filtrava "l.data_vencimento >= CURDATE()", o que excluía
-- lotes com data_vencimento NULL (produtos de consumo, sem validade) —
-- eles apareciam com saldo_total = 0 em t03_produtos.py mesmo tendo
-- lotes cadastrados com quantidade > 0.
--
-- Fix: inclui lotes sem data_vencimento (IS NULL) além dos não vencidos.
-- Lotes vencidos e ainda não retirados do estoque continuam excluídos
-- do saldo (comportamento já correto, não mudou).
CREATE OR REPLACE VIEW vw_saldo_produtos AS
SELECT
    p.id AS produto_id,
    p.nome,
    p.ean,
    p.marca,
    p.fornecedor,
    p.estoque_minimo,
    p.ativo,
    COALESCE(SUM(l.quantidade_atual), 0) AS saldo_total
FROM produto p
LEFT JOIN lote l ON p.id = l.produto_id
    AND (l.data_vencimento IS NULL OR l.data_vencimento >= CURDATE())
GROUP BY p.id;
