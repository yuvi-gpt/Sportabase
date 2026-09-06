import { useEffect, useState } from 'react';
import { AccessibilityInfo, useColorScheme, type TextStyle, type ViewStyle, type ImageStyle } from 'react-native';
import { useAccount } from '../lib/account-context';

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
    background:'#050706',surface:'#0d110f',surfaceRaised:'#18221b',raised:'#18221b',text:high?'#ffffff':'#f3f7f3',muted:high?'#eeeeee':'#a5b3a9',border:high?'#ffffff':'#718477',accent:'#78f54a',accentSoft:'#182c14',error:'#ff9a9a',cyan:'#8be5ea',onAccent:'#071006',
  } : {
    background:'#f5f7f4',surface:'#ffffff',surfaceRaised:'#e8eee7',raised:'#e8eee7',text:high?'#000000':'#172219',muted:high?'#19291e':'#4e6053',border:high?'#172219':'#718476',accent:'#246b16',accentSoft:'#e2efdf',error:'#a82424',cyan:'#16656a',onAccent:'#ffffff',
  };
  return {colors,dark,high,scale:preferences.text_size==='large'?1.2:preferences.text_size==='small'?.9375:1,
    rowPadding:preferences.density==='compact'?8:16,
    reduceMotion:preferences.motion==='reduce'||(preferences.motion==='system'&&systemReduced)};
}
export function scaleStyles<T extends Record<string,ViewStyle|TextStyle|ImageStyle>>(styles:T,scale:number):T {
  return Object.fromEntries(Object.entries(styles).map(([key,value])=>[key,{...value,
    ...('fontSize' in value&&typeof value.fontSize==='number'?{fontSize:value.fontSize*scale}:{}),
    ...('lineHeight' in value&&typeof value.lineHeight==='number'?{lineHeight:value.lineHeight*scale}:{}),
  }])) as T;
}
