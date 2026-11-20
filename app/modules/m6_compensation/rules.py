from decimal import Decimal
from app.reasons import sources
from app.errors import DomainError
def evaluate(rows,context):
    intake=context.get("intake")
    bad=context.get("quarantine",[])
    accepted=set(x for row in rows for x in sources(row))
    rejected=set(x for row in bad for x in sources(row))
    if accepted & rejected: raise DomainError("LINEAGE_OVERLAP","同一来源行被重复裁决")
    m={"accepted_inputs":len(accepted),"quarantine_inputs":len(rejected),"output_records":len(rows)}
    if intake:
        excluded=intake["duplicate"]+intake["blank"]+intake["repeated_headers"]
        m.update(input=intake["input"],excluded=excluded,balanced=intake["input"]==len(accepted)+len(rejected)+excluded)
    else:m.update(input=len(accepted)+len(rejected),excluded=0,balanced=True)
    output=[]
    for row in rows:
        expected=Decimal(str(row.get("expected","0")));reported=Decimal(str(row.get("reported","0")))
        item={**row,"difference":str(expected-reported),"status":"通过" if expected==reported else "差异"}
        # 参考口径（新目的地承诺）只能对比，永不进入赔付；正式赔付仅沿用受理承诺版本
        if row.get("reference_expected") is not None:
            item["reference_difference"]=str(Decimal(str(row["reference_expected"]))-expected)
        output.append(item)
    official_total=sum((Decimal(str(r.get("expected","0"))) for r in rows),Decimal(0))
    reference_total=sum((Decimal(str(r["reference_expected"])) for r in rows if r.get("reference_expected") is not None),Decimal(0))
    m.update(expected_total=str(official_total),reported_total=str(sum((Decimal(str(r.get("reported","0"))) for r in rows),Decimal(0))),differences=sum(r["status"]=="差异" for r in output),
             reference_total=str(reference_total),reference_claim_blocked=reference_total>official_total)
    return {"rows":output,"quarantine":[],"metrics":m}
