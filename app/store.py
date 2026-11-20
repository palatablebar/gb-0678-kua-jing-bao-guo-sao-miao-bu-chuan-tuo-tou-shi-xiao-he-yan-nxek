import sqlite3,json
from pathlib import Path
from app.config import DATA_DIR
from app.errors import DomainError
def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA_DIR/"records.db",timeout=20)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,decision TEXT NOT NULL DEFAULT '待复核')")
    # 原始扫描留存：任何切换或重跑都不删除原始字节
    db.execute("CREATE TABLE IF NOT EXISTS run_inputs (run_id TEXT PRIMARY KEY,raw BLOB NOT NULL,params TEXT NOT NULL)")
    return db
def save(run_id,payload,raw=None,params=None):
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO runs(id,payload) VALUES (?,?)",(run_id,json.dumps(payload,ensure_ascii=False)))
        if raw is not None:
            db.execute("INSERT OR IGNORE INTO run_inputs(run_id,raw,params) VALUES (?,?,?)",(run_id,sqlite3.Binary(raw),json.dumps(params or {},ensure_ascii=False,sort_keys=True)))
    return get(run_id)
def get_input(run_id):
    with connect() as db: row=db.execute("SELECT raw,params FROM run_inputs WHERE run_id=?",(run_id,)).fetchone()
    if not row: raise DomainError("NO_RAW_INPUT","该批次未留存原始扫描，无法切换口径",409)
    return bytes(row[0]),json.loads(row[1])
def get(run_id):
    with connect() as db: row=db.execute("SELECT payload,version,decision FROM runs WHERE id=?",(run_id,)).fetchone()
    if not row: raise DomainError("NOT_FOUND","批次不存在",404)
    return {**json.loads(row[0]),"version":row[1],"decision":row[2]}
def latest():
    with connect() as db: row=db.execute("SELECT id FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
    return get(row[0]) if row else None
def history():
    with connect() as db: return [{"run_id":i,"version":v,"decision":d} for i,v,d in db.execute("SELECT id,version,decision FROM runs ORDER BY rowid DESC")]
def review(run_id,version,decision):
    if decision not in {"已复核","退回复核"}: raise DomainError("BAD_DECISION","复核状态无效")
    with connect() as db:
        cursor=db.execute("UPDATE runs SET version=version+1,decision=? WHERE id=? AND version=?",(decision,run_id,version))
        if cursor.rowcount!=1:
            if not db.execute("SELECT 1 FROM runs WHERE id=?",(run_id,)).fetchone(): raise DomainError("NOT_FOUND","批次不存在",404)
            raise DomainError("STALE_VERSION","版本已更新，请刷新",409)
    return get(run_id)
def switch_commitment(run_id,target_policy,dry_run=False):
    """一次性原子切换承诺口径。新口径计算失败时不写入任何内容，页面与导出仍读取上一版完整结论。"""
    if target_policy not in {"original","revised"}: raise DomainError("BAD_POLICY","承诺口径只能是 original 或 revised")
    previous=get(run_id)
    raw,params=get_input(run_id)
    # 先在事务外完成全部计算：任一步抛错都不会触碰已保存批次（失败回退）
    from app.pipeline import calculate
    next_params={**params,"commitment_policy":target_policy}
    candidate=calculate(raw,next_params)
    if not candidate["stages"][-1]["metrics"].get("ready"):
        raise DomainError("SWITCH_NOT_READY","新口径结论不完整，已保留上一版结论",409)
    if dry_run:
        return {"dry_run":True,"switched":False,"previous_run_id":run_id,"candidate_run_id":candidate["run_id"],
                "previous_policy":previous["stages"][4]["metrics"].get("commitment_policy","original"),
                "target_policy":target_policy,"candidate":candidate}
    from app.pipeline import execute
    switched=execute(raw,next_params)
    return {"dry_run":False,"switched":True,"previous_run_id":run_id,"run_id":switched["run_id"],
            "previous_policy":previous["stages"][4]["metrics"].get("commitment_policy","original"),
            "target_policy":target_policy,"run":switched}
