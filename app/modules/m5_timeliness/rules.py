from datetime import datetime,timedelta,time
from zoneinfo import ZoneInfo
from decimal import Decimal
from app.values import instant,number,money
from app.errors import DomainError
HOLIDAYS={"JP":{"2026-11-03","2026-11-23"},"US":{"2026-11-26"},"DE":{"2026-10-03"}}
POLICIES={"original","revised"}
NOT_ADOPTED_REASON="订单受理时运输合同已按原目的地承诺成立，财务结算与赔付不得追溯变更；新目的地承诺仅自下一次扫描起参考，不回溯已受理订单"
def working_hours(start,end,zone,holidays):
    if end<start:raise DomainError("NEGATIVE_INTERVAL","妥投早于收件")
    tz=ZoneInfo(zone);cursor=start;seconds=Decimal(0)
    while cursor<end:
        local=cursor.astimezone(tz);next_day=datetime.combine(local.date()+timedelta(days=1),time.min,tzinfo=tz).astimezone(cursor.tzinfo)
        stop=min(end,next_day)
        if local.weekday()<5 and local.date().isoformat() not in holidays:seconds+=Decimal(str((stop-cursor).total_seconds()))
        cursor=stop
    return seconds/3600
def _holidays(p,destination):
    return set(p.get("holidays",{}).get(destination,HOLIDAYS.get(destination,set())))
def _settle(row,start,end,p,destination,zone,promised_hours,rate):
    hours=working_hours(start,end,zone,_holidays(p,destination))
    late=max(Decimal(0),hours-number(promised_hours))
    comp=min(number(row["declared_value"])*Decimal("0.10"),late*rate)
    return hours,late,comp
def evaluate(rows,context):
    p=context.get("parameters",{});as_of=instant(p.get("as_of","2026-11-18T00:00:00Z"));rate=number(p.get("hourly_compensation","1.00"))
    if rate<0:raise DomainError("BAD_RATE","赔付费率不能为负")
    policy=p.get("commitment_policy","original")
    if policy not in POLICIES:raise DomainError("BAD_POLICY","承诺口径只能是 original 或 revised")
    good=[]
    for row in rows:
        start=instant(row["accepted_at"]);end=instant(row["delivered_at"]) if row.get("delivered_at") else max(start,as_of)
        versions=row.get("commitment_versions",[])
        if not versions:
            # 向后兼容：未经M4承诺链的精简行，按当前行字段构造受理原承诺
            versions=[{"version":"original","destination":row["destination"],"zone":row["zone"],"promised_hours":row["promised_hours"],"decided_at":row["accepted_at"],"source_lines":row.get("_sources",[]),"basis":row.get("note",""),"adopted":True}]
        original=next((v for v in versions if v["version"]=="original"),None)
        revised=next((v for v in reversed(versions) if v["version"]=="revised"),None)
        # 正式时效：口径参数可切换，但默认且财务结算沿用受理原承诺
        official=revised if policy=="revised" and revised else original
        if official is None:raise DomainError("MISSING_COMMITMENT","缺少受理承诺，无法裁决时效")
        hours,late,comp=_settle(row,start,end,p,official["destination"],official["zone"],official["promised_hours"],rate)
        out={**row,"working_hours":str(hours),"late_hours":str(late),"expected":money(comp),"sla":"超时" if late>0 else "达标","clock_end":end.isoformat(),
             "commitment_policy":policy,"official_commitment_version":official["version"],"official_destination":official["destination"],"promised_hours":official["promised_hours"],
             "official_basis":official.get("basis",""),"official_source_lines":official.get("source_lines",[])}
        # 另一版（新目的地）承诺只做参考重算，绝不进入正式赔付
        if revised and official["version"]=="original":
            r_hours,r_late,r_comp=_settle(row,start,end,p,revised["destination"],revised["zone"],revised["promised_hours"],rate)
            out.update(reference_commitment_version="revised",reference_destination=revised["destination"],reference_promised_hours=revised["promised_hours"],
                       reference_working_hours=str(r_hours),reference_late_hours=str(r_late),reference_expected=money(r_comp),
                       reference_sla="超时" if r_late>0 else "达标",reference_basis=revised.get("basis",""),reference_source_lines=revised.get("source_lines",[]),
                       not_adopted_reason=NOT_ADOPTED_REASON)
        elif revised:
            out.update(reference_commitment_version="original",reference_destination=original["destination"],reference_promised_hours=original["promised_hours"],
                       reference_basis=original.get("basis",""),reference_source_lines=original.get("source_lines",[]),
                       not_adopted_reason="当前批次按新口径试算，原受理承诺保留备查；正式批次仍以受理原承诺结算")
        good.append(out)
    revised_parcels=[r for r in good if r.get("reference_commitment_version")=="revised"]
    metrics={"parcels":len(good),"late_parcels":sum(r["sla"]=="超时" for r in good),
             "compensation":money(sum((number(r["expected"]) for r in good),Decimal(0))),
             "corrected_parcels":len(revised_parcels),
             "reference_compensation":money(sum((number(r["reference_expected"]) for r in revised_parcels),Decimal(0))),
             "commitment_policy":policy}
    return {"rows":good,"quarantine":[],"metrics":metrics}
