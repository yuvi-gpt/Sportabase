import { useFonts } from 'expo-font';
import { createContext } from 'react';

export type WordmarkCandidate = 'uppercase-a' | 'uppercase-b' | 'uppercase-c' | 'oxanium';
export const WordmarkContext = createContext<WordmarkCandidate>('uppercase-b');

export const designLabFontNames = {
  wordmark: 'SportabaseBarlowSemiCondensedExtraBoldItalic',
  display: 'SportabaseBarlowSemiCondensedBold',
  label: 'SportabaseBarlowCondensedSemiBold',
  body: 'SportabaseBarlowRegular',
  bodyMedium: 'SportabaseBarlowMedium',
  kanitWordmark: 'SportabaseKanitExtraBoldItalic',
  chakraWordmark: 'SportabaseChakraPetchBoldItalic',
  titilliumWordmark: 'SportabaseTitilliumWebBoldItalic',
  exoWordmark: 'SportabaseExo2ExtraBoldItalic',
  oxaniumWordmark: 'SportabaseOxaniumBold',
  rajdhaniWordmark: 'SportabaseRajdhaniBold',
} as const;

export function useDesignLabFonts() {
  return useFonts({
    [designLabFontNames.wordmark]: require('../../assets/fonts/BarlowSemiCondensed-ExtraBoldItalic.ttf'),
    [designLabFontNames.display]: require('../../assets/fonts/BarlowSemiCondensed-Bold.ttf'),
    [designLabFontNames.label]: require('../../assets/fonts/BarlowCondensed-SemiBold.ttf'),
    [designLabFontNames.body]: require('../../assets/fonts/Barlow-Regular.ttf'),
    [designLabFontNames.bodyMedium]: require('../../assets/fonts/Barlow-Medium.ttf'),
    [designLabFontNames.kanitWordmark]: require('../../assets/fonts/Kanit-ExtraBoldItalic.ttf'),
    [designLabFontNames.chakraWordmark]: require('../../assets/fonts/ChakraPetch-BoldItalic.ttf'),
    [designLabFontNames.titilliumWordmark]: require('../../assets/fonts/TitilliumWeb-BoldItalic.ttf'),
    [designLabFontNames.exoWordmark]: require('../../assets/fonts/Exo2-Italic-Variable.ttf'),
    [designLabFontNames.oxaniumWordmark]: require('../../assets/fonts/Oxanium-Variable.ttf'),
    [designLabFontNames.rajdhaniWordmark]: require('../../assets/fonts/Rajdhani-Bold.ttf'),
  });
}
