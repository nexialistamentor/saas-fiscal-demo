/* SOLVERIS B02 G5 V8-REAL — CANDIDATE ONLY. NOT APPROVED OR INSTALLED.
 * Native trust-root proposal for the real base solveris-pg17-migration-test
 * (database solveris_b02_r4g_test, porta 55432). Corpo da politica identico
 * ao validado e testado como v12 no isolado solveris-b02-v7-isolado, mas
 * reativado na base real diretamente como v8 (ver policy_decisions.rationale
 * de B02-9d115d33-ratificada-v1 para historico completo).
 * Public Ed25519 key reused; no private keys or credentials included.
 */
static const B02G5NativeRoot b02_g5_native_roots[] = {
 { "SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V1", { 0xab, 0x8d, 0xc9, 0x26, 0x51, 0x20, 0x61, 0xfe, 0xe3, 0x70, 0xdf, 0xca, 0xbc, 0x5f, 0x11, 0x75, 0x22, 0x29, 0xc6, 0x58, 0x35, 0x46, 0xa6, 0x55, 0x92, 0xc9, 0x7c, 0xe2, 0x4c, 0x6a, 0xe3, 0x81 },
   "{\"schema\":\"B02_G5_TX_RELEASE_V1\",\"audit_scope\":\"SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE\",\"synthetic_only\":false,\"capability_root_id\":\"SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V1\",\"release_policy_hash\":\"9d115d33cd73f4cd59d5621d1fcd2b30ab1d08edac148284cb1a1cb590750ab9\",\"g5_policy_binding\":{\"policy_type\":\"activation_authority\",\"policy_id\":\"SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE\",\"policy_version\":8,\"policy_hash\":\"9d115d33cd73f4cd59d5621d1fcd2b30ab1d08edac148284cb1a1cb590750ab9\",\"decision_id\":\"B02-9d115d33-ratificada-v1\",\"decision_hash\":\"40c53100fa10f492599c15c780e932a1920d58fcd926db001d403dd3dd850525\",\"policy_activation_id\":\"B02-9d115d33-activation-v1\",\"policy_activation_record_hash\":\"6eb2f3e02b58d2d37cebb82fc3aaca9625d21b20d619faf8f280fdd4074e0f2a\"},\"g4_verifier\":{\"id\":\"SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN\",\"version\":\"1\",\"hash\":\"fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472\"},\"server\":{\"system_identifier\":\"7688884600396267558\",\"database_oid\":40962,\"database_name\":\"solveris_b02_r4g_test\",\"writer_oid\":40961,\"writer_name\":\"solveris_b02_writer\"},\"documents\":[{\"id\":\"101201900571\",\"sha256\":\"af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d\",\"byte_size\":1944929},{\"id\":\"101202501245\",\"sha256\":\"e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832\",\"byte_size\":258302}]}",
   "2026-11-01T00:00:00+00:00", "2026-11-15T00:00:00+00:00" }
};
#define B02_G5_NATIVE_ROOT_COUNT ((Size) 1)