import re

path = r"C:\dev\solveris-b02-g5-v5-publicacao\native\g5\historical_20261022\b02_g5_approved_roots.h"
with open(path, encoding="utf-8") as f:
    content = f.read()

constraints_json = r'{\"audit_scope\":\"SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE\",\"capability_root_id\":\"SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V2\",\"documents\":[{\"byte_size\":1944929,\"id\":\"101201900571\",\"sha256\":\"af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d\"},{\"byte_size\":258302,\"id\":\"101202501245\",\"sha256\":\"e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832\"}],\"g4_verifier\":{\"hash\":\"fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472\",\"id\":\"SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN\",\"version\":\"1\"},\"g5_policy_binding\":{\"decision_hash\":\"29b7d2e98abb876bb472f3ef67deec7056dfe8aa9fe0d960ae03e6bd5e1e77d6\",\"decision_id\":\"B02-389cce04-ratificada-v1\",\"policy_activation_id\":\"B02-389cce04-activation-v1\",\"policy_activation_record_hash\":\"6b495c284eb9d86c75a29ae0ae705603428daa45933a307786692a52cf7af5b8\",\"policy_hash\":\"389cce04dd249c5fb184fce7b876608651dd84ca3db64b7d778bb2de66a0c3d2\",\"policy_id\":\"SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE\",\"policy_type\":\"activation_authority\",\"policy_version\":3},\"release_policy_hash\":\"389cce04dd249c5fb184fce7b876608651dd84ca3db64b7d778bb2de66a0c3d2\",\"schema\":\"B02_G5_TX_RELEASE_V1\",\"server\":{\"database_name\":\"solveris_b02_r4g_test\",\"database_oid\":40962,\"system_identifier\":\"7688884600396267558\",\"writer_name\":\"solveris_b02_writer\",\"writer_oid\":40961},\"synthetic_only\":false}'

new_entry = ('{ "SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V2", '
    '{ 0xab, 0x8d, 0xc9, 0x26, 0x51, 0x20, 0x61, 0xfe, 0xe3, 0x70, 0xdf, 0xca, 0xbc, 0x5f, 0x11, 0x75, '
    '0x22, 0x29, 0xc6, 0x58, 0x35, 0x46, 0xa6, 0x55, 0x92, 0xc9, 0x7c, 0xe2, 0x4c, 0x6a, 0xe3, 0x81 }, '
    '"' + constraints_json + '", '
    '"2026-11-05T00:00:00+00:00", "2036-11-05T00:00:00+00:00" }')

old_array = '''static const B02G5NativeRoot b02_g5_native_roots[] = {
 { "SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V1", { 0xab, 0x8d, 0xc9, 0x26, 0x51, 0x20, 0x61, 0xfe, 0xe3, 0x70, 0xdf, 0xca, 0xbc, 0x5f, 0x11, 0x75, 0x22, 0x29, 0xc6, 0x58, 0x35, 0x46, 0xa6, 0x55, 0x92, 0xc9, 0x7c, 0xe2, 0x4c, 0x6a, 0xe3, 0x81 }, "{\\"audit_scope\\":\\"SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE\\",\\"capability_root_id\\":\\"SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V1\\",\\"documents\\":[{\\"byte_size\\":1944929,\\"id\\":\\"101201900571\\",\\"sha256\\":\\"af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d\\"},{\\"byte_size\\":258302,\\"id\\":\\"101202501245\\",\\"sha256\\":\\"e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832\\"}],\\"g4_verifier\\":{\\"hash\\":\\"fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472\\",\\"id\\":\\"SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN\\",\\"version\\":\\"1\\"},\\"g5_policy_binding\\":{\\"decision_hash\\":\\"458150c4a74db845a2619f4717ffe16eb756e7988c819f4a864e62d68d541342\\",\\"decision_id\\":\\"B02-57982-ratificada-v1\\",\\"policy_activation_id\\":\\"B02-57982-activation-v1\\",\\"policy_activation_record_hash\\":\\"0ccc9f90b9f338d14548189d48612e220b3b7b673e9e99c5aa55a9b4cdfb0ac2\\",\\"policy_hash\\":\\"57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa\\",\\"policy_id\\":\\"SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE\\",\\"policy_type\\":\\"activation_authority\\",\\"policy_version\\":1},\\"release_policy_hash\\":\\"57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa\\",\\"schema\\":\\"B02_G5_TX_RELEASE_V1\\",\\"server\\":{\\"database_name\\":\\"solveris_b02_r4g_test\\",\\"database_oid\\":40962,\\"system_identifier\\":\\"7688884600396267558\\",\\"writer_name\\":\\"solveris_b02_writer\\",\\"writer_oid\\":40961},\\"synthetic_only\\":false}", "2026-10-22T12:00:00+00:00", "2026-10-23T07:56:30.910737+00:00" }
};
#define B02_G5_NATIVE_ROOT_COUNT ((Size) 1)'''

