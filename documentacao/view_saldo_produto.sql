use sce_db;

CREATE VIEW vw_saldo_produtos AS
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
LEFT JOIN lote l ON p.id = l.produto_id AND l.data_vencimento >= CURDATE()
GROUP BY p.id;
 
