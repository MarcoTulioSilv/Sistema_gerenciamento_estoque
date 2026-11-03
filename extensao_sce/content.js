console.log("SCE: Extensão injetada com sucesso. Aguardando NF...");

let escutaAtiva = setInterval(() => {
    let lblNf = document.querySelector(".fixo-nro-serie span");
    if (lblNf && lblNf.innerText.trim() !== "") {
        console.log("SCE: NF Detectada! Extraindo dados e baixando...");
        clearInterval(escutaAtiva);
        criarBotaoFlutuante();
        setTimeout(extrairDadosSefaz, 1000); 
    }
}, 2000); 

function criarBotaoFlutuante() {
    if(document.getElementById("btn-sce-enviar")) return;
    let btn = document.createElement("button");
    btn.id = "btn-sce-enviar";
    btn.innerHTML = "📥 Forçar Download do JSON";
    btn.style.cssText = "position: fixed; bottom: 20px; right: 20px; z-index: 999999; padding: 15px 20px; background-color: #2E75B6; color: white; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; box-shadow: 0px 4px 6px rgba(0,0,0,0.3);";
    btn.onclick = extrairDadosSefaz;
    document.body.appendChild(btn);
}

function extrairFatorEmbalagem(descricao) {
    const padrao = /(?:C\/|CX\s*\/?|CT\s*\/?|C\s+)\s*(\d+)/i;
    const match = descricao.match(padrao);
    if (match && match[1]) {
        return parseInt(match[1], 10);
    }
    return 1; // Retorna 1 se não encontrar fracionamento
}

function formatarDataBR(valor) {
    if (valor && valor.includes('-')) {
        let p = valor.split('-');
        return `${p[2]}/${p[1]}/${p[0]}`;
    }
    return valor || "";
}

// ─── Múltiplos lotes na mesma linha de produto ────────────────────────────────
//
// Algumas notas resumem mais de um lote físico numa única linha (mesmo
// produto, quantidade total dividida entre lotes diferentes). As funções
// abaixo detectam isso de dois jeitos independentes — o rastro estruturado
// da NFe (repetível por natureza, um bloco por lote) e o texto livre de
// "Informações Adicionais do Produto" (formato observado:
// "Lote: 123 Venc: dd/mm/aaaa Qtd: 10") — e NUNCA inventam quantidade: se
// não há como saber a quantidade de um lote, ela fica null e um aviso é
// disparado (ver resolverLotesMultiplos). O caminho de lote único (0 ou 1
// lote na linha) continua passando pelo código original em extrairDadosSefaz,
// inalterado.

