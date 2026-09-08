import { useFonts } from 'expo-font';

export function useProductFonts() {
  return useFonts({
    SportabaseBarlowRegular: require('../../assets/fonts/Barlow-Regular.ttf'),
    SportabaseBarlowMedium: require('../../assets/fonts/Barlow-Medium.ttf'),
    SportabaseBarlowCondensedSemiBold: require('../../assets/fonts/BarlowCondensed-SemiBold.ttf'),
    SportabaseBarlowSemiCondensedBold: require('../../assets/fonts/BarlowSemiCondensed-Bold.ttf'),
    SportabaseOxaniumBold: require('../../assets/fonts/Oxanium-Variable.ttf'),
  });
}
