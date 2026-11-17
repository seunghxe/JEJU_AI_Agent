// Optional Kakao renderer. Only the public JavaScript platform key reaches the browser.
const KakaoView = (() => {
  let K, km, iw, items=[], full=[], pair=[], drawing=null, scheduled=false;
  const pos=(a,b)=>new K.LatLng(+a,+b);
  function clear(){iw?.close();items.forEach(item=>item.setMap(null));items=[];}
  function fit(coords){
    if (!coords.length) return;
    const bounds=new K.LatLngBounds(); coords.forEach(p=>bounds.extend(pos(...p)));
    if(coords.every(p=>p[0]===coords[0][0]&&p[1]===coords[0][1])){km.setCenter(pos(...coords[0]));km.setLevel(4);}
    else km.setBounds(bounds,55,32,55,32);
  }
  function point(lat,lon,label,css,activate,title,background){
    const btn=document.createElement("button");btn.type="button";btn.className="kpoint "+css;btn.textContent=label;
    if(background)btn.style.background=background;
    btn.title=title;btn.setAttribute("aria-label",title);
    const loc=pos(lat,lon);btn.onclick=()=>activate(loc);
    items.push(new K.CustomOverlay({map:km,position:loc,content:btn,clickable:true,zIndex:css==="plan"?5:2}));
  }
  function show(loc,html){iw?.close(); iw=new K.InfoWindow({position:loc,content:html,removable:true});iw.open(km);}
  function stations(){
    if(!km||drawing)return;
    clear();
    const proj=km.getProjection(), bound=km.getBounds(), groups=new Map();
    state.points.forEach(p=>{
      const ll=pos(p[0],p[1]); if(!bound.contain(ll))return;
      const pt=proj.containerPointFromCoords(ll),key=km.getLevel()>6?Math.floor(pt.x/56)+":"+Math.floor(pt.y/56):p;
      if(!groups.has(key))groups.set(key,[]);groups.get(key).push(p);
    });
    groups.forEach(g=>{
      const p=g[0];
      if(g.length===1){point(p[0],p[1],"","dot",ll=>show(ll,infoPopup(p[2],p[4])),p[2],TONE[p[3]]);return;}
      const avg=i=>g.reduce((s,r)=>s+r[i],0)/g.length;
      const bad=g.filter(r=>r[3]==="bad").length,warn=g.filter(r=>r[3]==="warn").length;
      point(avg(0),avg(1),String(g.length),"group",ll=>{km.setCenter(ll);km.setLevel(km.getLevel()-2);},g.length+"개 시설 확대",TONE[bad>=Math.max(2,g.length*.2)?"bad":bad+warn>=Math.max(2,g.length*.25)?"warn":"good"]);
    });
  }
  function overview(){drawing=null;$("#kfit").hidden=true;clear();fit(JEJU_BOUNDS);stations();}
  function result(r){
    clear();drawing=r;
    const xy=p=>[p.lat,p.lon], a=r.A,b=r.B;pair=[xy(a)];if(b)pair.push(xy(b));full=[...pair,xy(r.dest)];
    if(r.origin)full.push(xy(r.origin));
    (r.alternatives||[]).forEach(s=>point(s.lat,s.lon,"","dot",ll=>show(ll,infoPopup(s.name,s)),s.name,"#64748b"));
    for(const [s,letter,color] of [[a,"A","#2f6bff"],[b,"B","#087d75"]]){
      if(!s)continue;
      const coords=s.driving?.coordinates||[];
      if(coords.length>1){items.push(new K.Polyline({map:km,path:coords.map(p=>pos(...p)),strokeWeight:5,strokeColor:color,strokeOpacity:.85,strokeStyle:letter==="B"?"shortdash":"solid"}));full.push(...coords);}
      point(s.lat,s.lon,letter,"plan",ll=>show(ll,infoPopup("Plan "+letter+" · "+s.name,s)),s.name,color);
    }
    for(const [s,label] of [[r.dest,"목적지"],[r.origin,"출발"]]){
      if(!s||pair.some(p=>Math.abs(p[0]-s.lat)+Math.abs(p[1]-s.lon)<.00005))continue;
      point(s.lat,s.lon,label,"location",ll=>show(ll,"<div class='klabel'>"+esc(s.name)+"</div>"),s.name);
    }
    fit(full);$("#kfit").hidden=false;
  }
  async function start(key){
    if(!key)return;
    const host=$("#kmap");
    try{
      await new Promise((ok,fail)=>{
        const script=document.createElement("script"); const timer=setTimeout(()=>fail(Error("지도 연결 지연")),7000);
        script.src="https://dapi.kakao.com/v2/maps/sdk.js?autoload=false&appkey="+encodeURIComponent(key);
        script.onerror=()=>{clearTimeout(timer);fail(Error("지도 설정 확인 필요"));};
        script.onload=()=>{if(!window.kakao?.maps){clearTimeout(timer);fail(Error("SDK 미연결"));return;}window.kakao.maps.load(()=>{clearTimeout(timer);ok();});};document.head.append(script);
      });
      K=window.kakao.maps;host.hidden=false;
      km=new K.Map(host,{center:pos(33.37,126.55),level:10});km.addControl(new K.ZoomControl(),K.ControlPosition.RIGHT);
      $("#map").style.visibility="hidden";
      K.event.addListener(km,"idle",()=>{if(!drawing&&!scheduled){scheduled=true;requestAnimationFrame(()=>{scheduled=false;stations();});}});
      $("#kfit").onclick=e=>{const mode=e.target.dataset.kfit;if(mode)fit(mode==="all"?full:pair);};
      new ResizeObserver(()=>km.relayout()).observe(host);
      if(state.current?.ok&&state.view==="recommend")result(state.current);else overview();
    }catch(e){km=null;host.hidden=true;$("#map").style.visibility="";$("#kfit").hidden=true;$("#mapChip").title="카카오 지도 연결이 어려워 기본 지도를 사용합니다.";}
  }
  return {start,stations,overview,result,get ready(){return !!km;}};
})();