function extrairLotesEstruturados(detalhe) {
    function snapshot(xpath) {
        let resultado = document.evaluate(xpath, detalhe, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
        let nos = [];
        for (let i = 0; i < resultado.snapshotLength; i++) nos.push(resultado.snapshotItem(i));
        return nos;
    }

    let nosLote = snapshot(".//label[contains(text(), 'Número do Lote do produto')]/following-sibling::span");
    if (nosLote.length === 0) return [];

    let nosVal = snapshot(".//label[contains(text(), 'Data de validade')]/following-sibling::span");
    let nosFab = snapshot(".//label[contains(text(), 'Data de fabricação')]/following-sibling::span");
    // Rótulo exato de quantidade por lote ainda não confirmado contra uma nota
    // real com múltiplos lotes estruturados — tentamos as variações mais
    // prováveis; se nenhuma existir, qtd fica null e resolverLotesMultiplos()
    // tenta casar com o texto livre antes de desistir.
    let nosQtd = snapshot(".//label[contains(text(), 'Quantidade do Lote')]/following-sibling::span")
        .concat(snapshot(".//label[contains(text(), 'Qtde do Lote')]/following-sibling::span"));

    return nosLote.map((no, i) => ({
        lote: no.innerText.trim(),
        validade: formatarDataBR(nosVal[i] ? nosVal[i].innerText.trim() : ""),
        fabricacao: formatarDataBR(nosFab[i] ? nosFab[i].innerText.trim() : ""),
        qtd: nosQtd[i] ? parseFloat(nosQtd[i].innerText.replace(/\./g, '').replace(',', '.')) : null,
    }));
}

function extrairLotesTextoLivre(texto) {
    if (!texto) return [];
    // Quebra em blocos a partir de cada ocorrência de "Lote" — não depende do
    // separador usado entre eles (" - ", "|", quebra de linha, etc).
    const blocos = texto.split(/(?=Lote\s*[:\-]?\s*\S)/i)
        .map(b => b.trim())
        .filter(b => /^Lote\s*[:\-]?/i.test(b));

    return blocos.map(bloco => {
        const mLote = bloco.match(/Lote\s*[:\-]?\s*([A-Za-z0-9_\-]+)/i);
        const mFab = bloco.match(/Fab\s*[:\-]?\s*(\d{2}\/\d{2}\/\d{4})/i);
        const mVenc = bloco.match(/(?:Venc|Val)\s*[:\-]?\s*(\d{2}\/\d{2}\/\d{4})/i);
        const mQtd = bloco.match(/Qtd\s*[:\-]?\s*(\d+)/i);
        return {
            lote: mLote ? mLote[1].trim() : null,
            fabricacao: mFab ? mFab[1] : "",
            validade: mVenc ? mVenc[1] : "",
            qtd: mQtd ? parseInt(mQtd[1], 10) : null,
        };
    }).filter(l => l.lote);
}

function obterTextoInfoAdicionalProduto(detalhe) {
    let no = document.evaluate(
        ".//fieldset[contains(@class, 'fieldset-internal')]//label[contains(text(), 'Descrição')]/following-sibling::span",
        detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
    ).singleNodeValue;
    return no ? no.innerText : "";
}

/**
 * Detecta se a linha tem MAIS de um lote (estruturado ou texto livre) e,
 * se tiver, resolve a quantidade de cada um sem nunca inventar número:
 *   1. estruturado já traz a própria quantidade -> usa
 *   2. senão, casa pelo número do lote com o texto livre -> usa
 *   3. senão, fica null + avisa (console.warn + alert)
 * Devolve null se a linha tem só 0 ou 1 lote (deixa o caminho original de
 * extrairDadosSefaz cuidar, sem nenhuma mudança de comportamento).
 */
function resolverLotesMultiplos(detalhe, descricaoProduto) {
    let lotesEstruturados = extrairLotesEstruturados(detalhe);
    let lotesTexto = extrairLotesTextoLivre(obterTextoInfoAdicionalProduto(detalhe));

    let lotes = lotesEstruturados.length > 1 ? lotesEstruturados
        : (lotesTexto.length > 1 ? lotesTexto : null);
    if (!lotes) return null;

    if (lotes === lotesEstruturados) {
        let semQuantidade = [];
        lotes.forEach(l => {
            if (l.qtd === null) {
                let correspondente = lotesTexto.find(t => t.lote === l.lote);
                if (correspondente && correspondente.qtd !== null) {
                    l.qtd = correspondente.qtd;
                } else {
                    semQuantidade.push(l.lote);
                }
            }
        });
        if (semQuantidade.length > 0) {
            let msg = `SCE: Produto "${descricaoProduto}" tem lote(s) sem quantidade identificada: ${semQuantidade.join(', ')}. Confira manualmente na tela de revisão (T-07c) antes de confirmar a entrada.`;
            console.warn(msg);
            alert(msg);
        }
    }

    let somaConhecida = lotes.reduce((acc, l) => l.qtd !== null ? acc + l.qtd : acc, 0);
    let todasConhecidas = lotes.every(l => l.qtd !== null);
    console.log(`SCE: ${lotes.length} lotes detectados em "${descricaoProduto}": ${lotes.map(l => l.lote).join(', ')}.`);

    return { lotes, somaConhecida, todasConhecidas };
}

function extrairDadosSefaz() {
    try {
        let numNfNode = document.querySelector(".fixo-nro-serie span");
        let emitNode = document.evaluate("//div[@id='Emitente']//label[contains(text(), 'Nome / Razão Social')]/following-sibling::span", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        let dataNode = document.evaluate("//div[@id='NFe']//label[contains(text(), 'Data de Emissão')]/following-sibling::span", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        
        let itens = [];
        
        let tbToggles = document.querySelectorAll("#Prod > fieldset > div > table.toggle");
        let tbDetalhes = document.querySelectorAll("#Prod > fieldset > div > table.toggable");
        
        for (let i = 0; i < tbToggles.length; i++) {
            let tr = tbToggles[i].querySelector("tbody tr");
            let detalhe = tbDetalhes[i];
            if (!tr || !detalhe) continue;
            
            // 1. Quantidade, Descrição e Valor Total (Nomes corrigidos!)
            let qtdNode = tr.querySelector(".fixo-prod-serv-qtd span");
            let qtdComercial = qtdNode ? parseFloat(qtdNode.innerText.replace(/\./g, '').replace(',', '.')) : 0;

            let nomeNode = tr.querySelector(".fixo-prod-serv-descricao span");
            let descricaoProduto = nomeNode ? nomeNode.innerText.trim() : "Item sem descrição";
            
            // CORREÇÃO: A classe certa do HTML da Sefaz é .fixo-prod-serv-vb
            let vTotalNode = tr.querySelector(".fixo-prod-serv-vb span");
            let valorTotal = vTotalNode ? parseFloat(vTotalNode.innerText.replace(/\./g, '').replace(',', '.')) : 0;

            // 2. Extração do código e EAN
            let codProdNode= document.evaluate(".//label[contains(text(), 'Código do Produto')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            let codigoProduto = codProdNode ? codProdNode.innerText.trim() : "";
            
            let eanNode = document.evaluate(".//label[contains(text(), 'Código EAN Comercial')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            let eanOriginal= eanNode? eanNode.innerText.trim() : "";

            let eanFinal= eanOriginal;
            if(eanFinal==="" || eanFinal.toUpperCase() ==="SEM GTIN"){
                eanFinal= codigoProduto;
                console.log(`SCE: Produto sem EAN. Substituindo pelo Código Interno: ${eanFinal}`);
            }

            // 3. Unidade e Valor Unitário (Nomes corrigidos!)
            let unidadeNode = document.evaluate(".//label[contains(text(), 'Unidade Comercial')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            let uComercial = unidadeNode ? unidadeNode.innerText.trim() : "CX";

            let vUnNode = document.evaluate(".//label[contains(text(), 'Valor unitário de comercialização')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            let vUnComercial = vUnNode ? parseFloat(vUnNode.innerText.replace(/\./g, '').replace(',', '.')) : 0;
           
            // 4. Validade e Fabricação
            let valNode = document.evaluate(".//label[contains(text(), 'Data de validade')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            let fabNode = document.evaluate(".//label[contains(text(), 'Data de fabricação')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            
            let validade = valNode ? valNode.innerText.trim() : "";
            if (validade && validade.includes('-')) {
                let p = validade.split('-');
                validade = `${p[2]}/${p[1]}/${p[0]}`;
            }

            let fabricacao = fabNode ? fabNode.innerText.trim() : "";
            if (fabricacao && fabricacao.includes('-')) {
                let p = fabricacao.split('-');
                fabricacao = `${p[2]}/${p[1]}/${p[0]}`;
            }
            
            // 5. Lote
            let loteNode = document.evaluate(".//label[contains(text(), 'Número do Lote do produto')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            let loteValor = loteNode ? loteNode.innerText.trim() : "";

            if (!loteValor) {
                let infoAdicionalNode = document.evaluate(".//fieldset[contains(@class, 'fieldset-internal')]//label[contains(text(), 'Descrição')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                
                if (infoAdicionalNode) {
                    let descText = infoAdicionalNode.innerText;
                    let matchLote = descText.match(/Lote\s*[:\-]?\s*([A-Za-z0-9_\-]+)/i);
                    if (matchLote && matchLote[1]) {
                        loteValor = matchLote[1].trim();
                        console.log(`SCE: Lote resgatado das informações adicionais: ${loteValor}`);
                    }
                }
            }

            // 5b. Mais de um lote na mesma linha? (estruturado ou texto livre —
            // ver resolverLotesMultiplos). Se só 0 ou 1 lote, devolve null e o
            // caminho abaixo segue IDÊNTICO ao comportamento original.
            let multiplos = resolverLotesMultiplos(detalhe, descricaoProduto);

            // 6. Cálculos de Fracionamento
            let fator = extrairFatorEmbalagem(descricaoProduto);

            if (valorTotal === 0) valorTotal = qtdComercial * vUnComercial;

            let qtdRealUnidades = Math.round(qtdComercial * fator);
            let vUnReal = qtdRealUnidades > 0 ? Number((valorTotal / qtdRealUnidades).toFixed(4)) : 0;
            let uEstoque = fator > 1 ? "UNID" : uComercial;

            if (eanNode && eanNode.innerText.trim() !== "") {
                if (multiplos) {
                    if (multiplos.todasConhecidas && Math.abs(multiplos.somaConhecida - qtdComercial) > 0.001) {
                        console.warn(`SCE: soma das quantidades dos lotes (${multiplos.somaConhecida}) diverge da quantidade total da linha (${qtdComercial}) em "${descricaoProduto}".`);
                    }
                    multiplos.lotes.forEach(l => {
                        let qtdComercialLote = l.qtd;
                        let qtdRealLote = qtdComercialLote !== null ? Math.round(qtdComercialLote * fator) : null;
                        let valorTotalLote = qtdComercialLote !== null ? Number((vUnComercial * qtdComercialLote).toFixed(4)) : null;
                        let vUnRealLote = (qtdRealLote && qtdRealLote > 0) ? Number((valorTotalLote / qtdRealLote).toFixed(4)) : null;
                        itens.push({
                            descricao: descricaoProduto,
                            ean: eanFinal,
                            quantidade: qtdRealLote,
                            valor_unitario: vUnRealLote,
                            unidade_estoque: uEstoque,
                            valor_total: valorTotalLote,
                            fator_fracionamento: fator,
                            quantidade_comercial: qtdComercialLote,
                            unidade_comercial: uComercial,
                            lote: l.lote,
                            validade: l.validade || validade,
                            fabricacao: l.fabricacao || fabricacao,
                        });
                    });
                } else {
                    itens.push({
                        descricao: descricaoProduto,
                        ean: eanFinal,
                        quantidade: qtdRealUnidades,
                        valor_unitario: vUnReal,
                        unidade_estoque: uEstoque,
                        valor_total: valorTotal,
                        fator_fracionamento: fator,
                        quantidade_comercial: qtdComercial,
                        unidade_comercial: uComercial,
                        lote: loteValor,
                        validade: validade,
                        fabricacao: fabricacao,
                    });
                }
            }
        }

        let dados = {
            identificador_sce: "NF_ENTRADA",
            numero_nf: numNfNode ? numNfNode.innerText.trim() : "NAO_ENCONTRADO",
            nome_emitente: emitNode ? emitNode.innerText.trim() : "",
            data_emissao: dataNode ? dataNode.innerText.substring(0, 10) : "",
            itens: itens
        };

        const blob = new Blob([JSON.stringify(dados, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        let dataHoraStr = new Date().toISOString().replace(/[:.]/g, '-');
        
        a.href = url;
        a.download = `sce_nf_${dados.numero_nf}_${dataHoraStr}.json`; 
        document.body.appendChild(a);
        a.click(); 
        
        setTimeout(() => {
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        }, 100);

        let btn = document.getElementById("btn-sce-enviar");
        if (btn) {
            btn.innerHTML = "✅ Arquivo JSON Baixado!";
            btn.style.backgroundColor = "#1D9E75";
        }

    } catch (error) {
        console.error("Erro geral na extração da NF:", error);
        alert("Falha na extensão SCE. Verifique o console do navegador (F12).");
    }
}