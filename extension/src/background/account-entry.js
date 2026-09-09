import { createClerkClient } from '@clerk/chrome-extension/client';
import { createAccountGateway, serializeGatewayError } from './account-gateway.mjs';
const config = {
  publishableKey: __SPORTABASE_CLERK_KEY__,
  syncHost: __SPORTABASE_SYNC_HOST__,
  apiBase: __SPORTABASE_API_BASE__,
};
export const gateway=createAccountGateway({chrome,config,createClient:createClerkClient});
chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
  if(!message?.type?.startsWith('SPORTABASE_'))return;
  gateway.handle(message,sender).then(sendResponse).catch(error=>sendResponse({ok:false,error:serializeGatewayError(error)}));
  return true;
});
