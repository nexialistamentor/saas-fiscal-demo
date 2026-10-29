/* Candidate only: actual Ed25519 verification against COMPILED approved roots.
 * Pure assertion, no authority issuance, DB writes, key files, environment keys,
 * runtime root injection or production test-key fallback. The real registry is
 * EMPTY. Linking with the unchanged precommit hook does not remove the 0064 veto.
 */
#include "postgres.h"
#include "fmgr.h"
#include "utils/builtins.h"
#include "utils/fmgrprotos.h"
#include "utils/jsonb.h"
#include "utils/timestamp.h"
#include <openssl/evp.h>

PG_FUNCTION_INFO_V1(b02g5_assert_signature);
PG_FUNCTION_INFO_V1(b02g5_native_profile);

#define B02_G5_MAX_MESSAGE_BYTES (1024 * 1024)
#define B02_G5_MAX_KEY_ID_BYTES 128

typedef struct B02G5NativeRoot
{
    const char *key_id;
    const unsigned char public_key[32];
    /* Immutable exact subject/activation/verifier/scope/profile constraints. */
    const char *constraints_json;
    const char *valid_from;
    const char *valid_until;
} B02G5NativeRoot;

#ifdef B02_G5_TEST_PROFILE
#include "b02_g5_fixture_roots.h"
#else
#include "b02_g5_approved_roots.h"
#endif

static void
b02g5_signature_denied(const char *code)
{
    ereport(ERROR,
            (errcode(ERRCODE_CHECK_VIOLATION),
             errmsg_internal("%s", code)));
}

static JsonbValue *
b02g5_json_field(Jsonb *object, const char *name)
{
    JsonbValue key;
    key.type = jbvString;
    key.val.string.val = (char *) name;
    key.val.string.len = strlen(name);
    return findJsonbValueFromContainer(&object->root, JB_FOBJECT, &key);
}

static TimestampTz
b02g5_manifest_time(Jsonb *manifest, const char *field)
{
    JsonbValue *value = b02g5_json_field(manifest, field);
    TimestampTz stamp;
    const char *raw;
    int len;
    if (value == NULL || value->type != jbvString || value->val.string.len == 0 ||
        value->val.string.len > 128)
        b02g5_signature_denied("G5_NATIVE_MANIFEST_TIME_REQUIRED");
    raw = value->val.string.val;
    len = value->val.string.len;
    /* No session-TimeZone-dependent, relative or timezone-free timestamps. */
    if (len < 20 || raw[4] != '-' || raw[7] != '-' || raw[10] != 'T' ||
        raw[13] != ':' || raw[16] != ':' ||
        !(raw[len - 1] == 'Z' ||
          (len >= 25 && (raw[len - 6] == '+' || raw[len - 6] == '-') &&
           raw[len - 3] == ':' && raw[len - 5] >= '0' && raw[len - 5] <= '9' &&
           raw[len - 4] >= '0' && raw[len - 4] <= '9' &&
           raw[len - 2] >= '0' && raw[len - 2] <= '9' &&
           raw[len - 1] >= '0' && raw[len - 1] <= '9')))
        b02g5_signature_denied("G5_NATIVE_EXPLICIT_TIMEZONE_REQUIRED");
    stamp = DatumGetTimestampTz(DirectFunctionCall3(timestamptz_in,
        CStringGetDatum(pnstrdup(value->val.string.val, value->val.string.len)),
        ObjectIdGetDatum(InvalidOid), Int32GetDatum(-1)));
    if (TIMESTAMP_NOT_FINITE(stamp))
        b02g5_signature_denied("G5_NATIVE_MANIFEST_TIME_INVALID");
    return stamp;
}

