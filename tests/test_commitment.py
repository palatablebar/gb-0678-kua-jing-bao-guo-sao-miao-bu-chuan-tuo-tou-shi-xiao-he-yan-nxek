import csv,io
import pytest
from app.pipeline import calculate,execute,load_sample
from app import store
from app.errors import DomainError

@pytest.fixture
def corrected():
    return load_sample("corrected.csv")

def test_original_commitment_is_official(corrected):
    "裁决：正式时效采用受理时原目的地承诺"
    r=calculate(corrected)
    rows={x["parcel"]:x for x in r["stages"][4]["rows"]}
    assert rows["1001"]["official_commitment_version"]=="original"
    assert rows["1001"]["official_destination"]=="JP"
    assert rows["1001"]["promised_hours"]=="24"
    assert r["stages"][4]["metrics"]["commitment_policy"]=="original"

def test_both_commitment_versions_preserved_with_basis(corrected):
    "原始扫描、前后两版承诺与更正依据完整保留，不覆盖删除"
    r=calculate(corrected)
    row=next(x for x in r["stages"][4]["rows"] if x["parcel"]=="1001")
    versions=row["commitment_versions"]
    assert [(v["version"],v["destination"],v["promised_hours"]) for v in versions]==[("original","JP","24"),("revised","US","48")]
    assert versions[0]["adopted"] is True and versions[1]["adopted"] is False
    assert versions[1]["basis"]=="目的地更正JP转US"
    assert versions[0]["source_lines"] and versions[1]["source_lines"]

def test_revised_version_is_reference_only_with_reason(corrected):
    "新目的地承诺仅作参考，页面/数据须给出未采用原因"
    r=calculate(corrected)
    row=next(x for x in r["stages"][4]["rows"] if x["parcel"]=="1001")
    assert row["reference_commitment_version"]=="revised"
    assert row["reference_destination"]=="US"
    assert "不回溯" in row["not_adopted_reason"]
    # 正式赔付与参考赔付是两套数字，参考值不得写入 expected
    assert row["expected"]!=row["reference_expected"]

def test_compensation_and_export_only_use_official(corrected):
    "赔付与证据导出只能沿用正式版本"
    run=execute(corrected)
    m6=run["stages"][5]
    official=sum(float(r["expected"]) for r in m6["rows"])
    assert float(m6["metrics"]["expected_total"])==official
    assert float(m6["metrics"]["reference_total"])!=official
    archive=store.get(run["run_id"])
    out=__import__("app.archive",fromlist=["build_archive"]).build_archive(archive)
    rows=list(csv.reader(io.StringIO(out.lstrip("﻿"))))
    header=rows[0]
    assert header[6]=="commitment_policy" and "not_adopted_reason" in header
    accepted=[x for x in rows[1:] if x[3]=="accepted"]
    assert all(x[6]=="original" for x in accepted)
    # 证据 JSON 内仍含两版承诺与更正依据
    assert all(("commitment_versions" in x[-1]) for x in accepted)

def test_same_reupload_rerun_creates_no_new_compensation(corrected):
    "同一补传重跑不能新增赔付：批次、赔付合计完全一致"
    a=execute(corrected);b=execute(corrected)
    assert a["run_id"]==b["run_id"]
    assert a["stages"][5]["metrics"]["expected_total"]==b["stages"][5]["metrics"]["expected_total"]
    assert len(store.history())==1

def test_reference_claim_that_exceeds_official_is_blocked(corrected):
    "参考口径若算出更高赔付，护栏标记拦截且正式合计不变"
    run=execute(corrected)
    m6=run["stages"][5]
    assert m6["metrics"]["reference_claim_blocked"] is True
    assert float(m6["metrics"]["reference_total"])>float(m6["metrics"]["expected_total"])

def test_revised_policy_trial_keeps_original_run_untouched(corrected):
    "一次性切换产生独立批次，原批次结论与原始输入均保留"
    first=execute(corrected)
    outcome=store.switch_commitment(first["run_id"],"revised")
    assert outcome["switched"] is True and outcome["run_id"]!=first["run_id"]
    prior=store.get(first["run_id"])
    assert prior["stages"][4]["metrics"]["commitment_policy"]=="original"
    assert prior["stages"][5]["metrics"]["expected_total"]==first["stages"][5]["metrics"]["expected_total"]
    raw,params=store.get_input(first["run_id"])
    assert raw==corrected
    new=store.get(outcome["run_id"])
    assert new["stages"][4]["metrics"]["commitment_policy"]=="revised"

