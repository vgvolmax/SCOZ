(function(root){
  "use strict";
  const invalid=()=>({kind:"invalid",reason:"INVALID_ROUTE"});
  function parseHash(hash){
    if(!hash||hash==="#")return {kind:"products",query:"",page:1};
    if(hash==="#data")return {kind:"data"};
    if(hash==="#settings")return {kind:"settings"};
    const workspace=/^#products\/([1-9]\d*)\/competitors$/.exec(hash);
    if(workspace){const productId=Number(workspace[1]);return Number.isSafeInteger(productId)?{kind:"workspace",productId,section:"competitors"}:invalid();}
    const match=/^#products(?:\?(.*))?$/.exec(hash);
    if(!match)return invalid();
    try{
      const params=new URLSearchParams(match[1]||"");
      for(const key of params.keys())if(key!=="q"&&key!=="page")return invalid();
      const query=params.get("q")||"";
      if(query.length>200)return invalid();
      const rawPage=params.get("page");
      if(rawPage!==null&&!/^[1-9]\d*$/.test(rawPage))return invalid();
      const page=rawPage===null?1:Number(rawPage);
      if(!Number.isSafeInteger(page))return invalid();
      return {kind:"products",query,page};
    }catch{return invalid();}
  }
  function serializeRoute(route){
    if(route.kind==="products"){
      const params=new URLSearchParams();
      if(route.query)params.set("q",route.query);
      if(route.page!==1)params.set("page",String(route.page));
      const query=params.toString();return `#products${query?`?${query}`:""}`;
    }
    if(route.kind==="workspace")return `#products/${route.productId}/competitors`;
    if(route.kind==="data")return "#data";
    if(route.kind==="settings")return "#settings";
    return "#products";
  }
  function documentTitle(route,productTitle){
    if(route.kind==="workspace")return `${productTitle||`Ozon SKU ${route.productId}`} · Конкуренты — SCOZ`;
    return `${route.kind==="data"?"Данные":route.kind==="settings"?"Настройки":"Товары"} — SCOZ`;
  }
  root.ScozProductNavigation=Object.freeze({parseHash,serializeRoute,documentTitle});
})(globalThis);
