import assert from "node:assert/strict";
import test from "node:test";
import config from "../product-config.mjs";
import { shouldEmitLandingEvent } from "../analytics-boundary.mjs";

const production={deployment:"production",landingAnalyticsEnabled:true};
test("checked-in and local/test web never emit acquisition analytics",()=>{
  assert.equal(shouldEmitLandingEvent(config,new URL("http://127.0.0.1:4173/")),false);
  assert.equal(shouldEmitLandingEvent(production,new URL("http://localhost:4173/")),false);
  assert.equal(shouldEmitLandingEvent(production,new URL("https://localhost/")),false);
  assert.equal(shouldEmitLandingEvent({deployment:"test",landingAnalyticsEnabled:true},new URL("https://app.example/")),false);
});
test("explicit production deployment on a nonlocal HTTPS origin can emit",()=>{
  assert.equal(shouldEmitLandingEvent(production,new URL("https://sportabase.example/")),true);
});
