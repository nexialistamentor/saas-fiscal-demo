# Receitas informadas — smoke integrado — 2026-10-08

Revisão testada: 7ad9f7e6ca80b237261867789f9be148065aaf10.

Componente React no navegador → rotas reais FastAPI → PostgreSQL 17 local.
Autenticação JWT e isolamento por empresa reais; dados sintéticos.

PASS:
- Migração Alembic até 0059 e guardas HTTP 401/403.
- Desktop 1280px e celular 390px.
- Registro, leitura de totais e troca de ano.
- POST realmente persistido com confirmação descartada no navegador.
- Reload e recuperação com a mesma identidade, sem duplicação.
- Erro 503 injetado no navegador remove o total anterior.
- Troca de empresa não apresenta dados da empresa anterior.
- PostgreSQL: quatro registros; duas empresas com 100.30 cada.
- Nenhum registro nas demais empresas.
- Worktree preservada e container descartável removido.

Limites:
- Não testa o login completo nem a inicialização de app.main.
- O componente é montado em uma página temporária de teste.
- Produção não acessada; pagamentos e provedores não chamados.
- Não comprova completude anual ou regularidade fiscal.

O executor está fixado na revisão testada e exige worktree limpa.
Os caracteres acentuados exibidos incorretamente no terminal não impediram
as verificações do navegador, das respostas HTTP ou dos valores no banco.