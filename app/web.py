from flask import render_template,request
from app.config import MODULES,TITLE,SHORT
from app.pipeline import execute,load_sample
from app import store
def register_pages(app):
    def page(index):
        run_id=request.args.get("run")
        run=store.get(run_id) if run_id else (store.latest() or execute(load_sample("dirty.csv")))
        stage=run["stages"][index]
        rows=stage["rows"]
        columns=[['scan_id', 'parcel', 'node', 'event_time', 'received_time'], ['scan_id', 'parcel', 'node', 'destination', 'zone'], ['scan_id', 'parcel', 'event_utc', 'received_utc', 'upload_lag_hours'], ['parcel', 'accepted_at', 'delivered_at', 'delivery_uploaded_at', 'scan_count', 'path', 'revised_destination', 'revised_promised_hours'], ['parcel', 'accepted_at', 'delivered_at', 'official_destination', 'working_hours', 'promised_hours', 'late_hours', 'expected', 'sla', 'reference_destination', 'reference_promised_hours', 'reference_expected', 'reference_sla'], ['parcel', 'expected', 'reported', 'difference', 'reference_expected', 'reference_difference', 'status'], ['parcel', 'delivered_at', 'sla', 'expected', 'status']][index]
        labels={'scan_id': '扫描号', 'parcel': '包裹号', 'node': '节点', 'event_time': '发生时间', 'received_time': '上传时间', 'destination': '目的地', 'zone': '时区', 'event_utc': '发生 UTC', 'received_utc': '上传 UTC', 'upload_lag_hours': '补传时差 / h', 'accepted_at': '收件 UTC', 'delivered_at': '妥投 UTC', 'delivery_uploaded_at': '妥投上传 UTC', 'scan_count': '扫描数', 'path': '节点路径', 'working_hours': '正式计时 / h', 'promised_hours': '正式承诺 / h', 'late_hours': '正式超时 / h', 'expected': '正式赔付 / 元', 'sla': '正式时效结论', 'reported': '申报 / 元', 'difference': '差额 / 元', 'status': '对账结论', 'accepted': '采纳扫描', 'late_uploads': '迟到上传', 'parcels': '包裹数', 'late_parcels': '超时包裹', 'compensation': '正式赔付合计', 'delivered': '妥投数', 'path_errors': '路径异常', 'records': '归档数', 'source_lines': '源行数', 'sha256': '摘要', 'ready': '可归档', 'differences': '差异数', 'revised_destination': '更正目的地', 'revised_promised_hours': '更正承诺 / h', 'official_destination': '正式目的地', 'reference_destination': '参考目的地', 'reference_promised_hours': '参考承诺 / h', 'reference_expected': '参考赔付 / 元', 'reference_sla': '参考时效结论', 'reference_difference': '参考口径差额 / 元', 'corrected_parcels': '目的地更正包裹', 'reference_compensation': '参考口径赔付合计', 'commitment_policy': '正式采用口径', 'reference_total': '参考口径合计', 'reference_claim_blocked': '参考口径赔付已拦截', 'commitment_corrected': '发生目的地更正'}
        for key,label in {'accepted_inputs': '采纳来源行', 'quarantine_inputs': '隔离来源行', 'output_records': '结果记录', 'input': '输入行', 'excluded': '排除行', 'balanced': '行数平衡', 'expected_total': '正式赔付合计', 'reported_total': '申报合计', 'differences': '差异项', 'blank': '空行', 'repeated_headers': '分段表头', 'encoding': '编码', 'duplicate': '重复行', 'quarantine': '隔离行', 'accepted': '采纳行', 'sha256': '校验摘要', 'ready': '可归档'}.items(): labels.setdefault(key,label)
        return render_template(f"m{index+1}.html",title=TITLE,short=SHORT,modules=MODULES,index=index,run=run,stage=stage,rows=rows,columns=columns[:12],history=store.history(),labels=labels)
    app.add_url_rule("/",view_func=lambda:page(4))
    for index,(slug,name) in enumerate(MODULES):
        app.add_url_rule("/"+slug,endpoint="page_"+slug,view_func=lambda index=index:page(index))
