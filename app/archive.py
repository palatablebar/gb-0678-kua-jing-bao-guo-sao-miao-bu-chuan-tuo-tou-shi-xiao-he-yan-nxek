import csv,io,json
def build_archive(run):
    stream=io.StringIO(newline="");writer=csv.writer(stream)
    writer.writerow(["run_id","input_sha256","rule_version","kind","source_lines","reason","commitment_policy","official_destination","reference_destination","not_adopted_reason","evidence"])
    meta=run["manifest"]
    policy=run["stages"][4]["metrics"].get("commitment_policy","original")
    for row in run["stages"][-1]["rows"]:
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"accepted",json.dumps(row.get("_sources",[])),row.get("status",""),policy,row.get("official_destination",""),row.get("reference_destination",""),row.get("not_adopted_reason",""),json.dumps(row,ensure_ascii=False)])
    for row in run["stages"][-1].get("cumulative_quarantine",[]):
        writer.writerow([run["run_id"],meta["input_sha256"],meta["rule_version"],"quarantine",json.dumps(row.get("_sources",[])),row.get("reason",""),policy,"","","",json.dumps(row,ensure_ascii=False)])
    return "﻿"+stream.getvalue()
