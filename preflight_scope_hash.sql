-- Unico valor que falta para completar structured_result.scope_hash --
-- READ ONLY, calcula via a funcao REAL do servidor, nunca reproduzido a mao.
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT b02_json_hash(scope) AS scope_hash_real
FROM public.policy_versions
WHERE policy_id='SOLVERIS-B02-SEFA-PR-DOCUMENTARY-AUTHORITY'
  AND policy_hash='05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a';
ROLLBACK;
