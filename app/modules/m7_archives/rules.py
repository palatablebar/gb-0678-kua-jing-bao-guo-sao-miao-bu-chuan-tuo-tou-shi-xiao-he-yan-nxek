import hashlib,json
from decimal import Decimal
from app.errors import DomainError
from app.reasons import sources
def evaluate(rows,context):
    stages=[v for v in context.values() if isinstance(v,dict) and "metrics" in v]
    balances=[s["metrics"]["balanced"] for s in stages if "balanced" in s["metrics"]]
    if balances and not all(balances): raise DomainError("UNBALANCED","来源行未对平，不能归档")
    ids=[str(r.get("parcel",r.get("_line",""))) for r in rows]
    if len(ids)!=len(set(ids)): raise DomainError("ARCHIVE_DUPLICATE","归档业务键重复")
    # 原始扫描、前后两版承诺与更正依据随行完整封存，不做删除或覆盖
    if any(not r.get("commitment_versions") for r in rows): raise DomainError("COMMITMENT_LINEAGE","承诺版本链不完整，不能归档")
    encoded=json.dumps(rows,ensure_ascii=False,sort_keys=True,default=str).encode()
    timeliness=next((s for s in stages if "commitment_policy" in s.get("metrics",{})),None)
    reconcile=next((s for s in stages if "reference_claim_blocked" in s.get("metrics",{})),None)
    policy=timeliness["metrics"]["commitment_policy"] if timeliness else "original"
    return {"rows":rows,"quarantine":[],"metrics":{"records":len(rows),"source_lines":len(set(x for row in rows for x in sources(row))),"sha256":hashlib.sha256(encoded).hexdigest(),"ready":True,"differences":sum(r.get("status")=="差异" for r in rows),
             "corrected_parcels":sum(bool(r.get("commitment_corrected")) for r in rows),
             "commitment_policy":policy,
             "reference_claim_blocked":bool(reconcile and reconcile["metrics"].get("reference_claim_blocked"))}}
