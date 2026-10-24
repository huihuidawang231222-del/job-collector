() => {
 const jobs=[]; const errors=[];
 const visible=n=>!!n.getClientRects().length;
 const clean=s=>{const d=new DOMParser().parseFromString(String(s||''),'text/html');return d.body.innerText?.trim()||d.body.textContent?.trim()||''};
 const values=x=>Array.isArray(x)?x:x?[x]:[];
 function walk(o){
  if(!o||typeof o!=='object')return;
  if(Array.isArray(o)){o.forEach(walk);return;}
  if(values(o['@type']).includes('JobPosting')){
   const locations=values(o.jobLocation).map(l=>{const a=l.address||{};return [a.addressCountry?.name||a.addressCountry,a.addressRegion,a.addressLocality,a.streetAddress].filter(v=>typeof v==='string').join(' ')}).filter(Boolean);
   const v=o.baseSalary?.value;const units={MONTH:'月',YEAR:'年',HOUR:'时',DAY:'天'};let salary='';
   if(v && typeof v==='object' && v.minValue!=null && v.maxValue!=null)salary=`${v.minValue/10000}-${v.maxValue/10000}万/${units[v.unitText]||v.unitText||'未说明周期'}`;
   const org=values(o.hiringOrganization)[0]||{};
   jobs.push({title:clean(o.title||o.name),company:clean(org.name),location:locations.join('；')||(o.jobLocationType==='TELECOMMUTE'?'远程':'未说明'),salary,currency:o.baseSalary?.currency||'',jd:clean(o.description),benefits:clean(o.jobBenefits),industry_raw:clean(o.industry),date_posted:o.datePosted||'',valid_through:o.validThrough||'',url:typeof o.url==='string'?new URL(o.url,document.baseURI).href:document.baseURI,source:'企业招聘官网',extraction_method:'JobPosting JSON-LD',source_job_id:typeof o.identifier==='object'?o.identifier.value||'':o.identifier||''});
  }
  Object.values(o).forEach(v=>{if(v&&typeof v==='object')walk(v)});
 }
 for(const n of document.querySelectorAll('script[type="application/ld+json"]'))try{walk(JSON.parse(n.textContent))}catch{errors.push('无效JSON-LD')}
 // Microdata is used by public ATS pages such as SmartRecruiters.
 if(!jobs.length){
  const root=document.querySelector('[itemscope][itemtype*="JobPosting"]');
  if(root){
   const value=(scope,key)=>{const n=scope?.querySelector(`[itemprop="${key}"]`);return n?.getAttribute('content')||n?.innerText?.trim()||''};
   const desc=root.querySelector('[itemprop="description"]');
   const org=root.querySelector('[itemprop="hiringOrganization"]');
   const loc=root.querySelector('[itemprop="jobLocation"]');
   if(desc&&visible(desc))jobs.push({title:value(root,'title'),company:value(org,'name'),location:['addressCountry','addressRegion','addressLocality','streetAddress'].map(k=>value(loc,k)).filter(Boolean).join(' ')||'未说明',jd:desc.innerText.trim(),industry_raw:value(root,'industry'),date_posted:value(root,'datePosted'),valid_through:value(root,'validThrough'),benefits:value(root,'incentives'),url:document.baseURI,source:'企业招聘官网',extraction_method:'JobPosting Microdata'});
  }
 }
 // Only explicit detail containers; never label a whole page or list as a complete JD.
 if(!jobs.length){
  const n=[...document.querySelectorAll('.job-description,.job_description,.job-detail-description,#job-description,.jobad-description')].find(visible);
  const h=[...document.querySelectorAll('h1')].find(n=>visible(n)&&n.innerText.trim());
  if(n&&h&&n.innerText.trim().length>=80)jobs.push({title:h.innerText.trim(),jd:n.innerText.trim(),url:document.baseURI,location:'未说明',source:'企业招聘官网',extraction_method:'公开JD容器'});
 }
 const links=[...document.querySelectorAll('a[href]')].filter(visible).map(a=>({url:a.href,text:a.innerText.trim()})).filter(a=>/^https?:/.test(a.url));
 return {jobs,links,errors,title:document.title,body:document.body.innerText.slice(0,18000)};
}
