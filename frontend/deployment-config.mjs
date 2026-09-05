const LOCAL_HOSTS=new Set(["localhost","127.0.0.1","[::1]"]);

export function assertBrowserDeployment(config,pageLocation) {
  const deployment=String(config?.deployment||"");
  const local=LOCAL_HOSTS.has(String(pageLocation?.hostname||"").toLowerCase());
  if(!local&&!['staging','production'].includes(deployment)) {
    throw new Error('This deployment is missing an explicit staging or production browser configuration.');
  }
  if(deployment==='production') {
    if(!String(config?.clerkPublishableKey||'').startsWith('pk_live_')) throw new Error('Production Clerk sign-in is not configured.');
    if(config?.canonicalWebOrigin!==pageLocation?.origin) throw new Error('Production canonical web origin is not configured.');
    if(config?.cspDeploymentConfigured!==true) throw new Error('Production CSP deployment is not confirmed.');
    const api=new URL(config?.apiBase);
    if(api.protocol!=='https:'||api.origin!==String(config.apiBase).replace(/\/$/,'')) throw new Error('Production API origin is invalid.');
  }
}
