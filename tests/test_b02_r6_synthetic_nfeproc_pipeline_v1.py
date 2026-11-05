"""New synthetic-only pipeline tests, no historical R6 or R7 rerun."""
from pathlib import Path
import pytest
from tools.b02_r6_synthetic_nfeproc_pipeline_v1 import inspect_synthetic_nfeproc
FIXTURE=Path(__file__).parent/"fixtures"/"b02_r6_synthetic_nfeproc_20261105.xml"

def test_synthetic_pipeline_reports_no_fiscal_authority():
    r=inspect_synthetic_nfeproc(FIXTURE.read_bytes())
    assert r["synthetic_only"] is True
    assert r["items"][0]["ncm"]=="12119090"
    assert r["fiscal_authority_verified"] is False
    assert r["r7_real_consumer_eligible"] is False

def test_no_marker_must_stop():
    data=FIXTURE.read_bytes().replace(b'synthetic_only="true"',b'')
    with pytest.raises(ValueError,match="MARKER_REQUIRED"):
        inspect_synthetic_nfeproc(data)

def test_real_looking_nfe_id_must_stop():
    data=FIXTURE.read_bytes().replace(b'NFeSYNTHETIC_NOT_A_REAL_ACCESS_KEY', b'NFe1234567890')
    with pytest.raises(ValueError,match="NONFISCAL_ID_REQUIRED"):
        inspect_synthetic_nfeproc(data)

def test_non_c3_ncm_must_stop():
    data=FIXTURE.read_bytes().replace(b'12119090',b'99999999')
    with pytest.raises(ValueError,match="C3_NCM_REQUIRED"):
        inspect_synthetic_nfeproc(data)
