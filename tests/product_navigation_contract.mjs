import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
const source=fs.readFileSync(new URL("../frontend/assets/js/product_navigation.js",import.meta.url),"utf8");
const context={URLSearchParams};context.globalThis=context;vm.runInNewContext(source,context);
const nav=context.ScozProductNavigation;
assert.deepEqual({...nav.parseHash("#products")},{kind:"products",query:"",page:1});
assert.equal(nav.serializeRoute({kind:"products",query:"смеситель кухня",page:3}),"#products?q=%D1%81%D0%BC%D0%B5%D1%81%D0%B8%D1%82%D0%B5%D0%BB%D1%8C+%D0%BA%D1%83%D1%85%D0%BD%D1%8F&page=3");
assert.deepEqual({...nav.parseHash("#products/17/competitors")},{kind:"workspace",productId:17,section:"competitors"});
assert.equal(nav.documentTitle({kind:"products",query:"",page:1}),"Товары — SCOZ");
assert.equal(nav.documentTitle({kind:"workspace",productId:17,section:"competitors"},"Смеситель"),"Смеситель · Конкуренты — SCOZ");
assert.equal(nav.serializeRoute({kind:"products",query:"",page:1}),"#products");
assert.deepEqual({...nav.parseHash(nav.serializeRoute({kind:"products",query:"Ёж 🧰",page:2}))},{kind:"products",query:"Ёж 🧰",page:2});
for(const hash of ["#products?page=0","#products?page=-1","#products?page=1.5","#products/0/competitors","#products/-2/competitors","#products/01/competitors","#products/1/diagnostics","#products?q="+"я".repeat(201),"#wat"]){assert.equal(nav.parseHash(hash).kind,"invalid",hash);}
assert.deepEqual({...nav.parseHash("")},{kind:"products",query:"",page:1});
assert.deepEqual({...nav.parseHash("#data")},{kind:"data"});
assert.deepEqual({...nav.parseHash("#settings")},{kind:"settings"});
console.log("product navigation contract: PASS");
