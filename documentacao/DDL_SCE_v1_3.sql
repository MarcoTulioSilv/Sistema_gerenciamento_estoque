-- MySQL Workbench Forward Engineering

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Schema mydb
-- -----------------------------------------------------
-- -----------------------------------------------------
-- Schema sce_db
-- -----------------------------------------------------

-- -----------------------------------------------------
-- Schema sce_db
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `sce_db` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci ;
USE `sce_db` ;

-- -----------------------------------------------------
-- Table `sce_db`.`usuario`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `sce_db`.`usuario` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nome` VARCHAR(100) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `login` VARCHAR(60) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `senha_hash` VARCHAR(255) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `perfil` ENUM('tecnico', 'admin', 'ti') CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `ativo` TINYINT(1) NOT NULL DEFAULT '1',
  `criado_em` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_usuario_login` (`login` ASC) VISIBLE)
ENGINE = InnoDB
AUTO_INCREMENT = 4
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `sce_db`.`configuracao`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `sce_db`.`configuracao` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `chave` VARCHAR(120) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `valor` VARCHAR(500) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `atualizado_em` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `atualizado_por` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_configuracao_chave` (`chave` ASC) VISIBLE,
  INDEX `idx_config_usuario` (`atualizado_por` ASC) VISIBLE,
  CONSTRAINT `fk_configuracao_usuario`
    FOREIGN KEY (`atualizado_por`)
    REFERENCES `sce_db`.`usuario` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 9
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `sce_db`.`job_log`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `sce_db`.`job_log` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `job_nome` VARCHAR(60) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `executado_em` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `sucesso` TINYINT(1) NOT NULL,
  `detalhe` VARCHAR(255) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL DEFAULT NULL,
  PRIMARY KEY (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 2
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `sce_db`.`produto`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `sce_db`.`produto` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `fornecedor` VARCHAR(150) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL DEFAULT NULL,
  `nome` VARCHAR(120) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `descricao` VARCHAR(255) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL DEFAULT NULL,
  `ean` VARCHAR(15) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `marca` VARCHAR(100) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL DEFAULT NULL,
  `estoque_minimo` INT NOT NULL DEFAULT '0',
  `ativo` TINYINT(1) NOT NULL DEFAULT '1',
  `criado_em` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_produto_ean` (`ean` ASC) VISIBLE)
ENGINE = InnoDB
AUTO_INCREMENT = 20
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `sce_db`.`lote`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `sce_db`.`lote` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `produto_id` INT NOT NULL,
  `num_lote` VARCHAR(60) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `nota_fiscal` VARCHAR(60) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL DEFAULT NULL,
  `data_fabricacao` DATE NULL DEFAULT NULL,
  `data_vencimento` DATE NOT NULL,
  `quantidade_inicial` INT NOT NULL,
  `quantidade_atual` INT NOT NULL,
  `valor_unitario` DECIMAL(10,2) NOT NULL,
  `valor_total` DECIMAL(10,2) NOT NULL,
  `criado_em` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `chave_acesso` VARCHAR(44) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL DEFAULT NULL,
  `unidade_estoque` ENUM('caixa', 'pacote', 'unidade', 'ampola', 'galao', 'fardo', 'litro', 'rolo', 'kit', 'dose') CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `centro_alocacao` ENUM('deposito', 'almoxarifado', 'farmacia') CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_lote_produto` (`produto_id` ASC, `num_lote` ASC) VISIBLE,
  INDEX `idx_lote_produto_vencimento` (`produto_id` ASC, `data_vencimento` ASC) VISIBLE,
  CONSTRAINT `fk_lote_produto`
    FOREIGN KEY (`produto_id`)
    REFERENCES `sce_db`.`produto` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 36
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `sce_db`.`movimentacao`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `sce_db`.`movimentacao` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `lote_id` INT NOT NULL,
  `usuario_id` INT NOT NULL,
  `tipo` ENUM('entrada_manual', 'entrada_nfe', 'saida', 'entrada_danfe', 'transferencia', 'baixa_vencido') CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `quantidade` INT NULL DEFAULT NULL,
  `numero_nf` VARCHAR(60) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL DEFAULT NULL,
  `observacao` VARCHAR(255) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL DEFAULT NULL,
  `data_hora` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_mov_lote_hora` (`lote_id` ASC, `data_hora` ASC) VISIBLE,
  INDEX `idx_mov_usuario` (`usuario_id` ASC) VISIBLE,
  CONSTRAINT `fk_movimentacao_lote`
    FOREIGN KEY (`lote_id`)
    REFERENCES `sce_db`.`lote` (`id`),
  CONSTRAINT `fk_movimentacao_usuario`
    FOREIGN KEY (`usuario_id`)
    REFERENCES `sce_db`.`usuario` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 53
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `sce_db`.`notificacao_log`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `sce_db`.`notificacao_log` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `lote_id` INT NOT NULL,
  `tipo_alerta` ENUM('vencimento_30', 'vencimento_15', 'vencimento_7', 'vencido', 'estoque_baixo') CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `enviado_em` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `sucesso` TINYINT(1) NOT NULL,
  `erro_msg` VARCHAR(255) CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_notif_lote_tipo_data` (`lote_id` ASC, `tipo_alerta` ASC, `enviado_em` ASC) VISIBLE,
  CONSTRAINT `fk_notificacao_lote`
    FOREIGN KEY (`lote_id`)
    REFERENCES `sce_db`.`lote` (`id`))
ENGINE = InnoDB
AUTO_INCREMENT = 7
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


-- -----------------------------------------------------
-- Table `sce_db`.`relatorio_agendamento`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `sce_db`.`relatorio_agendamento` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `tipo_relatorio` ENUM('movimentacao', 'estoque_atual', 'a_vencer', 'lotes_vencidos') CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `habilitado` TINYINT(1) NOT NULL DEFAULT '0',
  `periodicidade` ENUM('diario', 'semanal', 'mensal') CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci' NOT NULL,
  `horario` TIME NOT NULL,
  `ultimo_envio` DATETIME NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `uq_agendamento_tipo` (`tipo_relatorio` ASC) VISIBLE)
ENGINE = InnoDB
AUTO_INCREMENT = 5
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;


SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
