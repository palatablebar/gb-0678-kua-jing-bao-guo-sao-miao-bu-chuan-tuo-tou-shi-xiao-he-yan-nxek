# 接口

模块GET使用仓内样例，模块POST可传csv或rows与context，直接计算当前规则。/api/runs使用完整流水线并原子保存。每个阶段返回rows、quarantine、metrics；后续阶段还返回累计隔离。/api/upload接收multipart文件file。/api/runs/<id>/archive只导出一份带清单与证据的CSV。

## 承诺口径

M4在`commitment_versions`中按事件发生时刻封存每个包裹的原承诺(original)与每次目的地更正(revised)，含目的地、承诺时限、裁决时刻、来源行与更正依据(note)，任何一版都不覆盖删除。M5默认`commitment_policy=original`：正式时效、超时与赔付(expected)只按受理原承诺；新目的地承诺以`reference_*`字段并行试算，并附`not_adopted_reason`说明未采用原因（合同受理后不得追溯变更）。M6的`expected_total`只汇总正式赔付，`reference_total`仅作对照；参考口径合计高于正式合计时`reference_claim_blocked=true`，且永不写入赔付。

`POST /api/runs/<id>/commitment`，body：`{"commitment_policy":"revised","dry_run":false}`。切换在事务外先完成全量计算（先算后写），任一步失败返回错误且不改动已保存批次，页面与导出仍读取上一版完整结论；成功则以不同run_id生成独立批次，原批次与`run_inputs`表中的原始扫描字节均保留。`dry_run=true`只返回候选批次不落库。
