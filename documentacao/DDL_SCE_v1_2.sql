-- =============================================================
-- SCE — Sistema de Controle de Estoque
-- DDL v1.2
-- MySQL Server 8.x · Engine InnoDB · charset utf8mb4
-- Gerado em: 2025-05-07
-- Baseado em: ERS v1.6 · DAS v1.3
--
-- Alterações em relação à v1.1:
--   [v1.2-01] lote.nota_fiscal: NOT NULL → NULL
--             (NF opcional no fluxo de entrada manual — RN-07 v1.6)
--   [v1.2-02] lote.chave_acesso VARCHAR(44) NULL adicionado
--             (chave de acesso DANFE — RF-04b / AD-12)
--   [v1.2-03] Índice idx_lote_chave_acesso adicionado
--   [v1.2-04] movimentacao.tipo ENUM: adicionado valor 'entrada_danfe'
--             (identifica o fluxo RF-04b para rastreabilidade)
--   [v1.2-05] movimentacao.numero_nf: mantido NULL
--             (já era nullable; confirma compatibilidade com fluxo manual)
-- =============================================================

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS,   UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE,
    SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -------------------------------------------------------------
-- Schema
-- -------------------------------------------------------------
DROP SCHEMA IF EXISTS `sce_db`;
CREATE SCHEMA IF NOT EXISTS `sce_db`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `sce_db`;



-- -------------------------------------------------------------
-- Tabela: usuario  (MOD-01)
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`usuario`;

CREATE TABLE IF NOT EXISTS `sce_db`.`usuario` (
  `id`          INT          NOT NULL AUTO_INCREMENT,
  `nome`        VARCHAR(100) NOT NULL,
  `login`       VARCHAR(60)  NOT NULL,
  `senha_hash`  VARCHAR(255) NOT NULL,
  `perfil`      ENUM('tecnico','gestora','ti') NOT NULL,
  `ativo`       TINYINT(1)   NOT NULL DEFAULT 1,
  `criado_em`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_usuario_login` (`login`)
) ENGINE = InnoDB;


-- -------------------------------------------------------------
-- Tabela: produto  (MOD-02)
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`produto`;

CREATE TABLE IF NOT EXISTS `sce_db`.`produto` (
  `id`               INT          NOT NULL AUTO_INCREMENT,
  `fornecedor_id`    INT          NULL,
  `nome`             VARCHAR(120) NOT NULL,
  `descricao`        VARCHAR(255) NULL,
  `ean`              VARCHAR(20)  NOT NULL,
  `unidade_estoque`  ENUM('CAIXA','PACOTE','UNIDADE','FRASCO','AMPOLA') NOT NULL,
  `marca`            VARCHAR(100) NULL,
  `centro_alocacao`  ENUM('almoxarifado','farmacia') NOT NULL,
  `estoque_minimo`   INT          NOT NULL DEFAULT 0,
  `ativo`            TINYINT(1)   NOT NULL DEFAULT 1,
  `criado_em`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `fornecedor`		 VARCHAR(120) NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_produto_ean` (`ean`),
  INDEX `idx_produto_fornecedor` (`fornecedor_id`)
) ENGINE = InnoDB;


-- -------------------------------------------------------------
-- Tabela: lote  (MOD-02)
--
-- [v1.2-01] nota_fiscal: NOT NULL → NULL
--           Justificativa: RN-07 v1.6 — número da NF é opcional
--           no fluxo de entrada manual pura (RF-03). Obrigatório
--           apenas nos fluxos XML (RF-04) e DANFE (RF-04b), onde
--           é preenchido automaticamente pelo sistema.
--
-- [v1.2-02] chave_acesso VARCHAR(44) NULL adicionado
--           Armazena a chave de acesso de 44 dígitos da NF-e.
--           Preenchida automaticamente:
--             - Fluxo XML: extraída do elemento <chNFe> do XML
--             - Fluxo DANFE: lida pelo leitor de barras (RF-04b)
--           NULL no fluxo de entrada manual pura.
--
-- [v1.2-03] Índice idx_lote_chave_acesso para consultas de
--           rastreabilidade fiscal e prevenção de duplicatas.
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`lote`;

