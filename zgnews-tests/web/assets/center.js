/* QA workflow UI. All interpolated data is escaped; permissions are enforced on server. */
(() => {
  "use strict";
  const root = document.querySelector("#qa-center");
  if (!root) return;
  const section = root.dataset.section, $ = s => root.querySelector(s);
  const titles = {overview:"总览",requirements:"需求文档",factory:"AI 用例工厂",prompts:"Prompt 管理",cases:"用例库",runs:"测试执行",defects:"缺陷协同",reports:"报告",outbox:"发件箱",settings:"设置",history:"只读历史"};
  const paths = {overview:"/",requirements:"/requirements",factory:"/factory",prompts:"/prompts",cases:"/cases",runs:"/runs",defects:"/defects",reports:"/reports",outbox:"/outbox",settings:"/settings",history:"/history"};
  const stateNames={active:"进行中",draft:"草稿",reviewed:"评审通过",rejected:"待修改",published:"已入库",deleted:"已删除",queued:"排队中",running:"执行中",passed:"通过",failed:"失败",cancelled:"已取消",aborted:"已中断",open:"待认领",claimed:"已认领",rd_running:"RD 自回测中",fix_failed:"RD 自测未通过",pending_qa:"待 QA 回测",qa_running:"QA 回测中",fixed:"已修复",closed:"已关闭",reopened:"未解决","queued-local":"已存入发件箱",archived:"已归档",risk:"存在风险",synced:"已同步"};
  const fieldNames={id:"数据库记录",name:"用例名称",origin:"用例来源",priority:"优先级",area:"测试域",nodeid:"pytest 定位",draft_version:"草稿版本",review_id:"评审记录",code_hash:"代码哈希",commit:"资产版本",code_path:"生成代码",version:"版本",status:"当前状态",source:"生成来源",scope:"执行范围",started:"开始时间",finished:"完成时间",title:"标题",case_id:"关联用例",run_id:"关联执行",owner_id:"认领人",routed_owner_id:"分派人",rd_run_id:"RD 自测记录",qa_run_id:"QA 回测记录",active:"是否启用",verdict:"测试结论",transport:"投递方式",report_id:"关联报告",defect_id:"关联缺陷"};
  const descriptions={overview:"从需求到交付，查看当前工作进展与质量证据。",requirements:"上传需求文档，由 AI 提取测试点并生成可评审的用例草稿。",factory:"核对生成结果、同步代码、独立评审，人工确认后进入正式用例库。",prompts:"管理生成与评审规则的版本，保留每次使用的依据。",cases:"正式用例保存在后端数据库，本页直接读取并展示。",runs:"选择冒烟、全量或指定范围，查看每条用例的执行证据。",defects:"分派问题、提交修复证明，分别完成 RD 自测和 QA 回测。",reports:"基于完整执行证据生成报告，保留当时的缺陷与风险快照。",outbox:"编辑收件人和抄送，预览报告邮件并保存投递记录。",settings:"配置人员、负责人路由、默认收件人和测试环境能力。",history:"保留升级前的运行、缺陷、报告和通知档案。"};
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const summaryText = value => {
    if (value==null || value==="") return "暂无内容";
    if (typeof value!=="object") return String(value);
    if (Array.isArray(value)) return value.slice(0,3).map(summaryText).join("；") || "暂无内容";
    return Object.entries(value).slice(0,4).map(([key,item])=>`${fieldNames[key]||key}：${summaryText(item)}`).join("；");
  };
  const pretty = value => `<div class="evidence-summary"><b>系统记录</b><p>${esc(summaryText(value))}</p></div>`;
  const panel = (title, body) => `<div class="qa-panel"><h2>${esc(title)}</h2>${body}</div>`;
  const metric = (label,value,caption,href,tone) => `<a class="metric-card ${tone||""}" href="${href}"><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(caption)} <b>→</b></small></a>`;
  const input = (name,label,value="",type="text") => `<label>${esc(label)}<input name="${name}" type="${type}" value="${esc(value)}"></label>`;
  const text = (name,label,value="") => `<label class="wide">${esc(label)}<textarea name="${name}">${esc(Array.isArray(value)?value.join("\n"):value)}</textarea></label>`;
  const select = (name,label,values,value) => `<label>${esc(label)}<select name="${name}">${values.map(v=>{const [k,t]=Array.isArray(v)?v:[v,v];return `<option value="${esc(k)}" ${k===value?"selected":""}>${esc(t)}</option>`;}).join("")}</select></label>`;
  const button = (id,label,primary=false) => `<button class="btn ${primary?"primary":""}" type="button" data-action="${id}">${esc(label)}</button>`;
  const submit = label => `<div class="wide"><button class="btn primary" type="submit">${label}</button></div>`;
  let token = sessionStorage.getItem("qa-token") || "", me, data = [], selected = null, busy = false, timer;
  let cache = {};
  $("#center-title").textContent = titles[section] || section;
  $("#center-description").textContent=descriptions[section]||"";
  $("#token").value = token;
  function notice(message,error=false) { $("#notice").className=error?"qa-error":"qa-ok";$("#notice").textContent=message; }
  async function api(path,body) {
    const response = await fetch("/api/qa/"+path,{method:body===undefined?"GET":"POST",
      headers:{"Authorization":"Bearer "+token,"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || value.detail || `请求失败 ${response.status}`);
    return value;
  }
  async function perform(fn) {
    if(busy) return;
    const buttons=[...root.querySelectorAll("button")].map(b=>[b,b.disabled]);
    busy=true;buttons.forEach(([b])=>b.disabled=true);
    try {await fn();notice("操作已完成");} catch(e) {notice(e.message,true);}
    finally {busy=false;buttons.forEach(([b,disabled])=>{if(b.isConnected)b.disabled=disabled;});}
  }
  function form(id,body) {return `<form id="${id}" class="qa-form">${body}</form>`;}
  function bindForm(id,fn) {const el=$("#"+id);if(el)el.onsubmit=e=>{e.preventDefault();perform(()=>fn(Object.fromEntries(new FormData(el)),el));};}
  function bindActions(actions) {
    $("#detail").querySelectorAll("[data-action]").forEach(el=>el.onclick=()=>perform(async()=>{await actions[el.dataset.action]();}));
  }
  function facts(obj,keys) {return keys.filter(k=>obj[k]!==undefined&&obj[k]!==null).map(k=>{
    let value=obj[k];if(["started","finished"].includes(k)&&typeof value==="number")value=new Date(value*1000).toLocaleString("zh-CN");
    else if(k==="status"||k==="verdict")value=stateNames[value]||value;
    else if(k==="origin")value=value==="manual"?"人工维护":"AI 生成";
    return `<div class="qa-facts"><b>${esc(fieldNames[k]||k)}</b><span>${esc(typeof value==="object"?JSON.stringify(value):value)}</span></div>`;
  }).join("");}
  async function mutate(kind,id,action,body={}) {
    const result=await api(`${kind}/${id||"new"}/${action}`,body);
    await load();return result;
  }
  function showList(kind,items,fn) {
    data=items;let page=1;const size=12;
    const val=(x,k)=>x[k]??x.spec?.[k]??"";
    const filter=(key,label)=>{const options=[...new Set(items.map(x=>val(x,key)).filter(Boolean))];return options.length>1?`<label>${label}<select id="filter-${key}"><option value="">全部</option>${options.sort().map(v=>`<option value="${esc(v)}">${esc(stateNames[v]||v)}</option>`).join("")}</select></label>`:"";};
    $("#listing").innerHTML=panel(`${kind==="cases"?"正式用例":kind==="drafts"?"候选草稿":"记录"} · ${items.length}`,
      `<label>搜索<input id="filter" placeholder="名称、描述、标签或编号"></label><div class="qa-list-filters">${filter("status","状态")}${filter("area","测试域")}${filter("priority","优先级")}</div><div id="rows"></div><div class="qa-pagination"><button class="btn" id="prev-page" type="button">上一页</button><span id="page-info"></span><button class="btn" id="next-page" type="button">下一页</button></div>`);
    function rows() {
      const q=$("#filter").value.toLowerCase();
      const matching=items.filter(x=>JSON.stringify(x).toLowerCase().includes(q)&&["status","area","priority"].every(k=>!$("#filter-"+k)||!$("#filter-"+k).value||val(x,k)===$("#filter-"+k).value));
      const pages=Math.max(1,Math.ceil(matching.length/size));page=Math.min(page,pages);
      if(matching.length&&!matching.some(x=>x.id===selected)){selected=matching[0].id;fn(matching[0]);}
      if(!matching.length)$("#detail").innerHTML='<div class="empty">调整筛选条件后，可在这里查看记录详情。</div>';
      $("#rows").innerHTML=matching.slice((page-1)*size,page*size).map(x=>{
        const status=x.status||x.verdict||"",area=val(x,"area"),priority=val(x,"priority");
        return `<button class="qa-row" data-id="${esc(x.id)}" aria-current="${x.id===selected}"><div class="qa-row-top"><strong>${esc(x.title||x.name||x.spec?.name||x.subject||x.category||x.scope||x.id)}</strong>${priority?`<span class="chip ${esc(priority.toLowerCase())}">${esc(priority)}</span>`:""}</div><small><span class="qa-state ${esc(status)}">${esc(stateNames[status]||status)}</span>${area?" · "+esc(area):""}${x.version?" · v"+x.version:""}</small>${val(x,"desc")?`<span class="qa-row-desc">${esc(val(x,"desc"))}</span>`:""}</button>`;
      }).join("")||'<div class="empty">没有匹配记录，试试其他关键词或筛选条件。</div>';
      $("#page-info").textContent=`${matching.length} 条 · ${page} / ${pages}`;
      $("#prev-page").disabled=page<=1;$("#next-page").disabled=page>=pages;
      $("#rows").querySelectorAll("[data-id]").forEach(el=>el.onclick=()=>{selected=el.dataset.id;history.replaceState(null,"","#"+selected);$("#rows").querySelectorAll("[data-id]").forEach(r=>r.setAttribute("aria-current",String(r===el)));fn(items.find(x=>x.id===selected));});
    }
    $("#filter").oninput=()=>{page=1;rows();};
    ["status","area","priority"].forEach(k=>{const field=$("#filter-"+k);if(field)field.onchange=()=>{page=1;rows();};});
    $("#prev-page").onclick=()=>{page--;rows();};$("#next-page").onclick=()=>{page++;rows();};
    const obj=items.find(x=>x.id===(location.hash.slice(1)||selected))||items[0];
    if(obj){selected=obj.id;fn(obj);}rows();
  }
  function requirementEditor(obj) {
    const isNew=!obj?.id;obj=obj||{};
    $("#detail").innerHTML=panel(isNew?"新建需求":"需求解析",`<div class="test-points">${(obj.test_points||String(obj.acceptance||"").split(/[。\n]/)).map(x=>String(x).trim()).filter(Boolean).slice(0,8).map(x=>`<span>${esc(x)}</span>`).join("")||"<span>等待导入需求文档</span>"}</div>`+form("req-form",
      input("title","标题",obj.title)+input("owner","负责人",obj.owner)+
      text("description","描述",obj.description)+text("acceptance","验收标准（必填）",obj.acceptance)+
      input("area","测试域",obj.area)+select("priority","优先级",["P0","P1","P2","P3"],obj.priority||"P1")+
      text("scope","测试范围",obj.scope)+text("risk","风险",obj.risk)+input("tags","标签（逗号分隔）",(obj.tags||[]).join(","))+submit("保存需求"))+
      (!isNew?`<div class="qa-actions">${button("generate","AI 生成草稿",true)}${button("demo","演示生成")}${button("delete","删除需求")}</div>${facts(obj,["id","version","status"])}`:""));
    bindForm("req-form",async d=>{d.tags=d.tags.split(",").map(x=>x.trim()).filter(Boolean);d.version=obj.version;await mutate("requirements",obj.id,isNew?"create":"update",d);});
    if(!isNew)bindActions({
      generate:async()=>{await mutate("drafts",null,"generate",{requirement_id:obj.id});location.href="/factory";},
      demo:async()=>{await mutate("drafts",null,"generate",{requirement_id:obj.id,demo:true});location.href="/factory";},
      delete:async()=>{if(confirm("删除后保留追溯记录，关联未发布内容不能执行。继续？"))await mutate("requirements",obj.id,"delete");}
    });
  }
  function draftEditor(obj) {
    const s=obj.spec;
    const checks=["home_reachable","title_contains","keyword_present","path_status","element_present","search_no_redirect","player_ready","player_play","player_pause","player_seek","player_volume","player_fullscreen","player_quality","player_rate","media_range","viewport_overflow"];
    const stage = obj.status === "published" ? "已入库" : obj.review_id ? "已评审" : obj.commit ? "已同步代码" : obj.code_path ? "已生成代码" : "草稿";
    const blocker = obj.source === "demo-local-rules" ? "演示结果不能代替真实 AI 评审" : obj.status === "rejected" ? "评审未通过，需要修改后重新评审" : obj.status === "reviewed" ? "等待人工确认入库" : "下一步：同步代码并执行独立评审";
    const assetPanel = panel(
      "资产与入库状态",
      `<div class="asset-grid"><span><b>用例资产</b>${obj.code_path?"已生成受控测试代码":"尚未生成"}</span><span><b>版本绑定</b>${obj.code_hash?"已绑定评审版本":"尚未绑定"}</span><span><b>资产提交</b>${obj.commit?"已提交":"未提交"}</span><span><b>入库</b>${esc(stage)}</span></div>` +
      facts(obj,["version","status","source","commit"]) +
      `<a href="/requirements#${esc(obj.requirement_id)}">查看关联需求</a>` +
      form("draft-form", input("name","用例名称",s.name)+input("goal","用例目标",s.goal)+text("desc","描述",s.desc)+
      text("preconditions","前置条件",s.preconditions)+text("steps","操作步骤（每行一步）",s.steps)+
      text("expected","预期结果（每行一项）",s.expected||s.expected_results)+
      input("test_type","测试类型",s.test_type||"http")+input("target","目标页面",s.target)+
      input("area","测试域",s.area)+select("priority","优先级",["P0","P1","P2","P3"],s.priority)+
      input("tags","标签（逗号分隔）",s.tags.join(","))+select("smoke","冒烟",[[false,"否"],[true,"是"]],s.smoke??s.tags.includes("smoke"))+
      select("automation","自动化",[[true,"是"],[false,"仅手工设计"]],s.automation!==false)+
      text("implementation","实现说明",s.implementation)+text("risk","风险",s.risk)+
      select("kind","自动化检查类型",checks,s.check?.kind)+
      input("text","标题预期 / 关键词",s.check?.params?.text||s.check?.params?.keyword||"")+
      input("path","站内路径",s.check?.params?.path||"/")+input("expect","预期状态码",s.check?.params?.expect||200,"number")+
      input("selector","CSS选择器",s.check?.params?.selector)+input("min","最小元素数",s.check?.params?.min||1,"number")+
      input("query","搜索关键词",s.check?.params?.query)+input("seconds","播放进度秒",s.check?.params?.seconds||10,"number")+input("level","音量 0-1",s.check?.params?.level||0.5,"number")+input("rate","倍速",s.check?.params?.rate||1,"number")+input("label","清晰度标识",s.check?.params?.label||"")+input("width","视口宽度",s.check?.params?.width||390,"number")+input("height","视口高度",s.check?.params?.height||844,"number")+submit("保存新版本（必须重审）")) +
      `<div class="qa-actions">${button("diff","查看代码 / diff")}${button("sync","同步代码到本地Git")}${button("review","独立 AI 评审")}${button("publish","人工确认入库",true)}${button("delete","删除草稿")}${button("regenerate","重新生成同需求")}</div><div id="evidence"></div>`
    );
    $("#detail").innerHTML = panel("用例流水线", `<ol class="pipeline-guide"><li><b>测试点</b><span>${esc(s.test_point||s.name||"已提取")}</span></li><li><b>测试资产</b><span>${obj.code_path?"已生成":"尚未生成"}</span></li><li><b>同步</b><span>${obj.commit?"已绑定版本":"尚未提交资产仓库"}</span></li><li><b>评审</b><span>${obj.review_id?"已有评审记录":"生产模式必须真实 AI 评审"}</span></li><li><b>入库</b><span>${stage}</span></li></ol><p class="note">当前阻塞：${esc(blocker)}。系统补齐：${esc((s.system_filled||[]).join("、")||"无")}</p>`) + assetPanel;
    bindForm("draft-form",async d=>{
      const params={home_reachable:{},title_contains:{text:d.text},keyword_present:{keyword:d.text},
        path_status:{path:d.path,expect:Number(d.expect)},element_present:{selector:d.selector,min:Number(d.min)},search_no_redirect:{query:d.query},
        player_ready:{},player_play:{},player_pause:{},player_seek:{seconds:Number(d.seconds)},player_volume:{level:Number(d.level)},player_fullscreen:{},player_quality:{label:d.label},player_rate:{rate:Number(d.rate)},media_range:{},viewport_overflow:{width:Number(d.width),height:Number(d.height)}}[d.kind];
      const spec={...s,...d,steps:d.steps.split("\n").filter(Boolean),expected:d.expected.split("\n").filter(Boolean),
        tags:d.tags.split(",").map(x=>x.trim()).filter(Boolean),smoke:d.smoke==="true",automation:d.automation==="true",check:{kind:d.kind,params}};
      if(spec.smoke&&!spec.tags.includes("smoke"))spec.tags.push("smoke");if(!spec.smoke)spec.tags=spec.tags.filter(x=>x!=="smoke");
      await mutate("drafts",obj.id,"update",{version:obj.version,spec});
    });
    const display = result => {$("#evidence").innerHTML=panel("评审 / 代码证据",pretty(result));};
    bindActions({
      diff:async()=>display(await api(`drafts/${obj.id}/diff`,{})),
      sync:async()=>{if(confirm("将当前版本的 generated 文件定向提交到独立本地资产仓库，不推送。继续？"))display(await mutate("drafts",obj.id,"sync",{confirm:true}));},
      review:async()=>display(await mutate("drafts",obj.id,"review")),
      publish:async()=>{if(confirm("确认当前草稿版本、代码hash与独立评审结论，正式入库？"))display(await mutate("drafts",obj.id,"publish",{confirm:true}));},
      delete:async()=>{if(confirm("删除当前草稿？"))await mutate("drafts",obj.id,"delete");},
      regenerate:async()=>{await mutate("drafts",null,"generate",{requirement_id:obj.requirement_id});}
    });
    if(obj.review_id)api(`reviews/${obj.review_id}`).then(display).catch(e=>notice(e.message,true));
  }
  async function load() {
    clearTimeout(timer);
    if(!token){$("#listing").innerHTML='<div class="empty">请先登录，再加载工作区。</div>';return;}
    $("#listing").setAttribute("aria-busy","true");
    try {
      me=await api("me");$("#identity").textContent=me.name+" · "+({admin:"管理员",qa:"QA",rd:"RD",viewer:"只读",test_lead:"测试负责人",tech_lead:"技术负责人",project_lead:"项目负责人"}[me.role]||me.role);$("#login").classList.add("authenticated");
      $("#controls").innerHTML="";
      if(section==="requirements"){
        $("#controls").innerHTML=panel("导入需求文档",`<form id="document-form" class="document-import">
          <label class="dropzone" for="requirement-document">
            <input id="requirement-document" name="document" type="file" accept=".txt,.md,.markdown,.csv,text/plain,text/markdown,text/csv" required>
            <span class="drop-kicker">REQUIREMENT DOCUMENT</span>
            <strong>拖拽需求文档到这里，或点击选择</strong>
            <small id="document-meta">支持 UTF-8 的 Markdown、TXT、CSV · 最大 2MB</small>
          </label>
          <div class="import-options">
            ${input("owner","负责人","验收 QA")}
            ${select("priority","优先级",["P0","P1","P2","P3"],"P1")}
            ${select("mode","分析方式",[["demo","本地规则演示"],["ai","真实 AI"]],"demo")}
            <button class="btn primary analyze" type="submit">分析并生成测试用例</button>
          </div>
        </form>`);
        $("#document-form").onsubmit=async event=>{
          event.preventDefault();
          const body=new FormData(event.currentTarget);
          body.set("demo",body.get("mode")==="demo");body.delete("mode");
          await perform(async()=>{
            const file=body.get("document");
            if(!(file instanceof File))throw new Error("请选择需求文档");
            const params=new URLSearchParams({filename:file.name,owner:body.get("owner")||"文档导入",priority:body.get("priority")||"P1",demo:body.get("demo")||"false"});
            const response=await fetch("/api/qa/requirements/import?"+params,{method:"POST",headers:{Authorization:"Bearer "+token,"Content-Type":"application/octet-stream"},body:file});
            const value=await response.json();
            if(!response.ok)throw new Error(value.error||`请求失败 ${response.status}`);
            location.href="/factory";
          });
        };
        const picker=$("#requirement-document"), meta=$("#document-meta");
        picker.onchange=()=>{const file=picker.files[0];meta.textContent=file?`${file.name} · ${Math.max(1,Math.ceil(file.size/1024))} KB`:"支持 UTF-8 的 Markdown、TXT、CSV · 最大 2MB";};
        ["dragover","dragleave","drop"].forEach(type=>picker.parentElement.addEventListener(type,event=>{
          event.preventDefault();picker.parentElement.classList.toggle("dragging",type==="dragover");
          if(type==="drop"&&event.dataTransfer.files[0]){picker.files=event.dataTransfer.files;picker.onchange();}
        }));
        showList("requirements",await api("requirements"),requirementEditor);
      } else if(section==="factory"){
        cache.requirements=(await api("requirements")).filter(r=>r.status==="active");
        $("#controls").innerHTML=panel("从需求生成",form("generate-form",select("requirement_id","需求",cache.requirements.map(r=>[r.id,r.title]))+
          select("source","来源",[["ai","真实AI（需配置）"],["demo","本地规则演示（不自动通过）"]],"ai")+submit("生成至草稿池")));
        bindForm("generate-form",async d=>mutate("drafts",null,"generate",{requirement_id:d.requirement_id,demo:d.source==="demo"}));
        showList("drafts",(await api("drafts")).filter(x=>x.status!=="deleted"),draftEditor);
      } else if(section==="prompts"){
        showList("prompts",await api("prompts"),p=>{
          $("#detail").innerHTML=panel(`${p.category} v${p.version}`,facts(p,["id","active"])+
            (me.role==="admin"?form("prompt-form",text("text","Prompt正文",p.text)+submit("保存为新版本"))+
            (!p.active?`<div class="qa-actions">${button("activate","启用此版本（回滚规则）")}</div>`:""):pretty(p.text)));
          if(me.role==="admin"){
            bindForm("prompt-form",d=>mutate("prompts",null,"create",{category:p.category,text:d.text}));
            if(!p.active)bindActions({activate:()=>mutate("prompts",p.id,"activate")});
          }
        });
      } else if(section==="runs") await runs();
      else if(section==="defects") await defects();
      else if(section==="reports") await reports();
      else if(section==="outbox") await outbox();
      else if(section==="settings") await settings();
      else if(section==="history"){
        const history=await api("history");
        $("#listing").innerHTML=panel("升级前只读数据",Object.keys(history).map(k=>button(k,k)).join(""));
        $("#listing").querySelectorAll("button").forEach(b=>b.onclick=()=>$("#detail").innerHTML=panel(b.dataset.action,pretty(history[b.dataset.action])));
      } else if(section==="cases"){
        showList("cases",await api("cases"),c=>{
          const s=c.spec||c;
          const block=(heading,content)=>content?`<h3>${heading}</h3><p class="qa-prose">${esc(Array.isArray(content)?content.join("\n"):content)}</p>`:"";
          $("#detail").innerHTML=panel(c.name||"正式用例",
            `<p class="qa-prose">${esc(s.desc||"")}</p><div class="qa-actions"><a class="btn primary" href="/runs?case=${esc(c.id)}">运行这条用例</a>${c.draft_id?`<a class="btn" href="/factory#${esc(c.draft_id)}">查看草稿及评审</a>`:""}</div>`+
            facts(c,["origin","priority","area","nodeid"])+
            block("测试目标",s.goal)+block("前置条件",s.preconditions)+block("测试步骤",s.steps)+block("预期结果",s.expected||s.expected_results)+
            `<div class="qa-actions">${(c.tags||[]).map(t=>`<span class="chip">${esc(t)}</span>`).join("")}</div>`+
            `<details><summary>追溯记录与代码版本</summary>${facts(c,["id","draft_version","review_id","code_hash","commit"])}</details>`);
        });
      } else {
        const [overview,recent,defectData,cases]=await Promise.all([api("overview"),api("runs"),api("defects"),api("cases")]);
        const last=recent.find(r=>r.scope==="full"&&r.finished)||recent.find(r=>r.finished);
        const passed=last?.evidence?.counts?.passed ?? last?.counts?.passed ?? last?.passed ?? 0;
        const failed=last?.evidence?.counts?.failed ?? last?.counts?.failed ?? last?.failed ?? 0;
        const effective=passed+failed;
        const rate=effective?Math.round(passed*100/effective):0;
        const p1=(defectData.items||[]).filter(d=>d.priority==="P0"||d.priority==="P1").length;
        $("#controls").innerHTML=`<section class="dashboard-hero">
          <div><div class="eyebrow">QUALITY CONTROL CENTER / 质量驾驶舱</div><h2>正观新闻质量工作台</h2><p>掌握当前测试周期的质量状态、风险结论与交付进展。</p></div>
          <div class="hero-meta"><span>目标环境 <b>${esc(location.host||"本地环境")}</b></span><span>更新时间 <b>${new Date().toLocaleTimeString("zh-CN",{hour:"2-digit",minute:"2-digit"})}</b></span></div>
        </section>
        <div class="metric-grid">
          ${metric("正式用例",cases.length,"查看用例库","/cases","blue")}
          ${metric("需求总数",overview.requirements||0,"查看需求","/requirements","cyan")}
          ${metric("最近通过率",rate+"%",last?"基于最近一次执行":"暂无执行","/runs",rate>=90?"green":"amber")}
          ${metric("未解决缺陷",defectData.counts?.todo||0,"进入缺陷协同","/defects","red")}
          ${metric("高优风险",p1,"P0 / P1 未关闭","/defects","amber")}
        </div>
        <div class="dashboard-grid">
          <section class="dashboard-panel dashboard-status"><div class="panel-title"><span>当前质量结论</span><a href="/reports">查看报告 →</a></div>
            <div class="quality-result ${last?.status==="passed"?"is-good":"is-watch"}"><span class="result-mark">${last?.status==="passed"?"✓":"!"}</span><div><strong>${last?.status==="passed"?"质量状态稳定":"需要关注测试风险"}</strong><p>${last?`最近一次${last.scope==="full"?"全量":"专项"}执行：${stateNames[last.status]||last.status}`:"尚未完成测试执行，请从测试执行开始。"}</p></div></div>
            <div class="result-facts"><span>测试用例 <b>${effective||"—"}</b></span><span>通过 <b class="good">${passed||"—"}</b></span><span>失败 <b class="bad">${failed||"—"}</b></span></div>
          </section>
          <section class="dashboard-panel"><div class="panel-title"><span>工作流进展</span><span class="panel-caption">从需求到交付</span></div>
            <div class="flow-track">${[["01","需求","requirements"],["02","用例","factory"],["03","执行","runs"],["04","缺陷","defects"],["05","报告","reports"]].map((x,i)=>`<a href="/${x[2]==="factory"?"factory":x[2]}"><i>${x[0]}</i><b>${x[1]}</b><small>${i===0?"定义目标":i===1?"生成并评审":i===2?"运行验证":i===3?"修复回测":"输出结论"}</small></a>`).join("")}</div>
          </section>
        </div>
        <div class="dashboard-grid lower"><section class="dashboard-panel"><div class="panel-title"><span>最近执行</span><a href="/runs">全部记录 →</a></div><div class="activity-list">${recent.slice(0,5).map(r=>`<a href="/runs#${esc(r.id)}"><span class="activity-status ${esc(r.status)}"></span><div><b>${esc(r.scope||"测试执行")}</b><small>${esc(stateNames[r.status]||r.status)} · ${r.selection?.length||r.count||"—"} 条用例</small></div><time>${r.finished?new Date(r.finished*1000).toLocaleDateString("zh-CN"):"进行中"}</time></a>`).join("")||'<div class="empty">还没有执行记录</div>'}</div></section>
        <section class="dashboard-panel"><div class="panel-title"><span>待处理事项</span><span class="panel-caption">${p1+(defectData.counts?.todo||0)} 项</span></div><div class="todo-list"><a href="/factory"><b>AI 用例工厂</b><span>生成草稿、完成独立评审并确认入库</span><em>进入 →</em></a><a href="/defects"><b>缺陷协同</b><span>${defectData.counts?.todo||0} 个问题等待处理或回测</span><em>处理 →</em></a><a href="/reports"><b>测试报告</b><span>查看最近一次全量测试结论</span><em>查看 →</em></a></div></section></div>`;
        showList("runs",recent.slice(0,12),runDetail);
        $("#detail").innerHTML=panel("操作导航","<p class='qa-prose'>从左侧进入对应模块。每个页面会显示当前任务、状态和下一步操作。</p><div class='quick-links'><a href='/requirements'><b>01 / 需求中心</b><span>定义验收目标</span></a><a href='/factory'><b>02 / AI 用例工厂</b><span>生成并评审测试设计</span></a><a href='/runs'><b>03 / 测试执行</b><span>运行冒烟或全量回归</span></a><a href='/reports'><b>04 / 测试报告</b><span>形成领导可读结论</span></a></div>");
      }
      if(section==="runs" && data.some(r=>["queued","running"].includes(r.status))) timer=setTimeout(()=>{if(!busy)load();},3000);
    } catch(e) {notice(e.message,true);$("#listing").innerHTML='<div class="empty">加载失败，请检查令牌或重试刷新。</div>';}
    finally {$("#listing").removeAttribute("aria-busy");}
  }
  function runDetail(r) {
    const counts=r.evidence?.counts||{};
    const domains=[...new Set((r.selection||[]).map(id=>String(id).includes("video")?"视频播放器":"综合回归"))];
    $("#detail").innerHTML=panel("执行前确认",`<div class="result-facts"><span>用例 <b>${r.selection?.length||0}</b></span><span>测试域 <b>${esc(domains.join("、")||"—")}</b></span><span>终端 <b>桌面 / H5</b></span></div><p class="note">执行使用数据库中的正式用例；生成代码必须与评审哈希一致，缺失证据不会判为通过。</p>`)+
      panel("执行摘要",`<div class="result-facts"><span>通过 <b>${counts.passed??"—"}</b></span><span>失败 <b>${counts.failed??"—"}</b></span><span>跳过 <b>${counts.skipped??"—"}</b></span></div>`+facts(r,["id","scope","status","started","finished"])+
      `<p>失败后保留页面、截图、播放器状态和错误摘要，可从缺陷协同继续处理。</p>`+
      (["running","queued"].includes(r.status)?button("cancel","取消执行"):"")+
      (r.scope==="full"&&r.finished?button("report","生成报告快照"):"")+
      `<details><summary>原始执行证据</summary>${pretty(r.evidence||r.selection)}</details>`);
    bindActions({cancel:()=>mutate("runs",r.id,"cancel"),report:async()=>{const p=await mutate("reports",null,"create",{run_id:r.id});location.href="/reports#"+p.id;}});
  }
  async function runs() {
    const [cases,requirements]=await Promise.all([api("cases"),api("requirements")]);
    const options=(items,key)=>[...new Set(items.map(x=>x[key]).filter(Boolean))].sort();
    const valueBox=(id,label,values)=>`<label class="scope-value" data-for="${id}">${label}<select name="value">${values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join("")||`<option value="">暂无可选项</option>`}</select></label>`;
    $("#controls").innerHTML=panel("新建执行",form("run-form",
      select("scope","执行范围",[["full","全部正式用例"],["smoke","冒烟测试"],["selected","只运行下方勾选的用例"],["area","按测试域"],["priority","按优先级"],["tag","按标签"],["requirement","按某个需求"]],"full")+
      valueBox("area","选择测试域",options(cases,"area"))+
      valueBox("priority","选择优先级",options(cases,"priority"))+
      valueBox("tag","选择标签",options(cases.flatMap(c=>(c.tags||[]).map(t=>t)),null))+
      valueBox("requirement","选择需求",requirements.map(r=>r.id).filter(id=>cases.some(c=>c.requirement_id===id)))+
      `<p class="scope-help" id="scope-help">全部正式用例：运行当前用例库中所有已入库用例。</p>`+
      `<div class="wide qa-checks">${cases.map(c=>`<label><input type="checkbox" name="ids" value="${esc(c.id)}">${esc(c.name)} · ${esc(c.priority)} · ${esc(c.area||"未分类")}</label>`).join("")}</div>`+submit("开始执行"))+
      '<p class="note">首次使用建议选择“冒烟测试”。只有已入库用例可以执行；生成用例的代码必须与评审时的哈希一致。</p>');
    const scope=$("#run-form select[name=scope]"), help=$("#scope-help");
    const helps={full:"运行全部已入库用例，适合发布前全量回归。",smoke:"只运行带 smoke 标签的核心用例，适合快速确认主要流程。",selected:"只运行下方手动勾选的用例。",area:"按测试域运行，例如视频播放器、首页与导航。",priority:"按 P0、P1 等优先级运行。",tag:"按用例标签运行，例如 search、video。",requirement:"运行某一份需求文档生成并已入库的全部用例。"};
    const refresh=()=>{const value=scope.value;[...$("#run-form").querySelectorAll(".scope-value")].forEach(el=>el.hidden=el.dataset.for!==value);$("#run-form .qa-checks").hidden=value!=="selected";help.textContent=helps[value]||"";};
    scope.onchange=refresh;refresh();
    bindForm("run-form",async(d,el)=>{const formData=new FormData(el);d.ids=formData.getAll("ids");if(!["area","priority","tag","requirement"].includes(d.scope))delete d.value;await mutate("runs",null,"create",d);});
    const requested=new URLSearchParams(location.search).get("case");
    if(requested&&cases.some(c=>c.id===requested)){
      $("#run-form select[name=scope]").value="selected";
      $("#run-form").querySelectorAll('input[name="ids"]').forEach(i=>i.checked=i.value===requested);
    }
    showList("runs",await api("runs"),runDetail);
  }
  async function defects() {
    let users=[];if(me.role==="admin")users=await api("users");
    showList("defects",await api("defects"),d=>{
      $("#detail").innerHTML=panel("缺陷详情",facts(d,["id","title","priority","status","case_id","run_id","owner_id","routed_owner_id","rd_run_id","qa_run_id"])+pretty(d.evidence)+
        form("fix-form",text("note","修复说明",d.fix?.note)+input("commit","修复commit",d.fix?.commit)+input("pr","PR URL",d.fix?.pr)+submit("提交修复并真实自回测"))+
        (users.length?form("assign-form",select("owner_id","分派RD",users.filter(u=>u.role==="rd").map(u=>[u.id,u.name]),d.routed_owner_id)+submit("分派负责人")):"")+
        `<div class="qa-actions">${button("claim","认领")}${button("verify","QA 独立真实回测",true)}${button("close","关闭已验证缺陷")}</div>`+pretty(d.fix||{}));
      bindForm("fix-form",v=>mutate("defects",d.id,"fix",v));
      bindForm("assign-form",v=>mutate("defects",d.id,"assign",v));
      bindActions({claim:()=>mutate("defects",d.id,"claim"),verify:()=>mutate("defects",d.id,"verify"),close:()=>mutate("defects",d.id,"close")});
    });
  }
  async function reports() {
    const runs=(await api("runs")).filter(r=>r.scope==="full"&&r.finished&&["passed","failed"].includes(r.status));
    $("#controls").innerHTML=panel("从完成的全量运行生成快照",form("report-form",select("run_id","全量运行",runs.map(r=>[r.id,`${r.id} / ${r.status}`]))+input("title","报告标题","全量测试报告")+submit("生成报告")));
    bindForm("report-form",v=>mutate("reports",null,"create",v));
    showList("reports",await api("reports"),r=>{
      $("#detail").innerHTML=panel("不可变报告快照",facts(r,["id","title","verdict","run_id","source"])+
        `<div class="qa-actions">${button("mail","生成邮件草稿",true)}</div>`+pretty(r.risks)+pretty(r.run_snapshot.evidence));
      bindActions({mail:async()=>{const m=await mutate("outbox",null,"create",{report_id:r.id});location.href="/outbox#"+m.id;}});
    });
  }
  async function outbox() {
    showList("outbox",await api("outbox"),m=>{
      $("#detail").innerHTML=panel("邮件预览",facts(m,["id","status","transport","report_id","defect_id"])+
        form("mail-form",input("to","收件人（逗号分隔）",m.to.join(","))+input("cc","抄送（逗号分隔）",m.cc.join(","))+
        input("subject","主题",m.subject)+text("body","自定义正文",m.body)+submit("保存草稿"))+
        `<h3>不可移除的证据与风险摘要</h3>${pretty(m.evidence_summary||"")}<div class="qa-actions">${button("send","发送到本地发件箱",true)}${button("archive","归档")}${button("download","下载 .eml")}</div>`);
      bindForm("mail-form",v=>{v.to=v.to.split(",").map(x=>x.trim()).filter(Boolean);v.cc=v.cc.split(",").map(x=>x.trim()).filter(Boolean);return mutate("outbox",m.id,"update",v);});
      bindActions({send:()=>mutate("outbox",m.id,"send"),archive:()=>mutate("outbox",m.id,"archive"),download:async()=>{
        const r=await fetch(`/api/qa/outbox/${m.id}/eml`,{headers:{Authorization:"Bearer "+token}});
        if(!r.ok)throw new Error("下载失败");
        const url=URL.createObjectURL(await r.blob()),a=document.createElement("a");a.href=url;a.download=m.id+".eml";a.click();setTimeout(()=>URL.revokeObjectURL(url),500);
      }});
    });
  }
  async function settings() {
    const [s,users]=await Promise.all([api("settings"),api("users")]);
    const rd=users.filter(u=>u.role==="rd");
    $("#listing").innerHTML=panel("管理员配置",form("user-form",input("name","姓名")+select("role","角色",[["qa","QA"],["rd","RD"],["test_lead","测试负责人"],["tech_lead","技术负责人"],["project_lead","项目负责人"],["viewer","只读"],["admin","管理员"]],"rd")+input("email","负责人邮箱","", "email")+submit("创建用户（令牌仅显示一次）")))+
      panel("邮件与人员路由",form("settings-form",input("qa","默认收件人",(s.config.qa||[]).join(","))+input("leaders","默认抄送",(s.config.leaders||[]).join(","))+
        select("owner","默认RD",[["","未配置"],...rd.map(u=>[u.id,u.name])],s.config.routing.default||"")+
        input("area","指定测试域")+select("area_owner","域负责人",[["","不修改"],...rd.map(u=>[u.id,u.name])])+
        input("browsers","可用浏览器",(s.config.capabilities?.browsers||[]).join(","))+
        input("accounts","可用测试账号说明",s.config.capabilities?.accounts||"")+select("video","视频能力",[["false","未确认"],["true","支持"]],String(!!s.config.capabilities?.video))+submit("保存设置")));
    $("#detail").innerHTML=panel("接入入口",`<div class="integration-grid"><article><b>AI 接入</b><span>${s.ai.configured?"已配置":"未配置"} · ${esc(s.ai.model||"未选择模型")}</span></article><article><b>登录接入</b><span>当前为服务端令牌，可扩展企业 SSO</span></article><article><b>邮件接入</b><span>当前仅本地发件箱，SMTP 已预留但不会自动外发</span></article></div>`)+panel("AI 配置（密钥仅服务端环境设置）",pretty(s.ai))+
      panel("人员邮箱",users.map(u=>form("u-"+u.id,input("email",u.name+" / "+u.role,u.email,"email")+submit("保存邮箱"))).join(""))+
      `<div class="qa-actions">${button("audit","查看审计")}</div><div id="audit"></div>`;
    bindForm("user-form",async d=>{const u=await api("users",d);await load();$("#detail").innerHTML=panel("请妥善保存用户令牌（仅显示此次）",pretty(u));});
    bindForm("settings-form",async d=>{
      const routing={...s.config.routing};if(d.owner)routing.default=d.owner;else delete routing.default;
      if(d.area&&d.area_owner)routing[d.area]=d.area_owner;
      await mutate("settings",null,"update",{routing,qa:d.qa.split(",").filter(Boolean).map(x=>x.trim()),leaders:d.leaders.split(",").filter(Boolean).map(x=>x.trim()),
        capabilities:{browsers:d.browsers.split(",").filter(Boolean),accounts:d.accounts,video:d.video==="true"}});
    });
    users.forEach(u=>bindForm("u-"+u.id,d=>mutate("users",u.id,"update",d)));
    bindActions({audit:async()=>{$("#audit").innerHTML=pretty(await api("audit"));}});
  }
  $("#login").onsubmit=e=>{e.preventDefault();token=$("#token").value.trim();sessionStorage.setItem("qa-token",token);perform(load);};
  $("#logout").onclick=()=>{token="";sessionStorage.removeItem("qa-token");location.reload();};
  $("#reload").onclick=()=>perform(load);
  load();
})();
