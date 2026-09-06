import '../styles/extension-settings-page.css';
import '../styles/account-settings.css';
import { installAccountSettings } from '../ui/account-settings.js';

function applyPresentation(preferences) {
  const root=document.documentElement;
  root.dataset.appearance=preferences.sportabaseAppearance||'system';
  root.dataset.contrast=preferences.sportabaseHighContrast?'high':'standard';
  root.dataset.text=preferences.sportabaseTextScale||'medium';
  root.dataset.density=preferences.sportabaseDensity||'comfortable';
  root.dataset.motion=preferences.sportabaseMotionLevel||'system';
  root.dataset.detail=preferences.sportabaseDetailLevel||'full';
}

const settings=installAccountSettings({layer:document,applyShared:applyPresentation});
void settings.refresh();
