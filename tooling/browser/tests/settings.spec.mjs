import { test, expect } from "@playwright/test";
import contract from "../../../frontend/preferences-contract.json" with { type: "json" };
import { startServer, stopServer } from "../serve.mjs";

let staticServer;
test.beforeAll(async () => { staticServer = await startServer(); });
test.afterAll(async () => { await stopServer(staticServer); });

async function fixture(page, signedIn = true) {
  // Only the test runner replaces this module. Production has no flag, query
  // parameter or global that can select this adapter; the backend verifies JWTs.
  await page.route("**/auth-provider.mjs", route => route.fulfill({ contentType: "text/javascript", body: `
    export const auth = { state: { loaded:true,signedIn:${signedIn},label:'reader@example.test',error:'' },
      subscribe(fn) {fn(this.state);return ()=>{}}, token:async()=>${signedIn ? "'local-browser-adapter'" : "null"},
      signIn:async()=>{},signUp:async()=>{},signOut:async()=>{window.__clerkSignedOut=true},manage:async()=>{} };
    export async function initializeAuth() {}
  ` }));
  let state = { version:contract.version, account:{id:"acct_local",status:"active"}, account_revision:1,device_revision:1,
    device:{device_id:"device",name:"Web browser",platform:"web"}, follows_defaults:true,
    defaults:{...contract.defaults},overrides:{},effective:{...contract.defaults} };
  let cleared = false;
  const bootstrapBodies=[];
  let deviceSignOuts=0;
  await page.route("https://cdn.jsdelivr.net/**", route => route.abort());
  await page.route("https://sportabase-api.onrender.com/**", async route => {
    const request = route.request(), url = new URL(request.url());
    const body = request.postDataJSON();
    if (url.pathname.startsWith("/account") && !request.headers().authorization) return route.fulfill({status:401, json:{detail:"Sign in"}});
    if (url.pathname === "/account/bootstrap") { bootstrapBodies.push(body); state.legacy_migration={status:"claimed"}; }
    if (url.pathname === "/account/device/sign-out") deviceSignOuts++;
    if (url.pathname === "/account/preferences") {
      if (body.scope === "account") { state.defaults={...state.defaults,...body.preferences}; state.account_revision++; }
      else { state.overrides={...state.overrides,...body.preferences}; state.follows_defaults=body.follows_defaults ?? state.follows_defaults; state.device_revision++; }
      state.effective={...state.defaults,...(state.follows_defaults?{}:state.overrides)};
    }
    if (request.method() === "DELETE") { cleared=true; return route.fulfill({status:204}); }
    let data = state;
    if (url.pathname === "/account/activity") data={items:cleared?[]:[{id:"act",kind:"article",title:"A carefully reported match",url:"https://example.com/story",created_at:1788610000,platform:"web"}],next:null};
    else if (url.pathname === "/account/devices") data={items:[{name:"Web browser",platform:"web",current:true,follows_defaults:state.follows_defaults}]};
    else if (url.pathname === "/notifications/web/config") data={enabled:false};
    else if (url.pathname === "/notifications/web/subscriptions") data={items:[]};
    else if (url.pathname === "/health") data={ok:true};
    else if (url.pathname.includes("insight")) data={};
    await route.fulfill({json:data});
  });
  await page.goto("/");
  return {bootstrapBodies,get deviceSignOuts(){return deviceSignOuts;}};
}
async function section(page, name) {
  const target = page.locator("#settings-nav").getByRole("button",{name,exact:true});
  if (!await target.isVisible()) await page.getByRole("button", {name:"Back to Settings"}).click();
  await target.click();
}
async function open(page) { await page.locator("#open-settings").click(); await expect(page.locator("#settings-dialog")).toBeVisible(); }
async function overflowReport(page) {
  return page.evaluate(() => [...document.querySelectorAll("body *")].flatMap(element => {
    const rect = element.getBoundingClientRect();
    return rect.right > innerWidth + 1 || rect.left < -1
      ? [{ tag: element.tagName, id: element.id, className: String(element.className), left: rect.left, right: rect.right, width: rect.width }]
      : [];
  }).slice(0, 12));
}

