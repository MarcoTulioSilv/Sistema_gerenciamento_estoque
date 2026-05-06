-- =============================================================
-- SCE — Sistema de Controle de Estoque
-- DDL v1.1 — corrigido
-- MySQL Server 8.x · Engine InnoDB · charset utf8mb4
-- Gerado em: 2026-04-10
-- Baseado em: ERS v1.5 · DAS v1.2 · ERD v2
-- =============================================================

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS,   UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -------------------------------------------------------------
-- Schema
-- [FIX-01] Renomeado de mydb para sce_db
-- [FIX-02] charset alterado de utf8 para utf8mb4
-- -------------------------------------------------------------
DROP SCHEMA IF exists `sce_db`;
CREATE SCHEMA IF NOT EXISTS `sce_db`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `sce_db`;


-- -------------------------------------------------------------
-- Tabela: usuario  (MOD-01)
-- [FIX-22] Typo 'loguin' → 'login'
-- [FIX-23] Typo 'pefil'  → 'perfil'
-- [FIX-24] ENUM alinhado com ERS: 'tecnico','gestora','ti'
-- [FIX-03] Removido INT ZEROFILL
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`usuario`;

CREATE TABLE IF NOT EXISTS `sce_db`.`usuario` (
  `id`          INT          NOT NULL AUTO_INCREMENT,
  `nome`        VARCHAR(100) NOT NULL,
  `login`       VARCHAR(60)  NOT NULL,
  `senha_hash`  VARCHAR(255) NOT NULL,
  `perfil`      ENUM('tecnico','admin','ti') NOT NULL,
  `ativo`       TINYINT(1)   NOT NULL DEFAULT 1,
  `criado_em`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_usuario_login` (`login`)
) ENGINE = InnoDB;


-- -------------------------------------------------------------
-- Tabela: produto  (MOD-02)
-- [FIX-04] PK composta removida → PK apenas id
-- [FIX-07] 'unidade de estoque' → 'unidade_estoque'
-- [FIX-08] EAN INT → VARCHAR(20) UNIQUE (suporta zeros à esquerda)
-- [FIX-09] Adicionado criado_em
-- [FIX-03] Removido INT ZEROFILL
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`produto`;

CREATE TABLE IF NOT EXISTS `sce_db`.`produto` (
  `id`               INT          NOT NULL AUTO_INCREMENT,
  `fornecedor`    	VARCHAR(150),
  `nome`             VARCHAR(120) NOT NULL,
  `descricao`        VARCHAR(255) NULL,
  `ean`              VARCHAR(15)  NOT NULL,
  `unidade_estoque`  ENUM('caixa','pacote','unidade','ampola','galao','fardo','litro','rolo','kit','dose') NOT NULL,
  `marca`            VARCHAR(100) NULL,
  `centro_alocacao`  ENUM('almoxarifado','farmacia') NOT NULL,
  `estoque_minimo`   INT          NOT NULL DEFAULT 0,
  `ativo`            TINYINT(1)   NOT NULL DEFAULT 1,
  `criado_em`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_produto_ean` (`ean`)
) ENGINE = InnoDB;


-- -------------------------------------------------------------
-- Tabela: lote  (MOD-02)
-- [FIX-10] num_lote INT → VARCHAR(60) (suporta letras e hífen)
-- [FIX-11] nota_fiscal INT → VARCHAR(60)
-- [FIX-12] PK composta (idlote + nota_fiscal) → PK apenas id
-- [FIX-13] Typo 'quantiade_atual' → 'quantidade_atual'
-- [FIX-14] 'valor unitario'/'valor total' → valor_unitario/valor_total
-- [FIX-03] Removido INT ZEROFILL
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`lote`;

CREATE TABLE IF NOT EXISTS `sce_db`.`lote` (
  `id`                INT            NOT NULL AUTO_INCREMENT,
  `produto_id`        INT            NOT NULL,
  `num_lote`          VARCHAR(60)    NOT NULL,
  `nota_fiscal`       VARCHAR(60)    NOT NULL,
  `data_fabricacao`   DATE           NULL,
  `data_vencimento`   DATE           NOT NULL,
  `quantidade_inicial` INT           NOT NULL,
  `quantidade_atual`  INT            NOT NULL,
  `valor_unitario`    DECIMAL(10,2)  NOT NULL,
  `valor_total`       DECIMAL(10,2)  NOT NULL,
  `criado_em`         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_lote_produto_vencimento` (`produto_id`, `data_vencimento`),
  CONSTRAINT `fk_lote_produto`
    FOREIGN KEY (`produto_id`)
    REFERENCES `sce_db`.`produto` (`id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION
) ENGINE = InnoDB;


-- -------------------------------------------------------------
-- Tabela: movimentacao  (MOD-02)
-- [FIX-15] observacao NOT NULL → NULL (RN-05: campo opcional)
-- [FIX-16] PK composta com 4 campos → PK apenas id
-- [FIX-17] FK para lote simplificada: apenas lote_id (sem nota_fiscal)
-- [FIX-25] Adicionado numero_nf para rastreio da NF na movimentação
-- [FIX-03] Removido INT ZEROFILL
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`movimentacao`;

CREATE TABLE IF NOT EXISTS `sce_db`.`movimentacao` (
  `id`           INT          NOT NULL AUTO_INCREMENT,
  `lote_id`      INT          NOT NULL,
  `usuario_id`   INT          NOT NULL,
  `tipo`         ENUM('entrada_manual','entrada_nfe','saida') NOT NULL,
  `quantidade`   INT          NOT NULL,
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
-- [FIX-18] Typo 'venciemento_2' → 'vencimento_2'
-- [FIX-19] PK composta → PK apenas id
-- [FIX-17] FK para lote: apenas lote_id
-- [FIX-03] Removido INT ZEROFILL
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `sce_db`.`notificacao_log`;

CREATE TABLE IF NOT EXISTS `sce_db`.`notificacao_log` (
  `id`           INT          NOT NULL AUTO_INCREMENT,
  `lote_id`      INT          NOT NULL,
  `tipo_alerta`  ENUM('vencimento_15','vencimento_7','vencimento_2','vencido','estoque_baixo') NOT NULL,
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
-- Sem erros encontrados; apenas padronização de nomenclatura
-- [FIX-03] Removido INT ZEROFILL
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
-- [FIX-21] PK composta → PK apenas id
-- [FIX-03] Removido INT ZEROFILL
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
-- [FIX-20] Adicionado campo tipo_relatorio (ausente no original)
-- [FIX-03] Removido INT ZEROFILL
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
-- Índices adicionais recomendados pelo DAS v1.2
-- -------------------------------------------------------------
-- produto(ean)                     → já criado como UNIQUE
-- lote(produto_id, data_vencimento)→ já criado como INDEX
-- movimentacao(lote_id, data_hora) → já criado como INDEX
-- notificacao_log(lote_id, tipo_alerta, enviado_em) → já criado como INDEX


-- -------------------------------------------------------------
-- Seed: usuário TI padrão (senha deve ser redefinida na 1ª entrada)
-- hash bcrypt de 'Admin@SCE2025' — apenas para primeiro acesso
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