CREATE TABLE IF NOT EXISTS `sce_db`.`lote` (
  `id`                INT            NOT NULL AUTO_INCREMENT,
  `produto_id`        INT            NOT NULL,
  `num_lote`          VARCHAR(60)    NOT NULL,
  `nota_fiscal`       VARCHAR(60)    NULL,
  `chave_acesso`      VARCHAR(44)    NULL,
  `data_fabricacao`   DATE           NULL,
  `data_vencimento`   DATE           NOT NULL,
  `quantidade_inicial` INT           NOT NULL,
  `quantidade_atual`  INT            NOT NULL,
  `valor_unitario`    DECIMAL(10,2)  NOT NULL,
  `valor_total`       DECIMAL(10,2)  NOT NULL,
  `criado_em`         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  -- [v1.2-03] Índice para rastreabilidade e prevenção de duplicatas
  unique INDEX `idx_lote_chave_acesso` (`chave_acesso`),
  INDEX `idx_lote_produto_vencimento` (`produto_id`, `data_vencimento`),
  CONSTRAINT `fk_lote_produto`
    FOREIGN KEY (`produto_id`)
    REFERENCES `sce_db`.`produto` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION
) ENGINE = InnoDB;


-- -------------------------------------------------------------
-- Tabela: movimentacao  (MOD-02)
--
-- [v1.2-04] tipo ENUM: adicionado 'entrada_danfe'
--           Identifica entradas registradas via leitura de chave
--           de acesso DANFE (fluxo RF-04b / DanfeEntryAssistant).
--           Permite filtros e relatórios por canal de entrada.
--
-- [v1.2-05] numero_nf: já era NULL (confirmado sem alteração)
--           Compatível com entrada manual sem NF.
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`movimentacao`;

CREATE TABLE IF NOT EXISTS `sce_db`.`movimentacao` (
  `id`           INT          NOT NULL AUTO_INCREMENT,
  `lote_id`      INT          NOT NULL,
  `usuario_id`   INT          NOT NULL,
  -- [v1.2-04] 'entrada_danfe' adicionado ao ENUM
  `tipo`         ENUM('entrada_manual','entrada_nfe','saida','entrada_danfe') NOT NULL,
  `quantidade`   INT          NOT NULL,
  -- NULL permitido — opcional no fluxo manual (RN-07 v1.6)
  `numero_nf`    VARCHAR(60)  NULL,
  `observacao`   VARCHAR(255) NULL,
  `data_hora`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_mov_lote_hora` (`lote_id`, `data_hora`),
  INDEX `idx_mov_usuario`   (`usuario_id`),
  CONSTRAINT `fk_movimentacao_lote`
    FOREIGN KEY (`lote_id`)
    REFERENCES `sce_db`.`lote` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_movimentacao_usuario`
    FOREIGN KEY (`usuario_id`)
    REFERENCES `sce_db`.`usuario` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION
) ENGINE = InnoDB;


-- -------------------------------------------------------------
-- Tabela: notificacao_log  (MOD-04)
-- Sem alterações em v1.2
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`notificacao_log`;

