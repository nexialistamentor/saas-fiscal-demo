"""Prepare synthetic physical-test inputs. No database/network/real CAS writes.

Runtime persistence stays blocked until real policies and independent evidence
have their own authorisation and proofs. Import has no side effects.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]

def prepare_fixtures(context, namespace):
    # Context is a reviewed export of exact policies/activations from ONLY the
    # isolated database. This tool neither creates nor activates any policy.
    from app.services.enterprise_b02_noncredential_acquisition import (
        CANONICAL_CONTRACT_ID, CANONICAL_CONTRACT_VERSION, CANONICAL_CONTRACT_HASH,
        record_hash, canonical_bytes)
    if context.get('database') != 'solveris_b02_r4g_test' or context.get('synthetic_only') is not True:
        raise ValueError('B02_SYNTHETIC_POLICY_CONTEXT_REQUIRED')
    if not namespace or len(namespace)>12 or not namespace.isalnum():
        raise ValueError('B02_FIXTURE_NAMESPACE_INVALID')
    raw=b'%PDF-SYNTHETIC-B02\nThis is an inert rollback fixture.\n%%EOF\n'
    h=hashlib.sha256(raw).hexdigest(); now=datetime.now(timezone.utc).isoformat()
    common={'schema_version':1,'canonicalization_contract_id':CANONICAL_CONTRACT_ID,
            'canonicalization_contract_version':CANONICAL_CONTRACT_VERSION,
            'canonicalization_contract_hash':CANONICAL_CONTRACT_HASH}
    cases={}; documents={}
    def ref(table,column,key,value):return {'$ref':{'table':table,'column':column,'key':key,'id':value}}
    for name in ('cas','public','concurrent'):
        cfg=context['contexts']['public' if name=='public' else 'cas']
        required={'security_policy_binding','sanitization_policy_binding','source_scope','tenant_scope','actor','verifier','adapter_contract_binding','acquisition_contract_binding','verification_engine_binding','custody_contract_binding'}
        if set(cfg)!=required or cfg['actor']==cfg['verifier']:raise ValueError('B02_POLICY_CONTEXT_INCOMPLETE')
        for field in ('security_policy_binding','sanitization_policy_binding'):
            if not {'policy_type','policy_id','policy_version','policy_hash','policy_activation_id','policy_activation_record_hash'}.issubset(cfg[field]):raise ValueError('B02_EXACT_POLICY_BINDING_REQUIRED')
        mode='EXTERNAL_PUBLIC_NO_CREDENTIALS' if name=='public' else 'LOCAL_CAS_INCORPORATION'
        base='b02test-'+namespace+'-'+name; execution=base+'-exec'; reference=base+'-ref'
        source={'source_id':'urn:solveris:synthetic:'+name,'exact_locator':'https://example.invalid/b02/'+name}
        provenance={'synthetic_only':True,'fixture_case':name,'namespace':namespace}
        rows=[]
        def add(stage,table,values):rows.append({'stage':stage,'table':table,'values':values})
        ar={'artifact_reference_record_id':base+'-ref-r1','artifact_reference_id':reference,'reference_event':'identificada','event_sequence':1,
            'source_id':source['source_id'],'exact_locator':source['exact_locator'],'discovered_at':now,'occurred_at':now,'evidence':{'synthetic_only':True}}
        ar['record_hash']=record_hash(ar);add('reference','artifact_references',ar)
        plan={'acquisition_execution_record_id':base+'-plan','acquisition_execution_id':execution,'artifact_reference_record_id':ar['artifact_reference_record_id'],
            'artifact_reference_id':reference,'attempt_number':1,'execution_event':'criacao','projected_state':'planeada','event_sequence':1,'actor_or_worker':cfg['actor'],
            'adapter_version':str(cfg['adapter_contract_binding']['version']),'occurred_at':now,'evidence':{'synthetic_only':True},'provenance':provenance}
        plan['record_hash']=record_hash(plan);add('planning','acquisition_executions',plan)
        binding=dict(common,mode_binding_id=base+'-binding',planning_execution_record_id=plan['acquisition_execution_record_id'],planning_execution_record_hash=plan['record_hash'],
            acquisition_execution_id=execution,artifact_reference_id=reference,attempt_number=1,mode=mode,actor=cfg['actor'],adapter_contract_binding=cfg['adapter_contract_binding'],
            acquisition_contract_binding=cfg['acquisition_contract_binding'],source_identity_binding=source,source_scope=cfg['source_scope'],tenant_scope=cfg['tenant_scope'],
            scope_hash=hashlib.sha256(canonical_bytes(cfg['source_scope'])).hexdigest(),security_policy_binding=cfg['security_policy_binding'],sanitization_policy_binding=cfg['sanitization_policy_binding'],
            bound_at=now,provenance=provenance)
        add('binding','acquisition_mode_bindings',binding)
        start=dict(plan,acquisition_execution_record_id=base+'-start',execution_event='inicio',projected_state='em_execucao',event_sequence=2,
                   previous_acquisition_execution_record_id=plan['acquisition_execution_record_id'],started_at=now)
        start['record_hash']=record_hash(start);add('start','acquisition_executions',start)
        uri='cas+sha256://'+h+'/'+str(len(raw))
        doc={'id':base+'-observed','synthetic_only':True,'mode':mode,'artifact_hash':h,'byte_size':len(raw),'observed_at':now}
        doc['record_hash']=record_hash(doc);documents[doc['id']]=doc
        proof={'id':doc['id'],'hash':doc['record_hash']}
        custody={'id':base+'-custody','synthetic_only':True,'artifact_hash':h,'byte_size':len(raw),'source':source}
        custody['record_hash']=record_hash(custody);documents[custody['id']]=custody
        transport={} if name!='public' else {'dispatched':True,'response_observed':True,'components_complete':True,'credential_presentation_observed':False,'credential_categories':[],
            'method':'GET','requested_locator':source['exact_locator'],'final_locator':source['exact_locator'],'redirects':[],
            'request_fingerprint':hashlib.sha256(canonical_bytes({'method':'GET','locator':source['exact_locator']})).hexdigest(),
            'status':200,'dispatch_observed_at':now,'response_observed_at':now,'inspected_request_components':['configuration','environment','headers','query','body','proxy','tls','redirects']}
        cas={} if name=='public' else {'read_observed':True,'components_complete':True,'object_uri':uri,'recalculated_hash':h,'recalculated_size':len(raw),
             'custody_contract_binding':cfg['custody_contract_binding'],'prior_evidence_bindings':[{'id':custody['id'],'hash':custody['record_hash']}],'read_observed_at':now}
        receipt=dict(common,receipt_id=base+'-receipt',mode_binding_id=binding['mode_binding_id'],mode_binding_hash=ref('acquisition_mode_bindings','record_hash','mode_binding_id',binding['mode_binding_id']),
            start_execution_record_id=start['acquisition_execution_record_id'],start_execution_record_hash=start['record_hash'],acquisition_execution_id=execution,
            artifact_reference_id=reference,attempt_number=1,mode=mode,source_identity_binding=source,source_scope=cfg['source_scope'],tenant_scope=cfg['tenant_scope'],
            acquisition_contract_binding=cfg['acquisition_contract_binding'],security_policy_binding=cfg['security_policy_binding'],sanitization_policy_binding=cfg['sanitization_policy_binding'],
            artifact_hash=h,byte_size=len(raw),media_type='application/pdf',content_reference={'uri':uri,'hash':h,'byte_size':len(raw)},transport_manifest=transport,cas_manifest=cas,
            component_manifest={'complete':True,'components':['source','scope','contract','transport' if name=='public' else 'cas','content','redaction','execution_proof']},redaction_manifest=[],
            execution_proof_binding=proof,observed_at=now,receipt_created_at=now,acquisition_outcome='acquired' if name=='public' else 'incorporated',creator=cfg['actor'],provenance=provenance)
        add('receipt','noncredential_acquisition_receipts',receipt)
        independent={'id':base+'-independence','synthetic_only':True,'test_kind':'simulated_engine_proof_not_real_independence','producer':cfg['actor'],'verifier':cfg['verifier']}
        independent['record_hash']=record_hash(independent);documents[independent['id']]=independent
        engine=cfg['verification_engine_binding']
        verification=dict(common,verification_id=base+'-verify',receipt_id=receipt['receipt_id'],receipt_hash=ref('noncredential_acquisition_receipts','receipt_hash','receipt_id',receipt['receipt_id']),
            verification_engine_id=engine['id'],verification_engine_version=engine['version'],verification_engine_hash=engine['hash'],
            inspected_component_manifest=dict(receipt['component_manifest'],execution_proof_binding=proof,independence_evidence_binding={'id':independent['id'],'hash':independent['record_hash']}),
            violation_manifest=[],verification_outcome='verified_sanitized',verified_at=now,verifier=cfg['verifier'],sanitization_policy_binding=cfg['sanitization_policy_binding'],provenance=provenance)
        add('verification','noncredential_sanitization_verifications',verification)
        terminal=dict(start,acquisition_execution_record_id=base+'-terminal',execution_event='conclusao',projected_state='concluida',event_sequence=3,
                      previous_acquisition_execution_record_id=start['acquisition_execution_record_id'],finished_at=now,
                      structured_result={'bytes_received':True,'artifact_hash':h,'byte_size':len(raw),'noncredential_receipt_id':receipt['receipt_id'],
                        'noncredential_receipt_hash':verification['receipt_hash'],'noncredential_verification_id':verification['verification_id'],
                        'noncredential_verification_hash':ref('noncredential_sanitization_verifications','record_hash','verification_id',verification['verification_id'])})
        terminal.pop('record_hash');add('terminal','acquisition_executions',terminal)
        artifact={'normative_artifact_id':base+'-artifact','acquisition_execution_record_id':terminal['acquisition_execution_record_id'],
            'acquisition_execution_id':execution,'artifact_reference_id':reference,'acquisition_attempt_number':1,'immutable_bytes':{'$bytea_hex':raw.hex()},
            'byte_size':len(raw),'artifact_hash':h,'acquired_at':now,'media_type':'application/pdf','provenance':provenance}
        add('artifact','normative_artifacts',artifact)
        cases[name]={'case_id':base,'rows':rows}
    # Original credentialled case intentionally has no binding or invented
    # credential predecessor. It must fail the original sanitization gate.
    import copy
    c=copy.deepcopy(cases['cas']);c['case_id']+='-credential-control'
    c['rows']=[r for r in c['rows'] if r['stage'] in ('reference','planning','start','terminal','artifact')]
    t=next(r['values'] for r in c['rows'] if r['stage']=='terminal')
    t['structured_result']={'bytes_received':True,'artifact_hash':h,'byte_size':len(raw)};t['record_hash']=record_hash(t)
    cases['credentialled_without_chain']=c
    return {'schema':'SOLVERIS_B02_R4G_PHYSICAL_FIXTURES_V1','synthetic_only':True,'database':'solveris_b02_r4g_test',
            'policy_fixture_origin':'PREPARED_IN_ISOLATED_DATABASE_NOT_INSTITUTIONAL_AUTHORITY','cases':cases,'synthetic_evidence_documents':documents}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-synthetic-fixtures',action='store_true')
    parser.add_argument('--policy-context',type=Path)
    parser.add_argument('--policy-context-sha256')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if not args.prepare_synthetic_fixtures:parser.error('STOP_REAL_POLICY_OR_EVIDENCE_MISSING: no real persistence authorised')
    if not args.policy_context or not args.out or not args.policy_context_sha256:parser.error('exact policy context, hash and output required')
    raw=args.policy_context.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=args.policy_context_sha256:raise SystemExit('B02_POLICY_CONTEXT_HASH_DIVERGENCE')
    if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
    context=json.loads(raw)
    if context.get('context_origin') != 'ISOLATED_DB_EXACT_EXPORT':raise SystemExit('B02_ACTUAL_REVIEWED_POLICY_EXPORT_REQUIRED')
    content=json.dumps(prepare_fixtures(context,uuid.uuid4().hex[:10]),ensure_ascii=False,sort_keys=True,indent=2).encode('utf-8')+b'\n'
    with args.out.open('xb') as handle:handle.write(content)
    print('B02_SYNTHETIC_FIXTURE_SHA256='+hashlib.sha256(content).hexdigest())
    print('B02_FIXTURE_GENERATED_NOT_EXECUTED_NO_POLICY_ACTIVATED')

if __name__=='__main__':main()
