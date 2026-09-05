import contract from '../../../frontend/preferences-contract.json';

const mapping={appearance:'sportabaseAppearance',contrast:'sportabaseHighContrast',text_size:'sportabaseTextScale',density:'sportabaseDensity',motion:'sportabaseMotionLevel',analysis_detail:'sportabaseDetailLevel'};
const labels={system:'System setting',en:'English',full:'Full detail',essential:'Essential detail',comfortable:'Comfortable',compact:'Compact',standard:'Standard',high:'High contrast',reduce:'Reduce motion',light:'Light',dark:'Dark',small:'Smaller',large:'Larger',iso:'YYYY-MM-DD'};
export function sharedToLocal(preferences) {
  return Object.fromEntries(Object.entries(mapping).map(([key,local])=>[local,key==='contrast'?preferences[key]==='high':preferences[key]]));
}
export function installAccountSettings({layer,applyShared}) {
  const container=layer.querySelector('.sb-settings-content');
  const host=document.createElement('div');host.className='sb-account-settings';container.prepend(host);
  let state=null,scope='device',busy=false;
  const openSections=new Set(['Account']);
  const status=document.createElement('p');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  function element(tag,text){const el=document.createElement(tag);if(text)el.textContent=text;return el;}
  function setStatus(text,tone='neutral'){status.textContent=text;status.dataset.tone=tone;}
  async function message(type,extra={}) {const result=await chrome.runtime.sendMessage({type,...extra});if(!result?.ok)throw new Error(result?.error||'Account operation failed.');return result;}
  function button(label,fn){const el=element('button',label);el.type='button';el.className='sb-account-button';el.addEventListener('click',async()=>{el.disabled=true;try{await fn();}catch(error){setStatus(error.message,'error');}finally{el.disabled=false;}});return el;}
  function group(name,initial=false){const el=element('details');el.open=openSections.has(name)||initial;const summary=element('summary',name);el.append(summary);el.addEventListener('toggle',()=>el.open?openSections.add(name):openSections.delete(name));host.append(el);return el;}
  function lock(value){
    busy=value;
    for(const control of host.querySelectorAll('button,input,select')){
      if(value){control.dataset.wasDisabled=String(control.disabled);control.disabled=true;}
      else{control.disabled=control.dataset.wasDisabled==='true';delete control.dataset.wasDisabled;}
    }
  }
  async function refresh(){setStatus('Connecting account...');try{const result=await message('SPORTABASE_ACCOUNT_STATE');state=result.state;applyShared(sharedToLocal(state.effective));render('Account');setStatus(state.follows_defaults?'Connected · Using account defaults':'Connected · Device overrides enabled','success');}catch(error){state=null;render('Account');setStatus(error.message,'error');}}
  function render(focusSection=''){
    host.replaceChildren(status);
    const account=group('Account',true);
    account.append(element('p',state?'Connected account · Chrome extension':'Sign in on Sportabase, then connect this extension.'));
    account.append(button(state?'Open account and sessions':'Sign in on Sportabase',()=>message('SPORTABASE_OPEN_ACCOUNT')),button(state?'Refresh connection':'Connect after signing in',refresh));
    if(state)account.append(button('Sign out of this extension',async()=>{await message('SPORTABASE_SIGN_OUT');state=null;render('Account');setStatus('Signed out','success');}));
    if(state){
      const row=element('label','Settings location');row.className='sb-setting-row';
      const select=element('select');for(const [value,text]of[['device','This extension'],['account','Account defaults']]){const option=element('option',text);option.value=value;select.append(option);}select.value=scope;select.addEventListener('change',()=>{scope=select.value;render('Account');});row.append(select);account.append(row);
      if(scope==='device'){
        const follow=element('label','Use account defaults on this extension');follow.className='sb-setting-row';const input=element('input');input.type='checkbox';input.checked=state.follows_defaults;input.addEventListener('change',()=>save({},input.checked,'device','Account'));follow.append(input);account.append(follow);
      }
    }
    for(const name of ['Appearance','Analysis','Notifications','Language & Region','Privacy & Data']){
      const section=group(name);
      if(!state){section.append(element('p','Connect your account to manage these preferences.'));continue;}
      const privacy=name==='Privacy & Data';const selected=privacy?'account':scope;const values=selected==='account'?state.defaults:state.effective;const pending={};let saveButton;
      const inherited=()=>!privacy&&selected==='device'&&state.follows_defaults;
      const dependencies=()=>{
        if(name!=='Notifications')return;
        const master=section.querySelector('[name="notifications_enabled"]')?.checked;
        const quiet=section.querySelector('[name="quiet_hours_enabled"]')?.checked;
        for(const key of ['entity_alerts','story_alerts','claim_alerts','media_alerts','quiet_hours_enabled']){const control=section.querySelector(`[name="${key}"]`);if(control)control.disabled=busy||inherited()||!master;}
        for(const key of ['quiet_hours_start','quiet_hours_end','timezone']){const control=section.querySelector(`[name="${key}"]`);if(!control)continue;control.disabled=busy||inherited()||!master||!quiet;control.closest('.sb-setting-row').hidden=!quiet;}
      };
      for(const key of contract.sections[name]){
        const field=contract.fields[key];const row=element('label',field.label);row.className='sb-setting-row';let input;
        if(field.options){input=element('select');for(const value of field.options){const option=element('option',labels[value]||value);option.value=value;input.append(option);}input.value=values[key];}
        else{input=element('input');input.type=typeof values[key]==='boolean'?'checkbox':field.type||'text';if(input.type==='checkbox')input.checked=values[key];else input.value=values[key];input.maxLength=80;}
        input.name=key;input.disabled=busy||inherited();input.addEventListener('change',()=>{pending[key]=input.type==='checkbox'?input.checked:input.value;if(name==='Appearance'||name==='Analysis')applyShared(sharedToLocal({...state.effective,...pending}));saveButton.disabled=false;dependencies();setStatus('Unsaved changes');});row.append(input);section.append(row);
      }
      saveButton=button('Save changes',()=>save(pending,undefined,selected,name));saveButton.disabled=true;section.append(saveButton);dependencies();
      if(name==='Notifications')section.append(element('p','Push delivery uses web or mobile registrations. Quiet hours postpone delivery; Alerts stay available.'));
      if(privacy)section.append(element('p','Optional usage sharing controls narrow event counts. Necessary account, device, watch and notification records remain while the account is active. Export and deletion open the configured Sportabase web app.'),button('Manage personal data',()=>message('SPORTABASE_OPEN_ACCOUNT')));
    }
    const activity=group('My Activity');activity.append(button('Open personal activity',()=>message('SPORTABASE_OPEN_ACCOUNT')));
    const about=group('Support/About');about.append(element('p',`Sportabase ${chrome.runtime.getManifest().version}`),button('Account and privacy information',()=>message('SPORTABASE_OPEN_ACCOUNT')));
    if(focusSection)queueMicrotask(()=>[...host.querySelectorAll('summary')].find(summary=>summary.textContent===focusSection)?.focus());
  }
  async function save(preferences,follows,selected=scope,source='Account'){
    if(busy)return;lock(true);setStatus('Saving...');
    try{const result=await message('SPORTABASE_ACCOUNT_UPDATE',{body:{version:contract.version,scope:selected,revision:selected==='account'?state.account_revision:state.device_revision,preferences,...(follows===undefined?{}:{follows_defaults:follows})}});state=result.state;applyShared(sharedToLocal(state.effective));lock(false);render(source);setStatus(selected==='account'?'Saved to account defaults':state.follows_defaults?'This extension now follows account defaults':'Saved on this extension','success');}
    catch(error){applyShared(sharedToLocal(state.effective));lock(false);setStatus(error.message,'error');}
  }
  render();
  return {refresh};
}
