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
            
            let qtdNode = tr.querySelector(".fixo-prod-serv-qtd span");
            let qtd = qtdNode ? parseFloat(qtdNode.innerText.replace(/\./g, '').replace(',', '.')) : 0;

            let nomeNode = tr.querySelector(".fixo-prod-serv-descricao span");
            let descricaoProduto = nomeNode ? nomeNode.innerText.trim() : "Item sem descrição";
            
            let eanNode = document.evaluate(".//label[contains(text(), 'Código EAN Comercial')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            let unidadeNode = document.evaluate(".//label[contains(text(), 'Unidade Comercial')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            let vUnNode = document.evaluate(".//label[contains(text(), 'Valor unitário de comercialização')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            let vUn = vUnNode ? parseFloat(vUnNode.innerText.replace(/\./g, '').replace(',', '.')) : 0;
           
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
            
            // --- NOVA LÓGICA CORRIGIDA PARA EXTRAÇÃO DE LOTE ---
            let loteNode = document.evaluate(".//label[contains(text(), 'Número do Lote do produto')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
            let loteValor = loteNode ? loteNode.innerText.trim() : "";

            if (!loteValor) {
                // Busca especificamente na tabela de "Informações adicionais do produto" (ignora o nome do produto no topo)
                let infoAdicionalNode = document.evaluate(".//fieldset[contains(@class, 'fieldset-internal')]//label[contains(text(), 'Descrição')]/following-sibling::span", detalhe, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                
                if (infoAdicionalNode) {
                    let descText = infoAdicionalNode.innerText;
                    // Procura o padrão "Lote:" ou "LOTE " seguido de letras/números
                    let matchLote = descText.match(/Lote\s*[:\-]?\s*([A-Za-z0-9_\-]+)/i);
                    if (matchLote && matchLote[1]) {
                        loteValor = matchLote[1].trim();
                        console.log(`SCE: Lote resgatado das informações adicionais: ${loteValor}`);
                    }
                }
            }
            // ----------------------------------------------------

            if (eanNode && eanNode.innerText.trim() !== "") {
                itens.push({
                    descricao: descricaoProduto,
                    ean: eanNode.innerText.trim(),
                    quantidade: qtd,
                    valor_unitario: vUn,
                    lote: loteValor, 
                    validade: validade,
                    fabricacao: fabricacao,
                    unidade_estoque: unidadeNode ? unidadeNode.innerText.trim() : ""
                });
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