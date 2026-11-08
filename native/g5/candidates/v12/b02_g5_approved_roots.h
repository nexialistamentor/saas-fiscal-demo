/* SOLVERIS B02 G5 V12 — CANDIDATE ONLY. NOT APPROVED OR INSTALLED.
 * This is a policy-specific native trust-root proposal for the isolated
 * solveris-b02-v7-isolado clone. Historical headers and migrations untouched.
 * Public Ed25519 key reused; no private keys or credentials included.
 * Confirm physical V12 bindings, local operator time limits and native build
 * before any decision to install. Does not itself issue authority.
 */
static const B02G5NativeRoot b02_g5_native_roots[] = {
 { "SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V1", { 0xab, 0x8d, 0xc9, 0x26, 0x51, 0x20, 0x61, 0xfe, 0xe3, 0x70, 0xdf, 0xca, 0xbc, 0x5f, 0x11, 0x75, 0x22, 0x29, 0xc6, 0x58, 0x35, 0x46, 0xa6, 0x55, 0x92, 0xc9, 0x7c, 0xe2, 0x4c, 0x6a, 0xe3, 0x81 },
   "{\"schema\":\"B02_G5_TX_RELEASE_V1\",\"audit_scope\":\"SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE\",\"synthetic_only\":false,\"capability_root_id\":\"SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V1\",\"release_policy_hash\":\"727acdbb8ba0775f73100ea86671bc30bbac58b5af22a99b6be595d50268fab9\",\"g5_policy_binding\":{\"policy_type\":\"activation_authority\",\"policy_id\":\"SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE\",\"policy_version\":12,\"policy_hash\":\"727acdbb8ba0775f73100ea86671bc30bbac58b5af22a99b6be595d50268fab9\",\"decision_id\":\"B02-727acdbb-ratificada-v1\",\"decision_hash\":\"f66e30b5b799e4be3fb7423ba89373a74fae46cdf565a542869ea873d8ca72eb\",\"policy_activation_id\":\"B02-727acdbb-activation-v1\",\"policy_activation_record_hash\":\"a9be2383bd771864d94b23ae2ad2fbab5547d38cba9ef6b746785af507cdfc39\"},\"g4_verifier\":{\"id\":\"SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN\",\"version\":\"1\",\"hash\":\"fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472\"},\"server\":{\"system_identifier\":\"7705464689253724199\",\"database_oid\":16384,\"database_name\":\"solveris_b02_r4g_test\",\"writer_oid\":16390,\"writer_name\":\"solveris_b02_writer\"},\"documents\":[{\"id\":\"101201900571\",\"sha256\":\"af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d\",\"byte_size\":1944929},{\"id\":\"101202501245\",\"sha256\":\"e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832\",\"byte_size\":258302}]}",
   "2026-11-01T00:00:00+00:00", "2026-11-15T00:00:00+00:00" }
};
#define B02_G5_NATIVE_ROOT_COUNT ((Size) 1)
