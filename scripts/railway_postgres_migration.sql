-- Migração PostgreSQL (Railway)
-- Ajusta o schema para alinhar com os modelos do código.
-- Execução: Railway → Postgres → Data → Query
--
-- Contexto:
-- - usuarios.consulta_paga: usado para controle de consultas pagas
-- - empresas.regime_tributario: usado pelo scheduler e engines fiscais

-- Passo 1 — Corrigir schema (coluna regime_tributario)
ALTER TABLE empresas
ADD COLUMN IF NOT EXISTS regime_tributario VARCHAR(50);

-- Coluna consulta_paga (opcional, se ainda não existir)
ALTER TABLE usuarios
ADD COLUMN IF NOT EXISTS consulta_paga BOOLEAN DEFAULT FALSE;
