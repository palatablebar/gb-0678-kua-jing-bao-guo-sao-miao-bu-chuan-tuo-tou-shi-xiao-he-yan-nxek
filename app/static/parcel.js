const ui={message:document.querySelector('#message'),sample:document.querySelector('#sample-name'),file:document.querySelector('#scan-file')};
async function requestRun(url,body,isFile=false){ui.message.textContent='正在核算…';try{const options={method:'POST',body:isFile?body:JSON.stringify(body)};if(!isFile)options.headers={'Content-Type':'application/json'};const res=await fetch(url,options);const result=await res.json();if(!res.ok)throw new Error(result.message);window.location.reload();}catch(e){ui.message.textContent=e.message;}}
document.querySelector('#retry').addEventListener('click',()=>requestRun('/api/runs',{sample:ui.sample.value}));
document.querySelector('#read-file').addEventListener('click',()=>{if(!ui.file.files.length){ui.message.textContent='请选择扫描文件。';return;}const data=new FormData();data.append('file',ui.file.files[0]);requestRun('/api/upload',data,true);});
document.querySelector('#review-run').addEventListener('click',()=>requestRun('/api/runs/'+window.parcelRun.id+'/review',{version:window.parcelRun.version,decision:'已复核'}));
document.querySelector('#search-scans')?.addEventListener('input',event=>{document.querySelectorAll('#scan-rows tr').forEach(row=>{row.hidden=!row.textContent.includes(event.target.value);});});
const switchMessage=document.querySelector('#switch-message');
async function switchPolicy(policy,dryRun){
  if(!switchMessage)return;
  switchMessage.textContent='正在'+(dryRun?'预检':'切换')+'口径…';
  try{
    const res=await fetch('/api/runs/'+window.parcelRun.id+'/commitment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({commitment_policy:policy,dry_run:dryRun})});
    const result=await res.json();
    if(!res.ok)throw new Error(result.message);
    if(dryRun){
      const c=result.candidate.stages[4].metrics;
      switchMessage.textContent='预检通过：候选批次 '+result.candidate_run_id.slice(0,8)+'，正式赔付 '+c.compensation+'，参考(新)口径不写入。确认无误后再执行一次性切换。';
    }else{
      switchMessage.textContent='已切换至 '+result.target_policy+'，新批次 '+result.run_id.slice(0,8)+'；原批次结论与原始扫描均保留。';
      setTimeout(()=>window.location.assign('/timeliness?run='+result.run_id),800);
    }
  }catch(e){
    // 一次性切换失败：页面与导出仍读取上一版完整结论，原始扫描与前后承诺不删除
    switchMessage.textContent='切换失败，已保留上一版完整结论：'+e.message;
  }
}
document.querySelector('#switch-dry')?.addEventListener('click',()=>switchPolicy('revised',true));
document.querySelector('#switch-revised')?.addEventListener('click',()=>switchPolicy('revised',false));
document.querySelector('#switch-original')?.addEventListener('click',()=>switchPolicy('original',false));
