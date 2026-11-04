"""B02 PR28 — applicable owner adoption vs retained historical acts (synthetic)."""
import importlib.util
import json
from pathlib import Path
import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'tools/b02_documentary_signer_v2.py'
spec = importlib.util.spec_from_file_location('b02_adoption_selector', SOURCE)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')

def act(blob, **updates):
    obj = {
        'schema':'SOLVERIS-B02-SIGNER-V2-AUTHORITY-ADOPTION-V1',
        'id':s.SIGNER_ID,
        'issuer':'Miguel',
        'scope':s.SCOPE,
        'policy_subject':s.SUBJECT,
        'signer_source_git_blob':blob,
        'decision_sha256':s.APPROVED_DECISION_SHA256,
        'manifest_sha256':s.APPROVED_MANIFEST_SHA256,
        'approved':True,
        'signing_authorized':True,
        'status':'adopted',
        'revoked':False,
        'no_operational_authority':True,
        'no_g4_reactivation':True,
        'issued_at':'2026-11-04T10:10:00Z',
        'valid_from':'2026-11-04T10:20:00Z',
        'valid_until':s.ORIGINAL_WINDOW_END,
    }
    obj.update(updates)
    return obj

def owner(obj, *, at='2026-11-04T10:12:00Z', login=s.GITHUB_OWNER_LOGIN,
          user_id=s.GITHUB_OWNER_ID, association='OWNER', modified=None):
    return {
        'body':canonical(obj).decode('utf-8'),
        'id':123456,
        'user':{'login':login,'id':user_id},
        'author_association':association,
        'issue_url':s.GITHUB_ISSUE_API,
        'created_at':at,
        'updated_at':modified or at
    }

@pytest.fixture
def graph(monkeypatch):
    current = s.git_blob(SOURCE.read_bytes())
    legacy = owner(act('b8ff97373476bb3ef1b34362612eedd014f0ff21'),
                   at='2026-11-04T00:04:48Z')
    recent = act(current)
    latest = owner(recent)
    state = {'items':[legacy,latest]}
    def source(url):
        if 'page=1' in url:return state['items']
        return []
    monkeypatch.setattr(s,'_github_json',source)
    return state,recent,legacy,latest

def test_historic_act_coexists_and_new_applicable_is_selected(graph):
    state,current,legacy,latest=graph
    assert s._source_pinned_signer_authority(canonical(current),current) == s.sha(canonical(current))
    state['items']=[latest,legacy]
    assert s._source_pinned_signer_authority(canonical(current),current) == s.sha(canonical(current))

def test_old_signer_blob_is_rejected_even_if_preserved_owner_act(graph):
    _,current,legacy,_=graph
    old=json.loads(legacy['body'])
    with pytest.raises(ValueError,match='SIGNER_AUTHORITY_NOT_INDEPENDENTLY_PINNED'):
        s._source_pinned_signer_authority(canonical(old),old)

def test_other_decision_bytes_rejected_without_cli_selection(graph):
    state,current,legacy,_=graph
    other=act(current['signer_source_git_blob'],decision_sha256='e'*64)
    state['items']=[legacy,owner(other)]
    with pytest.raises(ValueError,match='SIGNER_AUTHORITY_APPLICABLE_ACT_INVALID'):
        s._source_pinned_signer_authority(canonical(other),other)

def test_two_conflicting_applicable_owner_acts_stop(graph):
    state,current,legacy,latest=graph
    other=owner(act(current['signer_source_git_blob'],
                    valid_from='2026-11-04T10:30:00Z'))
    state['items']=[legacy,latest,other]
    with pytest.raises(ValueError,match='COMPETENT_SIGNER_ADOPTION_NOT_UNIQUELY_ISSUED'):
        s._source_pinned_signer_authority(canonical(current),current)

def test_revoked_applicable_owner_act_stops(graph):
    state,current,legacy,_=graph
    invalid=act(current['signer_source_git_blob'],revoked=True)
    state['items']=[legacy,owner(invalid)]
    with pytest.raises(ValueError,match='SIGNER_AUTHORITY_APPLICABLE_ACT_INVALID'):
        s._source_pinned_signer_authority(canonical(invalid),invalid)

@pytest.mark.parametrize('tamper',[
    {'login':'different-owner'},
    {'user_id':19},
    {'association':'NONE'},
    {'modified':'2026-11-04T10:13:00Z'},
])
def test_non_owner_or_modified_source_cannot_authorize(graph,tamper):
    state,current,legacy,_=graph
    state['items']=[legacy,owner(current,**tamper)]
    with pytest.raises(ValueError,match='COMPETENT_SIGNER_ADOPTION_NOT_UNIQUELY_ISSUED'):
        s._source_pinned_signer_authority(canonical(current),current)

@pytest.mark.parametrize('invalid',[
    {'issued_at':'2026-11-04T10:15:00Z'},
    {'valid_from':'2026-11-03T17:00:00Z'},
    {'valid_until':'2026-11-04T18:01:00Z'},
    {'valid_until':'2026-11-04T10:19:00Z'},
])
def test_invalid_timeline_stops(graph,invalid):
    state,current,legacy,_=graph
    wrong=act(current['signer_source_git_blob'],**invalid)
    state['items']=[legacy,owner(wrong)]
    with pytest.raises(ValueError,match='SIGNER_AUTHORITY_CHRONOLOGY_INVALID'):
        s._source_pinned_signer_authority(canonical(wrong),wrong)

def test_local_changed_bytes_cannot_override_owner_source(graph):
    state,current,legacy,latest=graph
    altered=dict(current)
    altered['valid_from']='2026-11-04T10:22:00Z'
    with pytest.raises(ValueError,match='SIGNER_AUTHORITY_NOT_INDEPENDENTLY_PINNED'):
        s._source_pinned_signer_authority(canonical(altered),altered)