CREATE TABLE IF NOT EXISTS `sce_db`.`notificacao_log` (
  `id`           INT          NOT NULL AUTO_INCREMENT,
  `lote_id`      INT          NOT NULL,
  `tipo_alerta`  ENUM('vencimento_30','vencimento_15','vencimento_7','vencido','estoque_baixo') NOT NULL,
  `enviado_em`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `sucesso`      TINYINT(1)   NOT NULL,
  `erro_msg`     VARCHAR(255) NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_notif_lote_tipo_data` (`lote_id`, `tipo_alerta`, `enviado_em`),
  CONSTRAINT `fk_notificacao_lote`
    FOREIGN KEY (`lote_id`)
    REFERENCES `sce_db`.`lote` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION
) ENGINE = InnoDB;


-- -------------------------------------------------------------
-- Tabela: job_log  (MOD-04)
-- Sem alterações em v1.2
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`job_log`;

CREATE TABLE IF NOT EXISTS `sce_db`.`job_log` (
  `id`            INT          NOT NULL AUTO_INCREMENT,
  `job_nome`      VARCHAR(60)  NOT NULL,
  `executado_em`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `sucesso`       TINYINT(1)   NOT NULL,
  `detalhe`       VARCHAR(255) NULL,
  PRIMARY KEY (`id`)
) ENGINE = InnoDB;


-- -------------------------------------------------------------
-- Tabela: configuracao  (MOD-05)
-- Sem alterações em v1.2
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`configuracao`;

CREATE TABLE IF NOT EXISTS `sce_db`.`configuracao` (
  `id`              INT          NOT NULL AUTO_INCREMENT,
  `chave`           VARCHAR(120) NOT NULL,
  `valor`           VARCHAR(500) NOT NULL,
  `atualizado_em`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `atualizado_por`  INT          NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_configuracao_chave` (`chave`),
  INDEX `idx_config_usuario` (`atualizado_por`),
  CONSTRAINT `fk_configuracao_usuario`
    FOREIGN KEY (`atualizado_por`)
    REFERENCES `sce_db`.`usuario` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION
) ENGINE = InnoDB;


-- -------------------------------------------------------------
-- Tabela: relatorio_agendamento  (MOD-03)
-- Sem alterações em v1.2
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`relatorio_agendamento`;

CREATE TABLE IF NOT EXISTS `sce_db`.`relatorio_agendamento` (
  `id`              INT          NOT NULL AUTO_INCREMENT,
  `tipo_relatorio`  ENUM('movimentacao','estoque_atual','a_vencer','lotes_vencidos') NOT NULL,
  `habilitado`      TINYINT(1)   NOT NULL DEFAULT 0,
  `periodicidade`   ENUM('diario','semanal','mensal') NOT NULL,
  `horario`         TIME         NOT NULL,
  `ultimo_envio`    DATETIME     NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_agendamento_tipo` (`tipo_relatorio`)
) ENGINE = InnoDB;


-- -------------------------------------------------------------
-- Seed: usuário TI padrão
-- hash bcrypt de 'Admin@SCE2025' — redefinir na 1ª entrada
-- -------------------------------------------------------------
INSERT INTO `sce_db`.`usuario` (`nome`, `login`, `senha_hash`, `perfil`, `ativo`)
VALUES ('Administrador TI', 'admin',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMaWkal.M3UrZEAmJWl8Ru6sC2',
        'ti', 1);


-- -------------------------------------------------------------
-- Seed: configurações padrão do sistema
-- -------------------------------------------------------------
INSERT INTO `sce_db`.`configuracao` (`chave`, `valor`, `atualizado_por`) VALUES
  ('smtp_host',              'smtp.gmail.com',  1),
  ('smtp_porta',             '587',             1),
  ('smtp_usuario',           '',                1),
  ('smtp_senha_enc',         '',                1),
  ('email_gestora',          '',                1),
  ('dashboard_refresh_seg',  '30',              1),
  ('backup_diretorio',       './backups',       1);


-- -------------------------------------------------------------
-- Seed: agendamentos de relatório (todos desabilitados por padrão)
-- -------------------------------------------------------------
INSERT INTO `sce_db`.`relatorio_agendamento`
  (`tipo_relatorio`, `habilitado`, `periodicidade`, `horario`) VALUES
  ('movimentacao',   0, 'semanal', '08:00:00'),
  ('estoque_atual',  0, 'diario',  '07:00:00'),
  ('a_vencer',       0, 'diario',  '07:00:00'),
  ('lotes_vencidos', 0, 'diario',  '07:00:00');


SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