static void
b02g5_exact_object_field(Jsonb *manifest, Jsonb *constraints, const char *field)
{
    JsonbValue *value = b02g5_json_field(manifest, field);
    JsonbValue *required = b02g5_json_field(constraints, field);
    Jsonb *actual_json;
    Jsonb *required_json;
    if (value == NULL || required == NULL || value->type != jbvBinary ||
        required->type != jbvBinary)
        b02g5_signature_denied("G5_NATIVE_ROOT_EXACT_BINDING_REQUIRED");
    actual_json = JsonbValueToJsonb(value);
    required_json = JsonbValueToJsonb(required);
    if (!JB_ROOT_IS_OBJECT(actual_json) || !JB_ROOT_IS_OBJECT(required_json) ||
        compareJsonbContainers(&actual_json->root, &required_json->root) != 0)
        b02g5_signature_denied("G5_NATIVE_ROOT_EXACT_BINDING_DIVERGENCE");
}

Datum
b02g5_native_profile(PG_FUNCTION_ARGS)
{
#ifdef B02_G5_TEST_PROFILE
    PG_RETURN_TEXT_P(cstring_to_text("SYNTHETIC_TEST_PROFILE_NOT_INSTITUTIONAL_AUTHORITY"));
#else
    PG_RETURN_TEXT_P(cstring_to_text(B02_G5_NATIVE_ROOT_COUNT == 0 ?
        "REAL_PROFILE_NO_APPROVED_ROOTS" : "REAL_PROFILE_COMPILED_APPROVED_ROOTS"));
#endif
}

