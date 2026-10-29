/*
 * B02 candidate only: non-anticipatable PRE_COMMIT validation for real units.
 * No authority, policy, signing key, data or database is provisioned here.
 * The fixed SQL validator must perform only locks, reads and rejection.
 */
#include "postgres.h"
#include "fmgr.h"
#include "access/htup_details.h"
#include "access/xact.h"
#include "commands/trigger.h"
#include "catalog/pg_namespace_d.h"
#include "catalog/pg_type_d.h"
#include "executor/spi.h"
#include "utils/jsonb.h"
#include "utils/rel.h"
#include "utils/snapmgr.h"

PG_MODULE_MAGIC;

PGDLLEXPORT void _PG_init(void);
PG_FUNCTION_INFO_V1(b02g5_register_real_precommit);

/* Callback is backend lifetime; arming is top-level transaction lifetime. */
static bool callback_registered = false;
static bool real_guard_armed = false;
static bool callback_running = false;

static void
b02g5_xact_callback(XactEvent event, void *arg)
{
    volatile bool spi_connected = false;
    volatile bool snapshot_pushed = false;
    int rc;

    (void) arg;
    /* Never reset at a subtransaction boundary: a savepoint cannot disarm us. */
    if (event == XACT_EVENT_COMMIT || event == XACT_EVENT_ABORT ||
        event == XACT_EVENT_PARALLEL_COMMIT || event == XACT_EVENT_PARALLEL_ABORT)
    {
        real_guard_armed = false;
        callback_running = false;
        return;
    }
    if (!real_guard_armed)
        return;

    /* A prepared transaction could commit in another backend without our hook. */
    if (event == XACT_EVENT_PRE_PREPARE)
        ereport(ERROR,
                (errcode(ERRCODE_FEATURE_NOT_SUPPORTED),
                 errmsg("G5_TWO_PHASE_COMMIT_FORBIDDEN")));

    if (event == XACT_EVENT_PARALLEL_PRE_COMMIT)
        ereport(ERROR,
                (errcode(ERRCODE_FEATURE_NOT_SUPPORTED),
                 errmsg("G5_PARALLEL_REAL_COMMIT_FORBIDDEN")));

    if (event != XACT_EVENT_PRE_COMMIT)
        return;

    if (callback_running)
        ereport(ERROR,
                (errcode(ERRCODE_INTERNAL_ERROR),
                 errmsg("G5_PRECOMMIT_REENTRY_FORBIDDEN")));

    /* Do not accept an old statement or repeatable-read transaction snapshot. */
    if (XactIsoLevel != XACT_READ_COMMITTED)
        ereport(ERROR,
                (errcode(ERRCODE_INVALID_TRANSACTION_STATE),
                 errmsg("G5_PRECOMMIT_READ_COMMITTED_REQUIRED")));

    callback_running = true;
    PG_TRY();
    {
        PushActiveSnapshot(GetTransactionSnapshot());
        snapshot_pushed = true;
        rc = SPI_connect();
        if (rc != SPI_OK_CONNECT)
            ereport(ERROR,
                    (errcode(ERRCODE_INTERNAL_ERROR),
                     errmsg("G5_PRECOMMIT_SPI_CONNECT_FAILED")));
        spi_connected = true;

        /*
         * Fixed qualified identifier; no caller SQL, callback or search_path.
         * No SECURITY DEFINER: current_user remains the restricted writer.
         * The validator's owner, definition, ACL and read-only behaviour are
         * deployment gates.  Missing/inaccessible validator is a hard error.
         */
        rc = SPI_execute("SELECT public.b02g5_precommit_validate()", true, 1);
        if (rc != SPI_OK_SELECT || SPI_processed != 1 || SPI_tuptable == NULL ||
            SPI_tuptable->tupdesc->natts != 1 ||
            TupleDescAttr(SPI_tuptable->tupdesc, 0)->atttypid != VOIDOID)
            ereport(ERROR,
                    (errcode(ERRCODE_INTERNAL_ERROR),
                     errmsg("G5_PRECOMMIT_VALIDATION_DID_NOT_COMPLETE")));

        rc = SPI_finish();
        spi_connected = false;
        if (rc != SPI_OK_FINISH)
            ereport(ERROR,
                    (errcode(ERRCODE_INTERNAL_ERROR),
                     errmsg("G5_PRECOMMIT_SPI_FINISH_FAILED")));
        PopActiveSnapshot();
        snapshot_pushed = false;
        callback_running = false;
    }
    PG_CATCH();
    {
        /* Abort cleanup may release SPI/snapshots, but cannot turn denial green. */
        if (spi_connected)
            SPI_finish();
        if (snapshot_pushed)
            PopActiveSnapshot();
        callback_running = false;
        PG_RE_THROW();
    }
    PG_END_TRY();
}

void
_PG_init(void)
{
    if (!callback_registered)
    {
        RegisterXactCallback(b02g5_xact_callback, NULL);
        callback_registered = true;
    }
}