new_array = ('static const B02G5NativeRoot b02_g5_native_roots[] = {\n'
    ' { "SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V1", { 0xab, 0x8d, 0xc9, 0x26, 0x51, 0x20, 0x61, 0xfe, 0xe3, 0x70, 0xdf, 0xca, 0xbc, 0x5f, 0x11, 0x75, 0x22, 0x29, 0xc6, 0x58, 0x35, 0x46, 0xa6, 0x55, 0x92, 0xc9, 0x7c, 0xe2, 0x4c, 0x6a, 0xe3, 0x81 }, "{\\\\"audit_scope\\\\":\\\\"SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE\\\\",\\\\"capability_root_id\\\\":\\\\"SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V1\\\\",\\\\"documents\\\\":[{\\\\"byte_size\\\\":1944929,\\\\"id\\\\":\\\\"101201900571\\\\",\\\\"sha256\\\\":\\\\"af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d\\\\"},{\\\\"byte_size\\\\":258302,\\\\"id\\\\":\\\\"101202501245\\\\",\\\\"sha256\\\\":\\\\"e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832\\\\"}],\\\\"g4_verifier\\\\":{\\\\"hash\\\\":\\\\"fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472\\\\",\\\\"id\\\\":\\\\"SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN\\\\",\\\\"version\\\\":\\\\"1\\\\"},\\\\"g5_policy_binding\\\\":{\\\\"decision_hash\\\\":\\\\"458150c4a74db845a2619f4717ffe16eb756e7988c819f4a864e62d68d541342\\\\",\\\\"decision_id\\\\":\\\\"B02-57982-ratificada-v1\\\\",\\\\"policy_activation_id\\\\":\\\\"B02-57982-activation-v1\\\\",\\\\"policy_activation_record_hash\\\\":\\\\"0ccc9f90b9f338d14548189d48612e220b3b7b673e9e99c5aa55a9b4cdfb0ac2\\\\",\\\\"policy_hash\\\\":\\\\"57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa\\\\",\\\\"policy_id\\\\":\\\\"SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE\\\\",\\\\"policy_type\\\\":\\\\"activation_authority\\\\",\\\\"policy_version\\\\":1},\\\\"release_policy_hash\\\\":\\\\"57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa\\\\",\\\\"schema\\\\":\\\\"B02_G5_TX_RELEASE_V1\\\\",\\\\"server\\\\":{\\\\"database_name\\\\":\\\\"solveris_b02_r4g_test\\\\",\\\\"database_oid\\\\":40962,\\\\"system_identifier\\\\":\\\\"7688884600396267558\\\\",\\\\"writer_name\\\\":\\\\"solveris_b02_writer\\\\",\\\\"writer_oid\\\\":40961},\\\\"synthetic_only\\\\":false}", "2026-10-22T12:00:00+00:00", "2026-10-23T07:56:30.910737+00:00" },\n'
    ' ' + new_entry + '\n'
    '};\n'
    '#define B02_G5_NATIVE_ROOT_COUNT ((Size) 2)')

if old_array not in content:
    raise SystemExit("OLD_ARRAY_NOT_FOUND")
content = content.replace(old_array, new_array)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("PATCHED, root count now 2")
