() => {
 const configs = [
  {host:'zhipin.com',name:'BOSS直聘',card:'.job-card-wrapper', title:'.job-name',company:'.company-name',salary:'.salary',location:'.job-area'},
  {host:'zhaopin.com',name:'智联招聘',card:'.joblist-box__item',title:'.jobinfo__name',company:'.companyinfo__name',salary:'.jobinfo__salary',location:'.jobinfo__other-info-item'},
  {host:'liepin.com',name:'猎聘',card:'.job-card-pc-container',title:'.job-title',company:'.company-name',salary:'.job-salary',location:'.job-dq'},
  {host:'51job.com',name:'前程无忧',card:'.joblist-item',title:'.jname',company:'.cname',salary:'.sal',location:'.d'}
 ];
 const cfg=configs.find(c=>location.hostname===c.host || location.hostname.endsWith('.'+c.host));
 const rows=[];
 const txt=(n,s)=>n.querySelector(s)?.innerText?.trim() || '';
 if(cfg?.host==='zhaopin.com') for(const [index,n] of Array.from(document.querySelectorAll('.job-list-panel .job-card')).entries()){
  if(!n.getClientRects().length || n.closest('.job-list-login-gate')) continue;
  rows.push({title:txt(n,'.job-card__title-main .vue-clamp__text')||txt(n,'.job-card__title-main'),company:txt(n,'.job-card__company-name'),salary:txt(n,'.job-card__salary'),location:txt(n,'.job-card__location'),source:cfg.name,url:'',source_page:location.href,raw:n.innerText,list_index:index,capture_layout:'zhaopin-split'});
 }
 if(cfg) for(const n of document.querySelectorAll(cfg.card)){
  if(!n.getClientRects().length) continue;
  const a=n.querySelector('a[href*="job"],a[href*="position"],a[href]');
  rows.push({title:txt(n,cfg.title),company:txt(n,cfg.company),salary:txt(n,cfg.salary),location:txt(n,cfg.location),source:cfg.name,url:a?.href||'',raw:n.innerText});
 }
 // 标准 JobPosting 数据只作为详情页补充，不猜测其它网页文本。
 function walk(o){
  if(!o || typeof o!=='object') return;
  if(Array.isArray(o)){o.forEach(walk);return;}
  const types=[].concat(o['@type']||[]);
  if(types.includes('JobPosting')){
   const s=o.baseSalary?.value, unit=s?.unitText;
   rows.push({title:o.title||'',company:o.hiringOrganization?.name||'',salary:unit==='MONTH' && s?.minValue!=null && s?.maxValue!=null ? `${s.minValue/1000}-${s.maxValue/1000}K`:'',location:o.jobLocation?.address?.addressLocality||'',source:cfg?.name||location.hostname,url:o.url||location.href,raw:new DOMParser().parseFromString(o.description||'','text/html').body.textContent});
  }
  for(const [k,v] of Object.entries(o)) if(k!=='description') walk(v);
 }
 for(const n of document.querySelectorAll('script[type="application/ld+json"]')){try{walk(JSON.parse(n.textContent))}catch{}}
 return {rows,source:cfg?.name||location.hostname,url:location.href};
}