Datum
b02g5_register_real_precommit(PG_FUNCTION_ARGS)
{
    TriggerData *trigdata;
    HeapTuple tuple;
    TupleDesc desc;
    int attr;
    bool isnull;
    Datum provenance_datum;
    Jsonb *provenance;
    JsonbValue key;
    JsonbValue *classification;

    if (!CALLED_AS_TRIGGER(fcinfo))
        ereport(ERROR,
                (errcode(ERRCODE_E_R_I_E_TRIGGER_PROTOCOL_VIOLATED),
                 errmsg("G5_PRECOMMIT_REGISTRAR_TRIGGER_ONLY")));

    trigdata = (TriggerData *) fcinfo->context;
    if (!TRIGGER_FIRED_BEFORE(trigdata->tg_event) ||
        !TRIGGER_FIRED_FOR_ROW(trigdata->tg_event) ||
        !TRIGGER_FIRED_BY_INSERT(trigdata->tg_event))
        ereport(ERROR,
                (errcode(ERRCODE_E_R_I_E_TRIGGER_PROTOCOL_VIOLATED),
                 errmsg("G5_PRECOMMIT_REGISTRAR_BEFORE_INSERT_ONLY")));

    /* Only the three governed tables can arm this guard in this candidate. */
    if (RelationGetNamespace(trigdata->tg_relation) != PG_PUBLIC_NAMESPACE ||
        (strcmp(RelationGetRelationName(trigdata->tg_relation), "acquisition_mode_bindings") != 0 &&
         strcmp(RelationGetRelationName(trigdata->tg_relation), "noncredential_acquisition_receipts") != 0 &&
         strcmp(RelationGetRelationName(trigdata->tg_relation), "noncredential_sanitization_verifications") != 0))
        ereport(ERROR,
                (errcode(ERRCODE_E_R_I_E_TRIGGER_PROTOCOL_VIOLATED),
                 errmsg("G5_PRECOMMIT_REGISTRAR_TABLE_FORBIDDEN")));

    tuple = trigdata->tg_trigtuple;
    desc = trigdata->tg_relation->rd_att;
    attr = SPI_fnumber(desc, "provenance");
    if (attr <= 0 || SPI_gettypeid(desc, attr) != JSONBOID)
        ereport(ERROR,
                (errcode(ERRCODE_UNDEFINED_COLUMN),
                 errmsg("G5_PRECOMMIT_PROVENANCE_COLUMN_REQUIRED")));
    provenance_datum = heap_getattr(tuple, attr, desc, &isnull);
    if (isnull)
        ereport(ERROR,
                (errcode(ERRCODE_CHECK_VIOLATION),
                 errmsg("G5_PRECOMMIT_REAL_BOOLEAN_REQUIRED")));
    provenance = DatumGetJsonbP(provenance_datum);
    if (!JB_ROOT_IS_OBJECT(provenance))
        ereport(ERROR,
                (errcode(ERRCODE_CHECK_VIOLATION),
                 errmsg("G5_PRECOMMIT_REAL_BOOLEAN_REQUIRED")));

    key.type = jbvString;
    key.val.string.val = "synthetic_only";
    key.val.string.len = strlen("synthetic_only");
    classification = findJsonbValueFromContainer(&provenance->root, JB_FOBJECT, &key);
    if (classification == NULL || classification->type != jbvBool ||
        classification->val.boolean)
        ereport(ERROR,
                (errcode(ERRCODE_CHECK_VIOLATION),
                 errmsg("G5_PRECOMMIT_REAL_BOOLEAN_REQUIRED")));

    if (XactIsoLevel != XACT_READ_COMMITTED)
        ereport(ERROR,
                (errcode(ERRCODE_INVALID_TRANSACTION_STATE),
                 errmsg("G5_REAL_WRITE_READ_COMMITTED_REQUIRED")));

    real_guard_armed = true;
    /*
     * Acquire the fixed authority locks while ordinary trigger SQL is legal,
     * before any real row survives. PRE_COMMIT performs reads/rejection only.
     * The helper cannot take caller SQL and must lock the seven exact tables.
     */
    {
        int rc = SPI_connect();
        if (rc != SPI_OK_CONNECT)
            ereport(ERROR,
                    (errcode(ERRCODE_INTERNAL_ERROR),
                     errmsg("G5_REGISTRAR_SPI_CONNECT_FAILED")));
        rc = SPI_execute("SELECT public.b02g5_lock_authority_snapshot()", false, 1);
        if (rc != SPI_OK_SELECT || SPI_processed != 1 || SPI_tuptable == NULL ||
            SPI_tuptable->tupdesc->natts != 1 ||
            TupleDescAttr(SPI_tuptable->tupdesc, 0)->atttypid != VOIDOID)
            ereport(ERROR,
                    (errcode(ERRCODE_INTERNAL_ERROR),
                     errmsg("G5_REGISTRAR_AUTHORITY_LOCK_FAILED")));
        if (SPI_finish() != SPI_OK_FINISH)
            ereport(ERROR,
                    (errcode(ERRCODE_INTERNAL_ERROR),
                     errmsg("G5_REGISTRAR_SPI_FINISH_FAILED")));
    }
    PG_RETURN_POINTER(tuple);
}