test("public landing and product action gate", async ({page}) => {
  await fixture(page,false);
  await expect(page.locator("#settings-dialog")).not.toBeVisible();
  await expect(page.getByRole("heading",{name:/Understand the story/})).toBeVisible();
  await page.locator("#analyze-button").click();
  await expect(page.locator("#settings-dialog")).toBeVisible();
  await expect(page.locator("#settings-content").getByRole("button",{name:"Sign in",exact:true})).toBeVisible();
});

test("keyboard Escape focus restore and visible focus", async ({page}) => {
  await fixture(page); await open(page);
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => getComputedStyle(document.activeElement).outlineStyle)).toBe("solid");
  for(let i=0;i<18;i++) { await page.keyboard.press("Tab"); expect(await page.evaluate(()=>Boolean(document.activeElement.closest("#settings-dialog")))).toBe(true); }
  await page.keyboard.press("Escape"); await expect(page.locator("#settings-dialog")).not.toBeVisible();
  await expect(page.locator("#open-settings")).toBeFocused();
});

test("appearance account defaults device overrides and follow reset", async ({page}) => {
  await fixture(page); await open(page); await section(page,"Appearance");
  await expect(page.getByRole("button",{name:"Save changes"})).toBeDisabled();
  await page.getByLabel("Settings scope").selectOption("account");
  await page.locator('[name="appearance"]').selectOption("dark");
  await expect(page.getByRole("button",{name:"Save changes"})).toBeEnabled();
  await expect(page.locator("html")).toHaveAttribute("data-theme","dark");
  await page.getByRole("button",{name:"Save changes"}).click();
  await expect(page.locator("#settings-status")).toHaveText("Saved to account defaults");
  await expect(page.getByRole("button",{name:"Save changes"})).toBeDisabled();
  await page.getByLabel("Settings scope").selectOption("device");
  await expect(page.locator('[name="appearance"]')).toBeDisabled();
  await expect(page.getByRole("button",{name:"Save changes"})).toBeDisabled();
  await page.getByLabel("Use account defaults on this device").uncheck();
  await expect(page.locator('[name="appearance"]')).toBeEnabled();
  await page.locator('[name="appearance"]').selectOption("light");
  await page.locator('[name="contrast"]').selectOption("high");
  await page.locator('[name="text_size"]').selectOption("large");
  await page.locator('[name="motion"]').selectOption("reduce");
  await page.getByRole("button",{name:"Save changes"}).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme","light");
  await expect(page.locator("html")).toHaveAttribute("data-contrast","high");
  await expect(page.locator("html")).toHaveAttribute("data-text-size","large");
  await expect(page.locator("html")).toHaveAttribute("data-motion","reduce");
  await page.getByLabel("Use account defaults on this device").check();
  await expect(page.locator("html")).toHaveAttribute("data-theme","dark");
});

test("system theme and motion react to environment", async ({page}) => {
  await page.emulateMedia({colorScheme:"dark", reducedMotion:"reduce"}); await fixture(page);
  await expect(page.locator("html")).toHaveAttribute("data-theme","dark");
  await expect(page.locator("html")).toHaveAttribute("data-motion","reduce");
  await page.emulateMedia({colorScheme:"light", reducedMotion:"no-preference"});
  await expect(page.locator("html")).toHaveAttribute("data-theme","light");
});