Datum
b02g5_assert_signature(PG_FUNCTION_ARGS)
{
    bytea *expected;
    bytea *message;
    bytea *signature;
    text *key_text;
    Size expected_size, message_size, signature_size, key_size;
    char *key_id;
    Jsonb *manifest;
    Jsonb *constraints;
    JsonbValue *synthetic;
    const B02G5NativeRoot *root = NULL;
    Size i;
    const Size root_count = B02_G5_NATIVE_ROOT_COUNT;
    TimestampTz root_start, root_end, start, end, now;
    EVP_PKEY *public_key = NULL;
    EVP_MD_CTX *verify_context = NULL;
    int verified = 0;

    /* Deliberately NOT SQL STRICT: NULL cannot become an unchecked success. */
    for (i = 0; i < 4; ++i)
        if (PG_ARGISNULL(i))
            b02g5_signature_denied("G5_NATIVE_SIGNATURE_ARGUMENT_REQUIRED");

    expected = PG_GETARG_BYTEA_PP(0);
    message = PG_GETARG_BYTEA_PP(1);
    signature = PG_GETARG_BYTEA_PP(2);
    key_text = PG_GETARG_TEXT_PP(3);
    expected_size = VARSIZE_ANY_EXHDR(expected);
    message_size = VARSIZE_ANY_EXHDR(message);
    signature_size = VARSIZE_ANY_EXHDR(signature);
    key_size = VARSIZE_ANY_EXHDR(key_text);

    if (expected_size == 0 || expected_size > B02_G5_MAX_MESSAGE_BYTES ||
        message_size == 0 || message_size > B02_G5_MAX_MESSAGE_BYTES ||
        key_size == 0 || key_size > B02_G5_MAX_KEY_ID_BYTES ||
        signature_size != 64)
        b02g5_signature_denied("G5_NATIVE_SIGNATURE_INPUT_INVALID");

    /* This is always first, before root lookup or any cryptographic approval.
     * The mandatory server validator supplies expected from actual DB rows;
     * a direct caller supplying both values gains no authority from this API.
     */
    if (expected_size != message_size ||
        memcmp(VARDATA_ANY(expected), VARDATA_ANY(message), expected_size) != 0)
        b02g5_signature_denied("G5_NATIVE_EXPECTED_BYTES_DIVERGENCE");
    if (memchr(VARDATA_ANY(message), '\0', message_size) != NULL ||
        memchr(VARDATA_ANY(key_text), '\0', key_size) != NULL)
        b02g5_signature_denied("G5_NATIVE_SIGNATURE_INPUT_INVALID");

    key_id = text_to_cstring(key_text);
    for (i = 0; i < root_count; ++i)
    {
        if (strcmp(key_id, b02_g5_native_roots[i].key_id) == 0)
        {
            /* Duplicate compiled IDs are a deployment error, never first-wins. */
            if (root != NULL)
                b02g5_signature_denied("G5_NATIVE_ROOT_AMBIGUOUS");
            root = &b02_g5_native_roots[i];
        }
    }
    if (root == NULL)
        b02g5_signature_denied("G5_NATIVE_ROOT_NOT_APPROVED");

    manifest = DatumGetJsonbP(DirectFunctionCall1(jsonb_in,
        CStringGetDatum(pnstrdup(VARDATA_ANY(message), message_size))));
    if (!JB_ROOT_IS_OBJECT(manifest))
        b02g5_signature_denied("G5_NATIVE_SIGNED_OBJECT_REQUIRED");
    synthetic = b02g5_json_field(manifest, "synthetic_only");
    if (synthetic == NULL || synthetic->type != jbvBool)
        b02g5_signature_denied("G5_NATIVE_EXPLICIT_PROFILE_REQUIRED");
#ifdef B02_G5_TEST_PROFILE
    if (!synthetic->val.boolean)
        b02g5_signature_denied("G5_NATIVE_SYNTHETIC_PROFILE_REQUIRED");
#else
    if (synthetic->val.boolean)
        b02g5_signature_denied("G5_NATIVE_REAL_PROFILE_REQUIRED");
#endif

    /* Scope is not inferred from the key name or from a client's verified flag.
     * Each approved root pins the exact full policy/activation/ratification and
     * V2 verifier identities inside the server-recomputed signed bytes.
     */
    if (root->constraints_json == NULL)
        b02g5_signature_denied("G5_NATIVE_ROOT_CONSTRAINTS_MISSING");
    constraints = DatumGetJsonbP(DirectFunctionCall1(jsonb_in,
        CStringGetDatum(root->constraints_json)));
    if (!JB_ROOT_IS_OBJECT(constraints) ||
        !DatumGetBool(DirectFunctionCall2(jsonb_contains,
                         JsonbPGetDatum(manifest), JsonbPGetDatum(constraints))))
        b02g5_signature_denied("G5_NATIVE_ROOT_CONSTRAINT_DIVERGENCE");

    b02g5_exact_object_field(manifest, constraints, "g5_policy_binding");
    b02g5_exact_object_field(manifest, constraints, "g4_verifier");
    if (root->valid_from == NULL || root->valid_until == NULL)
        b02g5_signature_denied("G5_NATIVE_ROOT_VALIDITY_REQUIRED");
    root_start = DatumGetTimestampTz(DirectFunctionCall3(timestamptz_in,
        CStringGetDatum(root->valid_from), ObjectIdGetDatum(InvalidOid), Int32GetDatum(-1)));
    root_end = DatumGetTimestampTz(DirectFunctionCall3(timestamptz_in,
        CStringGetDatum(root->valid_until), ObjectIdGetDatum(InvalidOid), Int32GetDatum(-1)));
    start = b02g5_manifest_time(manifest, "valid_from");
    end = b02g5_manifest_time(manifest, "valid_until");
    now = GetCurrentTimestamp();
    if (TIMESTAMP_NOT_FINITE(root_start) || TIMESTAMP_NOT_FINITE(root_end) ||
        !(root_start <= start && start <= now && now < end && end <= root_end))
        b02g5_signature_denied("G5_NATIVE_CAPABILITY_OR_MANDATE_NOT_CURRENT");

    public_key = EVP_PKEY_new_raw_public_key(EVP_PKEY_ED25519, NULL,
                                             root->public_key, 32);
    if (public_key != NULL)
        verify_context = EVP_MD_CTX_new();
    if (verify_context != NULL &&
        EVP_DigestVerifyInit(verify_context, NULL, NULL, NULL, public_key) == 1)
        verified = EVP_DigestVerify(verify_context,
            (const unsigned char *) VARDATA_ANY(signature), signature_size,
            (const unsigned char *) VARDATA_ANY(message), message_size);
    if (verify_context != NULL)
        EVP_MD_CTX_free(verify_context);
    if (public_key != NULL)
        EVP_PKEY_free(public_key);
    if (verified != 1)
        b02g5_signature_denied("G5_NATIVE_SIGNATURE_INVALID");

    PG_RETURN_VOID();
}
