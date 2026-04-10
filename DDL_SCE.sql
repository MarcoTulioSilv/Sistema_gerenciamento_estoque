-- MySQL Workbench Forward Engineering

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Schema mydb
-- -----------------------------------------------------
DROP SCHEMA IF EXISTS `mydb` ;

-- -----------------------------------------------------
-- Schema mydb
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `mydb` DEFAULT CHARACTER SET utf8 ;
SHOW WARNINGS;
USE `mydb` ;

-- -----------------------------------------------------
-- Table `mydb`.`fornecedor`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mydb`.`fornecedor` ;

SHOW WARNINGS;
CREATE TABLE IF NOT EXISTS `mydb`.`fornecedor` (
  `idfornecedor` INT ZEROFILL NOT NULL AUTO_INCREMENT,
  `nome` VARCHAR(100) NOT NULL,
  PRIMARY KEY (`idfornecedor`),
  UNIQUE INDEX `idfornecedor_UNIQUE` (`idfornecedor` ASC) VISIBLE)
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `mydb`.`Produto`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mydb`.`Produto` ;

SHOW WARNINGS;
CREATE TABLE IF NOT EXISTS `mydb`.`Produto` (
  `idProduto` INT ZEROFILL NOT NULL AUTO_INCREMENT,
  `nome` VARCHAR(120) NOT NULL,
  `locacao` ENUM('almoxarifado', 'farmacia') NOT NULL,
  `EAN` INT NOT NULL,
  `descrição` VARCHAR(100) NULL,
  `unidade de estoque` ENUM('CAIXA', 'PACOTE') NOT NULL,
  `estoque_minimo` INT NOT NULL,
  `ativo` TINYINT NOT NULL,
  `fornecedor` VARCHAR(45) NOT NULL,
  `marca` VARCHAR(45) NOT NULL,
  `fornecedor_idfornecedor` INT ZEROFILL NOT NULL,
  PRIMARY KEY (`idProduto`, `fornecedor_idfornecedor`),
  UNIQUE INDEX `idtable2_UNIQUE` (`idProduto` ASC) VISIBLE,
  INDEX `fk_Produto_fornecedor1_idx` (`fornecedor_idfornecedor` ASC) VISIBLE,
  CONSTRAINT `fk_Produto_fornecedor1`
    FOREIGN KEY (`fornecedor_idfornecedor`)
    REFERENCES `mydb`.`fornecedor` (`idfornecedor`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `mydb`.`lote`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mydb`.`lote` ;

SHOW WARNINGS;
CREATE TABLE IF NOT EXISTS `mydb`.`lote` (
  `idlote` INT ZEROFILL NOT NULL AUTO_INCREMENT,
  `num_lote` INT NOT NULL,
  `Produto_idProduto` INT ZEROFILL NOT NULL,
  `data_fabricacao` DATE NOT NULL,
  `data_vencimento` DATE NOT NULL,
  `quantidade_inicial` INT NOT NULL,
  `quantiade_atual` INT NOT NULL,
  `criado_em` DATETIME NOT NULL,
  `valor unitario` DECIMAL(10,2) NOT NULL,
  `valor total` DECIMAL(10,2) NOT NULL,
  `nota_fiscal` INT NOT NULL,
  PRIMARY KEY (`idlote`, `nota_fiscal`),
  UNIQUE INDEX `idlote_UNIQUE` (`idlote` ASC) VISIBLE,
  INDEX `fk_lote_Produto_idx` (`Produto_idProduto` ASC) VISIBLE,
  CONSTRAINT `fk_lote_Produto`
    FOREIGN KEY (`Produto_idProduto`)
    REFERENCES `mydb`.`Produto` (`idProduto`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `mydb`.`usuario`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mydb`.`usuario` ;

SHOW WARNINGS;
CREATE TABLE IF NOT EXISTS `mydb`.`usuario` (
  `idusuario` INT ZEROFILL NOT NULL AUTO_INCREMENT,
  `nome` VARCHAR(60) NOT NULL,
  `loguin` VARCHAR(45) NOT NULL,
  `senha_hash` VARCHAR(100) NOT NULL,
  `pefil` ENUM('operacional', 'gestor', 'TI') NOT NULL,
  `ativo` TINYINT NOT NULL,
  `criado_em` DATETIME NOT NULL,
  PRIMARY KEY (`idusuario`),
  UNIQUE INDEX `idusuario_UNIQUE` (`idusuario` ASC) VISIBLE)
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `mydb`.`movimentacao`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mydb`.`movimentacao` ;

SHOW WARNINGS;
CREATE TABLE IF NOT EXISTS `mydb`.`movimentacao` (
  `idmovimentacao` INT ZEROFILL NOT NULL AUTO_INCREMENT,
  `tipo` ENUM('entrada_manual', 'entrada_NFE', 'saida') NOT NULL,
  `quantidade` INT NOT NULL,
  `observacao` VARCHAR(100) NOT NULL,
  `data_hora` DATETIME NOT NULL,
  `lote_idlote` INT ZEROFILL NOT NULL,
  `lote_nota_fiscal` INT NOT NULL,
  `usuario_idusuario` INT ZEROFILL NOT NULL,
  PRIMARY KEY (`idmovimentacao`, `lote_idlote`, `lote_nota_fiscal`, `usuario_idusuario`),
  INDEX `fk_movimentacao_lote1_idx` (`lote_idlote` ASC, `lote_nota_fiscal` ASC) VISIBLE,
  INDEX `fk_movimentacao_usuario1_idx` (`usuario_idusuario` ASC) VISIBLE,
  CONSTRAINT `fk_movimentacao_lote1`
    FOREIGN KEY (`lote_idlote` , `lote_nota_fiscal`)
    REFERENCES `mydb`.`lote` (`idlote` , `nota_fiscal`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_movimentacao_usuario1`
    FOREIGN KEY (`usuario_idusuario`)
    REFERENCES `mydb`.`usuario` (`idusuario`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `mydb`.`notificacao_log`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mydb`.`notificacao_log` ;

SHOW WARNINGS;
CREATE TABLE IF NOT EXISTS `mydb`.`notificacao_log` (
  `idnotificacao_log` INT ZEROFILL NOT NULL AUTO_INCREMENT,
  `tipo_alerta` ENUM('vencimento_15', 'vencimento_7', 'venciemento_2', 'vencido', 'estoque_baixo') NOT NULL,
  `lote_idlote` INT ZEROFILL NOT NULL,
  `lote_nota_fiscal` INT NOT NULL,
  `enviado_em` DATETIME NOT NULL,
  `sucesso` TINYINT NOT NULL,
  `erro_msg` VARCHAR(45) NULL,
  PRIMARY KEY (`idnotificacao_log`, `lote_idlote`, `lote_nota_fiscal`),
  UNIQUE INDEX `idnotificacao_log_UNIQUE` (`idnotificacao_log` ASC) VISIBLE,
  INDEX `fk_notificacao_log_lote1_idx` (`lote_idlote` ASC, `lote_nota_fiscal` ASC) VISIBLE,
  CONSTRAINT `fk_notificacao_log_lote1`
    FOREIGN KEY (`lote_idlote` , `lote_nota_fiscal`)
    REFERENCES `mydb`.`lote` (`idlote` , `nota_fiscal`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `mydb`.`configuracao`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mydb`.`configuracao` ;

SHOW WARNINGS;
CREATE TABLE IF NOT EXISTS `mydb`.`configuracao` (
  `idconfiguracao` INT ZEROFILL NOT NULL AUTO_INCREMENT,
  `chave` VARCHAR(120) NOT NULL,
  `valor` VARCHAR(45) NOT NULL,
  `atualizado_em` DATETIME NOT NULL,
  `atualizado_por` INT ZEROFILL NOT NULL,
  PRIMARY KEY (`idconfiguracao`, `atualizado_por`),
  UNIQUE INDEX `idconfiguracao_UNIQUE` (`idconfiguracao` ASC) VISIBLE,
  INDEX `fk_configuracao_usuario1_idx` (`atualizado_por` ASC) VISIBLE,
  UNIQUE INDEX `chave_UNIQUE` (`chave` ASC) VISIBLE,
  CONSTRAINT `fk_configuracao_usuario1`
    FOREIGN KEY (`atualizado_por`)
    REFERENCES `mydb`.`usuario` (`idusuario`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `mydb`.`job_log`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mydb`.`job_log` ;

SHOW WARNINGS;
CREATE TABLE IF NOT EXISTS `mydb`.`job_log` (
  `idjob_log` INT ZEROFILL NOT NULL AUTO_INCREMENT,
  `job_nome` VARCHAR(45) NOT NULL,
  `executado_em` DATETIME NOT NULL,
  `sucesso` TINYINT NOT NULL,
  `detalhe` VARCHAR(100) NULL,
  PRIMARY KEY (`idjob_log`),
  UNIQUE INDEX `idjob_log_UNIQUE` (`idjob_log` ASC) VISIBLE)
ENGINE = InnoDB;

SHOW WARNINGS;

-- -----------------------------------------------------
-- Table `mydb`.`relatorio_agendamento`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `mydb`.`relatorio_agendamento` ;

SHOW WARNINGS;
CREATE TABLE IF NOT EXISTS `mydb`.`relatorio_agendamento` (
  `idrelatorio_agendamento` INT ZEROFILL NOT NULL AUTO_INCREMENT,
  `habilitado` TINYINT NOT NULL,
  `periodicidade` ENUM('diario', 'semanal', 'mensal') NOT NULL,
  `horario` TIME NOT NULL,
  `ultimo_envio` DATETIME NOT NULL,
  PRIMARY KEY (`idrelatorio_agendamento`),
  UNIQUE INDEX `idrelatorio_agendamento_UNIQUE` (`idrelatorio_agendamento` ASC) VISIBLE)
ENGINE = InnoDB;

SHOW WARNINGS;

SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