test("notification relocation activity and destructive confirmation", async ({page}) => {
  await fixture(page);
  await expect(page.locator("#browser-notification-controls")).not.toBeVisible();
  await open(page); await section(page,"Notifications");
  await expect(page.locator("#browser-notification-controls")).toBeVisible();
  await page.getByLabel("Settings scope").selectOption("account");
  await expect(page.locator('[name="quiet_hours_start"]')).not.toBeVisible();
  await page.getByLabel("Allow push delivery").uncheck();
  await expect(page.getByLabel("Entity alerts")).toBeDisabled();
  await expect(page.getByLabel("Quiet hours", { exact: true })).toBeDisabled();
  await expect(page.locator('[name="quiet_hours_start"]')).not.toBeVisible();
  await page.getByLabel("Allow push delivery").check();
  await page.getByLabel("Quiet hours", { exact: true }).check();
  await expect(page.locator('[name="quiet_hours_start"]')).toBeVisible();
  await section(page,"Appearance"); await section(page,"Notifications");
  await expect(page.locator("#browser-notification-controls")).toBeVisible();
  await section(page,"My Activity");
  await expect(page.getByRole("link",{name:"A carefully reported match"})).toBeVisible();
  await section(page,"Privacy & Data"); await page.getByRole("button",{name:"Clear My Activity",exact:true}).click();
  await expect(page.locator("#data-confirmation")).toBeVisible();
  await page.locator("#data-confirmation").getByRole("button",{name:"Cancel"}).click();
  await expect(page.locator("#data-confirmation")).not.toBeVisible();
  await expect(page.getByRole("button",{name:"Clear My Activity",exact:true})).toBeFocused();
  await page.getByRole("button",{name:"Clear My Activity",exact:true}).click();
  await page.locator("#data-confirmation").getByRole("button",{name:"Clear My Activity"}).click();
  await section(page,"My Activity"); await expect(page.locator("#settings-status")).toContainText("No activity found");
});

test("localhost fixture creates no landing acquisition event",async({page})=>{
  let landingEvents=0;
  page.on("request",request=>{if(new URL(request.url()).pathname==="/product-events/landing")landingEvents++;});
  await fixture(page,false);
  await page.waitForTimeout(100);
  expect(landingEvents).toBe(0);
});

test("web legacy claim is attempted once and sign-out revokes device first",async({page})=>{
  const harness=await fixture(page);
  await expect.poll(()=>harness.bootstrapBodies.length).toBe(1);
  expect(harness.bootstrapBodies[0].legacy_client_id).toBeTruthy();
  await expect.poll(()=>page.evaluate(()=>localStorage.getItem("sportabase:legacy-migration:v1"))).toBe("complete");
  await page.reload();
  await expect.poll(()=>harness.bootstrapBodies.length).toBe(2);
  expect(harness.bootstrapBodies[1].legacy_client_id).toBeUndefined();
  await open(page);
  await page.getByRole("button",{name:"Sign out",exact:true}).click();
  await expect.poll(()=>harness.deviceSignOuts).toBe(1);
  await expect.poll(()=>page.evaluate(()=>window.__clerkSignedOut)).toBe(true);
});

for (const width of [320,768,1440]) test(`settings fits ${width}px with accessibility appearance`,async ({page},testInfo)=>{
  await page.setViewportSize({width,height:900}); await fixture(page); await open(page);
  await section(page,"Appearance"); await page.getByLabel("Settings scope").selectOption("account");
  await page.locator('[name="text_size"]').selectOption("large");
  await page.locator('[name="contrast"]').selectOption("high");
  await page.locator('[name="motion"]').selectOption("reduce");
  await page.getByRole("button",{name:"Save changes"}).click();
  await expect(page.locator("html")).toHaveAttribute("data-text-size","large");
  await expect(page.locator("html")).toHaveAttribute("data-contrast","high");
  await expect(page.locator("html")).toHaveAttribute("data-motion","reduce");
  for(const name of ["Account","Appearance","Notifications","Analysis","My Activity","Language & Region","Privacy & Data","Devices/Sessions","Support/About"]) {
    await section(page,name);
    expect(await page.locator("#settings-dialog").evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBe(true);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1), JSON.stringify(await overflowReport(page))).toBe(true);
  }
  await section(page,"Appearance"); await page.screenshot({path:testInfo.outputPath(`settings-${width}.png`)});
});
