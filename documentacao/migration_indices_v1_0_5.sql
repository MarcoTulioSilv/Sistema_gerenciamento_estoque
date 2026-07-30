-- ============================================================
-- SCE — Migração de índices (v1.0.5)
-- Rodar manualmente contra o MySQL de produção.
-- Antes de rodar, confira se o índice já existe:
--   SHOW INDEX FROM lote        WHERE Key_name = 'idx_lote_vencimento';
--   SHOW INDEX FROM movimentacao WHERE Key_name = 'idx_mov_data_hora';
-- (evita erro "Duplicate key name" se alguém já tiver rodado este script)
-- ============================================================
USE sce_db;

-- Cobre buscas cross-produto por vencimento sem produto_id no WHERE
-- (NotificacaoService.verificar_vencimentos / alertar_lotes_vencidos).
-- Os índices já existentes (idx_lote_produto_vencimento, idx_saida_estoque)
-- sempre lideram com produto_id, então não servem para essa busca.
ALTER TABLE lote
    ADD INDEX idx_lote_vencimento (data_vencimento);

-- Cobre buscas por período sem lote_id no WHERE
-- (KPI "movimentações hoje" da T-02 e o filtro de datas da T-19).
-- idx_mov_lote_hora(lote_id, data_hora) já existe mas lidera com lote_id.
ALTER TABLE movimentacao
    ADD INDEX idx_mov_data_hora (data_hora);

-- ------------------------------------------------------------
-- Opcional — limpeza de índice redundante (não obrigatório).
-- idx_lote_produto_vencimento(produto_id, data_vencimento) é um prefixo
-- estrito de idx_saida_estoque(produto_id, data_vencimento, criado_em):
-- qualquer consulta que usaria o primeiro também usa o segundo. Manter os
-- dois só custa espaço em disco e overhead de escrita, sem ganho de leitura.
-- Descomente se quiser aplicar:
-- ALTER TABLE lote DROP INDEX idx_lote_produto_vencimento;
-- ------------------------------------------------------------

-- Nota: idx_notif_lote_tipo_data (lote_id, tipo_alerta, enviado_em) em
-- notificacao_log já existe em produção — só foi documentado agora no
-- modelo SQLAlchemy (Modulo_06_dados/models.py), nenhuma ação de banco
-- necessária para ele.
