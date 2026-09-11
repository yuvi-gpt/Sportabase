import { useEffect, useState } from 'react';
import { AccessibilityInfo, type TextStyle, type ViewStyle, type ImageStyle } from 'react-native';
import { useAccount } from '../lib/account-context';
import { useColorScheme } from '../hooks/use-color-scheme';

export function useProductTheme() {
  const { preferences } = useAccount();
  const system = useColorScheme();
  const [systemReduced,setSystemReduced] = useState(false);
  useEffect(()=>{
    void AccessibilityInfo.isReduceMotionEnabled().then(setSystemReduced);
    const subscription=AccessibilityInfo.addEventListener('reduceMotionChanged',setSystemReduced);
    return ()=>subscription.remove();
  },[]);
  const dark=preferences.appearance==='dark'||(preferences.appearance==='system'&&system==='dark');
  const high=preferences.contrast==='high';
  const colors: Record<string,string> = dark ? {
    background:'#070a09',surface:'#0b0f0d',surfaceRaised:'#101512',raised:'#171d19',text:high?'#ffffff':'#f4f7f1',textMuted:high?'#eeeeee':'#c5cec6',muted:high?'#eeeeee':'#98a49d',border:high?'#ffffff':'#718477',line:high?'#ffffff':'rgba(197, 206, 198, 0.14)',accent:'#b5f36b',accentSoft:'#182c14',danger:'#ff9a8f',error:'#ff9a8f',teal:'#20c9b0',cyan:'#16b8c4',lime:'#b5f36b',onAccent:'#071006',
  } : {
    background:'#f5f7f4',surface:'#ffffff',surfaceRaised:'#e8eee7',raised:'#e8eee7',text:high?'#000000':'#172219',textMuted:high?'#19291e':'#4e6053',muted:high?'#19291e':'#66736b',border:high?'#172219':'#718476',line:high?'#172219':'rgba(20, 28, 23, 0.14)',accent:'#246b16',accentSoft:'#e2efdf',danger:'#8d2119',error:'#8d2119',teal:'#137f75',cyan:'#13788a',lime:'#4d8f22',onAccent:'#ffffff',
  };
  return {colors,dark,high,scale:preferences.text_size==='large'?1.2:preferences.text_size==='small'?.9375:1,
    rowPadding:preferences.density==='compact'?8:16,
    spacing:{item:preferences.density==='compact'?12:16,section:preferences.density==='compact'?24:32},
    reduceMotion:preferences.motion==='reduce'||(preferences.motion==='system'&&systemReduced)};
}
export function scaleStyles<T extends Record<string,ViewStyle|TextStyle|ImageStyle>>(styles:T,scale:number):T {
  return Object.fromEntries(Object.entries(styles).map(([key,value])=>[key,{...value,
    ...('fontSize' in value&&typeof value.fontSize==='number'?{fontSize:value.fontSize*scale}:{}),
    ...('lineHeight' in value&&typeof value.lineHeight==='number'?{lineHeight:value.lineHeight*scale}:{}),
  }])) as T;
}
