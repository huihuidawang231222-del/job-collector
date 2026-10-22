"""Conservative rules: company industry never inferred from job title."""
import re
CITIES=['广州','深圳','北京','上海','佛山','东莞','珠海','杭州','成都','武汉','南京','苏州']
DISTRICTS=['天河区','越秀区','海珠区','荔湾区','白云区','黄埔区','番禺区','花都区','南沙区','增城区','从化区']
INDUSTRIES={'互联网/软件':['互联网','软件开发','计算机软件','信息技术'], '房地产/建筑':['房地产','建筑工程','商业地产'], '金融':['银行','证券','保险','金融'], '制造业':['制造业','机械制造','汽车制造','电子制造'], '教育':['教育培训','高等教育','职业教育'], '物流/供应链':['物流','供应链'], '专业服务':['咨询服务','人力资源服务','法律服务'], '地理信息/测绘':['测绘','地理信息','遥感']}
SKILLS=['Python','SQL','Excel','Pandas','Power BI','Tableau','ArcGIS','QGIS','Java','JavaScript','R语言','AutoCAD']
def enrich(row):
    r=dict(row); loc=str(r.get('location','')); jd=str(r.get('jd','')); raw=str(r.get('raw',''))
    r['city']=next((x for x in CITIES if x in loc),'未说明')
    if r['city']=='未说明':
        aliases={'guangzhou':'广州','canton':'广州','shenzhen':'深圳','beijing':'北京','shanghai':'上海','foshan':'佛山'}
        r['city']=next((v for k,v in aliases.items() if re.search(r'(?<![a-z])'+k+r'(?![a-z])',loc,re.I)),'未说明')
    r['district']=next((x for x in DISTRICTS if x in loc),'未说明')
    text=' '.join([jd,raw,str(r.get('benefits',''))])
    r['jd']=jd; r['jd_status']='已采集' if jd.strip() else r.get('jd_access') or '未获取详情'
    r['education']=next((x for x in ['博士','硕士','本科','大专','高中','中专','学历不限'] if x in text),'未说明')
    exp=re.search(r'\d+\s*[-至]\s*\d+\s*年|\d+\s*年以上|经验不限|应届(?:毕业生)?|无需经验',text)
    r['experience']=exp[0] if exp else '未说明'
    r['skills']='、'.join(x for x in SKILLS if re.search(r'(?<![a-zA-Z])'+re.escape(x)+r'(?![a-zA-Z])',text,re.I)) or '未说明'
    r['benefit_tags']='、'.join(x for x in ['五险一金','六险一金','双休','带薪年假','餐补','房补','交通补贴','年终奖','股票期权'] if x in text) or '未说明'
    n=re.search(r'(\d{2})\s*薪',str(r.get('salary',''))+' '+text)
    r['salary_months']=int(n[1]) if n else None
    source=str(r.get('industry_raw','')).strip()
    r['industry_raw']=source
    r['industry']=source or '未说明';r['industry_basis']='平台原文' if source else '缺失'
    if source:
        for category,words in INDUSTRIES.items():
            if any(x in source for x in words):r['industry']=category;r['industry_basis']='平台行业原文归类';break
    return r
EXPORT_COLUMNS={'title':'岗位名称','company':'公司','city':'城市','district':'区','location':'工作地点原文','salary':'待遇原文','salary_min':'月薪下限_元','salary_max':'月薪上限_元','salary_months':'薪数','benefit_tags':'福利标签','weekends':'休息安排','jd':'岗位JD','jd_status':'JD采集状态','education':'学历','experience':'经验','skills':'技能关键词','industry':'行业分类','industry_raw':'行业原文','industry_basis':'行业分类依据','source':'招聘平台','url':'岗位链接','first_seen':'首次采集时间','last_seen':'最近采集时间','raw':'列表原文','career_entry':'官网招聘入口','source_evidence':'发现来源','source_trust':'官网核验状态','date_posted':'岗位发布日期','valid_through':'申请截止时间','listing_state':'在招状态','last_checked':'最近检查时间','currency':'薪资币种','extraction_method':'提取方式','source_job_id':'来源岗位ID','source_provider':'招聘系统','batch_task_id':'采集任务ID','employment_type':'用工类型','department':'部门','team':'团队','workplace_type':'办公方式','country':'国家代码'}
EXPORT_COLUMNS.update({'benefits':'福利原文','search_keyword':'搜索关键词','detail_error':'详情采集错误'})
EXPORT_COLUMNS.update({'source_page':'采集页面','jd_access':'详情访问状态'})
EXPORT_COLUMNS.update({'company_url':'公司链接'})

def export_rows(rows):
    return [{label:enrich(r).get(key,'') for key,label in EXPORT_COLUMNS.items()} for r in rows]