def test_dry_run_does_not_persist(corrected):
    first=execute(corrected)
    before=len(store.history())
    outcome=store.switch_commitment(first["run_id"],"revised",dry_run=True)
    assert outcome["switched"] is False and len(store.history())==before
    assert outcome["candidate"]["stages"][-1]["metrics"]["ready"] is True

def test_switch_failure_keeps_previous_complete_conclusion(corrected,monkeypatch):
    "新口径一次性切换失败：页面与导出仍读取上一版完整结论，且不产生残缺批次"
    first=execute(corrected)
    before=len(store.history())
    import app.pipeline as pipeline
    def boom(*a,**k): raise DomainError("SWITCH_BROKEN","模拟新口径计算失败",500)
    monkeypatch.setattr(pipeline,"calculate",boom)
    with pytest.raises(DomainError) as e:
        store.switch_commitment(first["run_id"],"revised")
    assert e.value.code=="SWITCH_BROKEN"
    assert len(store.history())==before
    intact=store.get(first["run_id"])
    assert intact["stages"][-1]["metrics"]["ready"] is True
    raw,_=store.get_input(first["run_id"]);assert raw==corrected

def test_switch_unknown_policy_rejected(corrected):
    first=execute(corrected)
    with pytest.raises(DomainError):store.switch_commitment(first["run_id"],"sideways")

def test_switch_api_failure_rollback(client,corrected,monkeypatch):
    p=client.post("/api/runs",json={"sample":"corrected.csv"}).get_json()
    import app.pipeline as pipeline
    def boom(*a,**k): raise DomainError("SWITCH_BROKEN","模拟新口径计算失败",500)
    monkeypatch.setattr(pipeline,"calculate",boom)
    url="/api/runs/"+p["run_id"]+"/commitment"
    r=client.post(url,json={"commitment_policy":"revised"})
    assert r.status_code==500 and r.get_json()["code"]=="SWITCH_BROKEN"
    detail=client.get("/api/runs/"+p["run_id"]).get_json()
    assert detail["stages"][-1]["metrics"]["ready"] is True

def test_switch_api_happy_path_and_bad_policy(client):
    p=client.post("/api/runs",json={"sample":"corrected.csv"}).get_json()
    url="/api/runs/"+p["run_id"]+"/commitment"
    ok=client.post(url,json={"commitment_policy":"revised"}).get_json()
    assert ok["switched"] is True
    bad=client.post(url,json={"commitment_policy":"nope"})
    assert bad.status_code==422

def test_timeliness_page_renders_ruling(client):
    client.post("/api/runs",json={"sample":"corrected.csv"})
    html=client.get("/timeliness").data.decode()
    assert "承诺口径裁决" in html and "不回溯" in html and "未采用" in html

def test_archive_export_switch_run_uses_its_own_policy(client):
    p=client.post("/api/runs",json={"sample":"corrected.csv"}).get_json()
    sw=client.post("/api/runs/"+p["run_id"]+"/commitment",json={"commitment_policy":"revised"}).get_json()
    r=client.get("/api/runs/"+sw["run_id"]+"/archive")
    rows=list(csv.reader(io.StringIO(r.data.decode("utf-8-sig"))))
    accepted=[x for x in rows[1:] if x[3]=="accepted"]
    assert all(x[6]=="revised" for x in accepted)
    # 原批次导出仍为 original
    r0=client.get("/api/runs/"+p["run_id"]+"/archive")
    rows0=list(csv.reader(io.StringIO(r0.data.decode("utf-8-sig"))))
    assert all(x[6]=="original" for x in rows0[1:] if x[3]=="accepted")

def test_m4_ledger_corrected_count(corrected):
    r=calculate(corrected)
    m4=r["stages"][3]
    assert m4["metrics"]["corrected_parcels"]==2
    normal=next(x for x in m4["rows"] if x["parcel"]=="1003")
    assert normal["commitment_corrected"] is False
    assert [v["version"] for v in normal["commitment_versions"]]==["original"]
