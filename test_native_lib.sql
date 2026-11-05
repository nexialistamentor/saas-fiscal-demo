BEGIN;
CREATE FUNCTION public.test_b02g5_native_profile() RETURNS text AS '$libdir/b02_g5_native_REAL_CLOSED','b02g5_native_profile' LANGUAGE C STABLE PARALLEL UNSAFE SECURITY INVOKER;
SELECT public.test_b02g5_native_profile();
ROLLBACK;
