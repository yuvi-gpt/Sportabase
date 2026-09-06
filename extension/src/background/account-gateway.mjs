const API_RULES = [
  ['POST', /^\/(analyze(?:\/video)?|resolve-content|content\/browser-capture)$/],
  ['GET', /^\/watchlists(?:\/alerts)?(?:\?[^#]*)?$/],
  ['POST', /^\/watchlists(?:\/alerts\/reconcile|\/alerts\/[a-zA-Z0-9_-]{1,128}\/read)?$/],
  ['DELETE', /^\/watchlists\/[a-zA-Z0-9_-]{1,128}$/],
];
export class AccountGatewayError extends Error {
  constructor(message, {status=0, code='gateway_error'}={}) {
    super(message);
    this.name='AccountGatewayError';
    this.status=Number.isInteger(status)&&status>=0&&status<=599?status:0;
    this.code=typeof code==='string'&&/^[a-z0-9_]{1,64}$/.test(code)?code:'gateway_error';
  }
}
export function serializeGatewayError(error) {
  return {
    message:String(error?.message||'Extension account operation failed.').slice(0,500),
    status:error instanceof AccountGatewayError?error.status:0,
    code:error instanceof AccountGatewayError?error.code:'gateway_error',
  };
}
export function validSender(sender, extensionId) {
  return sender?.id === extensionId && Number.isInteger(sender.tab?.id) && sender.frameId === 0 && /^https?:\/\//.test(sender.url || '');
}
export function validExtensionPageSender(sender, extensionId, pageUrl) {
  return sender?.id === extensionId && (sender.frameId === undefined || sender.frameId === 0) && sender.url === pageUrl;
}
export function validateApiMessage(message) {
  if (!message || Object.keys(message).some(key=>!['type','requestId','path','method','body'].includes(key))) throw new Error('Invalid request message.');
  if (!/^[a-zA-Z0-9_-]{1,80}$/.test(message.requestId || '') || typeof message.path !== 'string' || message.path.length>4096 || message.path.includes('..') || message.path.includes('\\') || !API_RULES.some(([method,pattern])=>message.method===method&&pattern.test(message.path))) throw new Error('Unsupported product operation.');
  if (JSON.stringify(message.body || {}).length>500000) throw new Error('Request is too large.');
  if (message.method!=='POST'&&message.body!==undefined) throw new Error('Unexpected request body.');
  return message;
}
const LOCAL_KEYS = new Set(['sportabaseAppearance','sportabaseHighContrast','sportabaseTextScale','sportabaseDensity','sportabaseMotionLevel','sportabaseDetailLevel','sportabasePanelPosition','sportabaseSizeMode','sportabaseCustomWidth','sportabaseCustomHeight','sportabaseLeft','sportabaseTop','sportabaseHorizontalAnchor','sportabaseEdgeOffset','sportabaseRememberPosition']);
const PRESENTATION_MAPPING = Object.freeze({
  appearance:'sportabaseAppearance',contrast:'sportabaseHighContrast',text_size:'sportabaseTextScale',
  density:'sportabaseDensity',motion:'sportabaseMotionLevel',analysis_detail:'sportabaseDetailLevel',
});
const LEGACY_MIGRATION_KEY = 'sportabaseLegacyMigrationV1';
export function presentationPreferences(preferences={}) {
  const result={};
  for(const [shared,local] of Object.entries(PRESENTATION_MAPPING)) {
    if(Object.hasOwn(preferences,shared)) result[local]=shared==='contrast'?preferences[shared]==='high':preferences[shared];
  }
  return result;
}
function exactKeys(message, allowed) {
  if(!message || typeof message!=='object' || Array.isArray(message) || Object.keys(message).some(key=>!allowed.includes(key))) {
    throw new Error('Invalid extension message.');
  }
}
export function localPreferences(payload) {
  if(!payload || typeof payload!=='object' || Array.isArray(payload) || Object.keys(payload).some(key=>!LOCAL_KEYS.has(key))) throw new Error('Unsupported local setting.');
  for(const [key,value] of Object.entries(payload)) {
    if(value!==null&&!['string','number','boolean'].includes(typeof value))throw new Error('Invalid local setting.');
    if(typeof value==='string'&&value.length>32)throw new Error('Invalid local setting.');
    if(typeof value==='number'&&(!Number.isFinite(value)||Math.abs(value)>100000))throw new Error('Invalid layout value.');
  }
  return payload;
}
export function createAccountGateway({chrome,config,createClient,fetchImpl=fetch}) {
  const active = new Map();
  let installationPromise;
  let clientPromise;
  let lastPresentationRefresh=0;
  let lastPresentationSession='';
  async function deviceId() {
    if(!installationPromise) installationPromise=(async()=>{
      const stored=await chrome.storage.local.get('sportabaseDeviceId');
      if(stored.sportabaseDeviceId)return stored.sportabaseDeviceId;
      const id=crypto.randomUUID();await chrome.storage.local.set({sportabaseDeviceId:id});return id;
    })().catch(error=>{installationPromise=null;throw error;});
    return installationPromise;
  }
  async function client() {
    if(!config.publishableKey||!config.syncHost)throw new AccountGatewayError('Configure Sportabase account sign-in for this extension.',{status:503,code:'configuration_unavailable'});
    if(!clientPromise)clientPromise=Promise.resolve(createClient({publishableKey:config.publishableKey,syncHost:config.syncHost,background:true})).catch(error=>{clientPromise=null;throw error;});
    return clientPromise;
  }
  function sameSession(clerk,expected) {
    const current=clerk.session;
    if(!current||!expected)return false;
    const currentId=String(current.id||'');
    const expectedId=String(expected.id||'');
    return currentId&&expectedId?currentId===expectedId:current===expected;
  }
  function requireCurrentSession(clerk,expected) {
    if(!sameSession(clerk,expected))throw new AccountGatewayError('Your active account changed. Retry this action.',{status:409,code:'account_changed'});
  }
  async function request(session,path,method='GET',body,signal) {
    let token;
    try { token=await session?.getToken(); }
    catch { throw new AccountGatewayError('Sportabase could not refresh the account session.',{status:503,code:'session_unavailable'}); }
    if(!token)throw new AccountGatewayError('Sign in to Sportabase to continue.',{status:401,code:'auth_required'});
    try {
      const response=await fetchImpl(config.apiBase+path,{method,headers:{Authorization:`Bearer ${token}`,'X-Sportabase-Device-ID':await deviceId(),'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal,redirect:'error'});
      const text=await response.text();
      return {status:response.status,body:text};
    } catch(error) {
      if(error?.name==='AbortError')throw new AccountGatewayError('The extension request was stopped.',{status:408,code:'request_aborted'});
      throw new AccountGatewayError('Sportabase could not reach the account service.',{status:503,code:'transport_unavailable'});
    }
  }
  async function cacheState(state) {
    const writes=presentationPreferences(state.effective);
    if(state.legacy_migration?.status&&state.legacy_migration.status!=='not_requested')writes[LEGACY_MIGRATION_KEY]='complete';
    if(Object.keys(writes).length)await chrome.storage.local.set(writes);
    return state;
  }
  async function bootstrap(clerk,session=clerk.session) {
    requireCurrentSession(clerk,session);
    const stored=await chrome.storage.local.get('sportabaseClientId');
    const migration=await chrome.storage.local.get(LEGACY_MIGRATION_KEY);
    requireCurrentSession(clerk,session);
    const result=await request(session,'/account/bootstrap','POST',{platform:'extension',name:'Chrome extension',...(!migration[LEGACY_MIGRATION_KEY]&&stored.sportabaseClientId?{legacy_client_id:stored.sportabaseClientId}:{})});
    requireCurrentSession(clerk,session);
    if(result.status!==200)throw new AccountGatewayError('Could not connect this extension to your account.',{status:result.status,code:'bootstrap_failed'});
    let state;
    try {state=JSON.parse(result.body);}
    catch {throw new AccountGatewayError('Sportabase returned an invalid account response.',{status:502,code:'invalid_response'});}
    requireCurrentSession(clerk,session);
    const cached=await cacheState(state);
    requireCurrentSession(clerk,session);
    return cached;
  }
  async function refreshPresentation({maxAgeMs=30000}={}) {
    const clerk=await client();
    if(!clerk.session)return null;
    const activeSession=clerk.session;
    const session=String(activeSession.id||'');
    // Only reuse the throttle when Clerk gives us a stable session identifier.
    // An empty identifier cannot distinguish a rapid same-installation account switch.
    if(session&&Date.now()-lastPresentationRefresh<maxAgeMs&&session===lastPresentationSession)return null;
    const state=await bootstrap(clerk,activeSession);
    lastPresentationRefresh=Date.now();lastPresentationSession=session;
    return state;
  }
  async function handle(message,sender) {
    const contentSender=validSender(sender,chrome.runtime.id);
    const extensionSender=validExtensionPageSender(sender,chrome.runtime.id,chrome.runtime.getURL('settings.html'));
    if(!contentSender&&!extensionSender)throw new Error('Untrusted extension sender.');
    if(message.type==='SPORTABASE_SAVE_OVERLAY_PREFS') {
      if(!contentSender)throw new Error('Unsupported extension operation.');
      exactKeys(message,['type','payload']);await chrome.storage.local.set(localPreferences(message.payload));return {ok:true};
    }
    if(message.type==='SPORTABASE_OPEN_EXTENSION_SETTINGS') {
      if(!contentSender)throw new Error('Unsupported extension operation.');
      exactKeys(message,['type']);await chrome.tabs.create({url:chrome.runtime.getURL('settings.html')});return {ok:true};
    }
    if(message.type==='SPORTABASE_OPEN_ACCOUNT') {
      if(!extensionSender)throw new Error('Unsupported extension operation.');
      exactKeys(message,['type']);
      if(!config.syncHost)throw new Error('Sportabase web app is not configured.');
      await chrome.tabs.create({url:config.syncHost+'/#settings'});return {ok:true};
    }
    if(message.type==='SPORTABASE_API_CANCEL') {
      if(!contentSender)throw new Error('Unsupported extension operation.');
      exactKeys(message,['type','requestId']);
      if(!/^[a-zA-Z0-9_-]{1,80}$/.test(message.requestId||''))throw new Error('Invalid cancellation message.');
      active.get(`${sender.tab.id}:${message.requestId}`)?.abort();return {ok:true};
    }
    if(!['SPORTABASE_ACCOUNT_STATE','SPORTABASE_ACCOUNT_UPDATE','SPORTABASE_SIGN_OUT','SPORTABASE_API_REQUEST'].includes(message.type))throw new Error('Unsupported extension operation.');
    if(message.type==='SPORTABASE_API_REQUEST'&&!contentSender)throw new Error('Unsupported extension operation.');
    if(message.type!=='SPORTABASE_API_REQUEST'&&!extensionSender)throw new Error('Unsupported extension operation.');
    const clerk=await client();
    if(!clerk.session)throw new AccountGatewayError('Sign in to Sportabase to continue.',{status:401,code:'auth_required'});
    const session=clerk.session;
    if(message.type==='SPORTABASE_SIGN_OUT') {
      exactKeys(message,['type']);
      const result=await request(session,'/account/device/sign-out','POST');
      requireCurrentSession(clerk,session);
      if(result.status!==200)throw new AccountGatewayError('Could not revoke this extension device. Sign-out was not completed.',{status:result.status,code:'sign_out_revoke_failed'});
      await clerk.signOut();lastPresentationSession='';lastPresentationRefresh=0;return {ok:true};
    }
    if(message.type==='SPORTABASE_ACCOUNT_STATE'){
      exactKeys(message,['type']);return {ok:true,state:await bootstrap(clerk,session)};
    }
    if(message.type==='SPORTABASE_ACCOUNT_UPDATE') {
      exactKeys(message,['type','body']);
      if(!message.body||typeof message.body!=='object'||Array.isArray(message.body)||JSON.stringify(message.body).length>20000)throw new Error('Invalid settings update.');
      const result=await request(session,'/account/preferences','PATCH',message.body);
      requireCurrentSession(clerk,session);
      if(result.status!==200)throw new AccountGatewayError('Settings were not saved. Refresh account settings and try again.',{status:result.status,code:'settings_update_failed'});
      let state;
      try {state=JSON.parse(result.body);}
      catch {throw new AccountGatewayError('Sportabase returned an invalid settings response.',{status:502,code:'invalid_response'});}
      const cached=await cacheState(state);
      requireCurrentSession(clerk,session);
      return {ok:true,state:cached};
    }
    validateApiMessage(message);
    if(active.size>=8)throw new AccountGatewayError('Too many product requests.',{status:429,code:'extension_concurrency'});
    const key=`${sender.tab.id}:${message.requestId}`;
    if(active.has(key))throw new AccountGatewayError('Duplicate product request.',{status:409,code:'duplicate_request'});
    const controller=new AbortController();active.set(key,controller);
    const timer=setTimeout(()=>controller.abort(),125000);
    try {
      await bootstrap(clerk,session);
      const result=await request(session,message.path,message.method,message.body,controller.signal);
      requireCurrentSession(clerk,session);
      return {ok:true,...result};
    }
    finally {clearTimeout(timer);active.delete(key);}
  }
  return {handle,refreshPresentation};
}
