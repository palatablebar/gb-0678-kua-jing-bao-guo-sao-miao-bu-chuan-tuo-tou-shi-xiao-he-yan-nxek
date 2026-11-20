from collections import defaultdict
from app.values import instant
from app.reasons import reject,sources
PRIORITY={"ACCEPT":0,"DEPART":1,"CUSTOMS":2,"DELIVERED":3}
def commitment_ledger(valid):
    # 以事件发生时刻为序，保留受理原承诺与每次目的地更正，任何一版都不覆盖删除
    versions=[];seen_destinations=set()
    accepts=[e for e in valid if e["node"]=="ACCEPT"]
    if not accepts:return versions
    first_accept=accepts[0]
    versions.append({"version":"original","destination":first_accept["destination"],"zone":first_accept["zone"],"promised_hours":first_accept["promised_hours"],"decided_at":first_accept["event_utc"],"received_utc":first_accept["received_utc"],"source_lines":sources(first_accept),"basis":first_accept.get("note",""),"adopted":True})
    seen_destinations.add(first_accept["destination"])
    for e in valid:
        if e["node"]=="ACCEPT" or e["destination"] in seen_destinations:continue
        seen_destinations.add(e["destination"])
        versions.append({"version":"revised","destination":e["destination"],"zone":e["zone"],"promised_hours":e["promised_hours"],"decided_at":e["event_utc"],"received_utc":e["received_utc"],"source_lines":sources(e),"basis":e.get("note",""),"adopted":False})
    return versions
def evaluate(rows,context):
    groups=defaultdict(list);good=[];bad=[]
    for r in rows:groups[r["parcel"]].append(r)
    for parcel,events in sorted(groups.items()):
        events=sorted(events,key=lambda r:(instant(r["event_utc"]),PRIORITY[r["node"]],r["scan_id"]))
        seen={};valid=[];last=-1
        for e in events:
            time=e["event_utc"]
            if time in seen and seen[time]!=e["node"]:bad.append(reject(e,"SIMULTANEOUS_CONFLICT","同刻扫描节点冲突"));continue
            seen[time]=e["node"]
            if PRIORITY[e["node"]]<last:bad.append(reject(e,"PATH_REGRESSION","扫描路径倒退"));continue
            last=PRIORITY[e["node"]];valid.append(e)
        accepts=[e for e in valid if e["node"]=="ACCEPT"]
        if not accepts:
            bad.extend(reject(e,"MISSING_ACCEPT","缺少收件扫描") for e in valid);continue
        delivery=next((e for e in valid if e["node"]=="DELIVERED"),None)
        first=accepts[0]
        source_lines=[line for e in valid for line in sources(e)]
        ledger=commitment_ledger(valid)
        revised=next((v for v in reversed(ledger) if v["version"]=="revised"),None)
        good.append({**first,"_sources":source_lines,"accepted_at":first["event_utc"],"delivered_at":delivery["event_utc"] if delivery else None,"delivery_uploaded_at":delivery["received_utc"] if delivery else None,"scan_count":len(valid),"path":" → ".join(e["node"] for e in valid),"reported":delivery["reported"] if delivery else first["reported"],"commitment_versions":ledger,"commitment_corrected":revised is not None,"revised_destination":revised["destination"] if revised else None,"revised_promised_hours":revised["promised_hours"] if revised else None})
    return {"rows":good,"quarantine":bad,"metrics":{"parcels":len(good),"delivered":sum(r["delivered_at"] is not None for r in good),"path_errors":len(bad),"corrected_parcels":sum(r["commitment_corrected"] for r in good)}}
