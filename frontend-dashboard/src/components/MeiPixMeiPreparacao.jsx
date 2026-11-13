import { useState } from 'react'

const ITENS = [
  { id: 'cadastro', descricao: 'Conferi meus dados cadastrais nos canais oficiais.' },
  { id: 'situacao', descricao: 'Verifiquei a situação do CNPJ do MEI no serviço oficial.' },
  { id: 'receitas', descricao: 'Organizei meus registros de faturamento anual, sem pressupor elegibilidade.' },
  { id: 'investimento', descricao: 'Anotei quais ferramentas ou equipamentos ajudariam meu negócio.' },
]

function storageKey(empresaId) {
  return `solveris.mei.pixmei.preparacao.v1:${empresaId}`
}

function carregarMarcacoes(empresaId) {
  try {
    const dados = JSON.parse(window.localStorage.getItem(storageKey(empresaId)) || '{}')
    if (!dados || typeof dados !== 'object' || Array.isArray(dados)) return {}
    return Object.fromEntries(ITENS.map(item => [item.id, dados[item.id] === true]))
  } catch {
    return {}
  }
}

export default function MeiPixMeiPreparacao({ empresaId }) {
  const [marcacoes, setMarcacoes] = useState(() => carregarMarcacoes(empresaId))
  const [podeGuardar, setPodeGuardar] = useState(true)

  function marcar(id, marcado) {
    const proximas = { ...marcacoes, [id]: marcado }
    setMarcacoes(proximas)
    try {
      window.localStorage.setItem(storageKey(empresaId), JSON.stringify(proximas))
      setPodeGuardar(true)
    } catch {
      setPodeGuardar(false)
    }
  }

  const concluidos = ITENS.filter(item => marcacoes[item.id]).length
  return (
    <section className="card" aria-labelledby="pixmei-preparacao-titulo"
      style={{ marginBottom: 20, overflowWrap: 'anywhere' }}>
      <h3 id="pixmei-preparacao-titulo">Preparação PixMEI — informações e checklist</h3>
      <p><strong>Inscrições ainda não abertas.</strong> O PixMEI é uma proposta
        do Ministério do Empreendedorismo de apoio produtivo de até R$ 5 mil;
        os valores individuais e os critérios finais ainda não publicados
        dependem de edital oficial. Não há garantia de recebimento.</p>
      <p>
        O Ministério divulgou como prioridade em estudo mulheres empreendedoras
        com faturamento de até R$ 40.500 por ano. Isso ainda não constitui
        critério definitivo, pré-seleção nem aprovação.
      </p>
      <p><strong>A SOLVERIS não processa inscrições nem garante acesso ao benefício.</strong>
        Esta área é exclusivamente de preparação: não solicita dados bancários,
        não oferece vaga e não substitui os canais oficiais.</p>
      <h4>Organize-se para consultar as regras quando saírem</h4>
      <p style={{ fontSize: 13, marginTop: 0 }}>
        Marque o que já conferiu. As marcações ficam apenas neste navegador,
        sem envio de dados à SOLVERIS ou ao governo.
      </p>
      <div role="group" aria-label="Checklist local de preparação PixMEI"
        style={{ display: 'grid', gap: 12, marginBottom: 14 }}>
        {ITENS.map(item => (
          <label key={item.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <input type="checkbox" checked={marcacoes[item.id] === true}
              onChange={event => marcar(item.id, event.target.checked)} />
            <span>{item.descricao}</span>
          </label>
        ))}
      </div>
      <p role="status" style={{ fontSize: 13 }}>
        Organização pessoal: {concluidos} de {ITENS.length} itens marcados.
        {!podeGuardar && ' O navegador não permitiu guardar as marcações.'}
      </p>
      <p><strong>Avisos automáticos ainda indisponíveis</strong> na SOLVERIS.
        Acompanhe o edital e as inscrições, quando anunciadas, diretamente no Ministério.</p>
      <a href="https://www.gov.br/memp/pt-br/prospera-mei/pixmei"
        target="_blank" rel="noopener noreferrer">Acompanhar a situação oficial do PixMEI</a>
      <p style={{ fontSize: 12, marginTop: 12 }}>
        Informação oficial conferida em 13/11/2026. Desconfie de cobranças
        antecipadas, solicitações de chave Pix e promessas de liberação imediata.
      </p>
    </section>
  )
}
