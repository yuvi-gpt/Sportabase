import { useGlobalSearchParams, usePathname } from 'expo-router';
import { useEffect, type PropsWithChildren } from 'react';
import {
  StyleSheet,
  useWindowDimensions,
  View,
} from 'react-native';

import '../global.css';
import { useProductFonts } from './ProductFonts';
import { ProductHeader } from './ProductHeader';
import { getProductHomePalette } from './ProductHomeTheme';
import { useProductShell } from './ProductShellContext';
import { useProductTheme } from '../theme/product-theme';

function routeUsesProductHeader(pathname: string) {
  return pathname !== '/handle-share';
}

export function ProductWebShell({
  children,
}: PropsWithChildren) {
  const pathname = usePathname();
  const { theme: previewThemeParam } = useGlobalSearchParams<{ theme?: string }>();
  useProductFonts();
  const { dark } = useProductTheme();
  const { homeControls } = useProductShell();
  const designLabPreview =
    pathname === '/design-lab' ||
    pathname === '/design-lab-analyzing';
  const designLabTheme = previewThemeParam === 'light' ? 'light' : 'dark';
  const effectiveDark = designLabPreview ? designLabTheme === 'dark' : dark;
  const palette = getProductHomePalette(effectiveDark);
  useEffect(() => {
    document.documentElement.style.colorScheme = effectiveDark ? 'dark' : 'light';
    document.documentElement.style.setProperty('--sportabase-ground', palette.ground);
    document.documentElement.style.setProperty('--sportabase-text', palette.text);
    document.documentElement.style.setProperty('--sportabase-focus', palette.lime);
    document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute('content', palette.ground);
  }, [effectiveDark, palette.ground, palette.lime, palette.text]);
  const { width } = useWindowDimensions();
  const compact = width < 980;
  const pageGutter =
    width >= 1200 ? 68 : width >= 700 ? 40 : 20;
  const shellWidth = Math.max(
    Math.min(width - pageGutter * 2, 1304),
    280,
  );

  return (
    <View style={[styles.frame, { backgroundColor: palette.ground }]}>
      <a
        className="sportabase-skip-link"
        href="#sportabase-main"
        tabIndex={0}
      >
        Skip to content
      </a>

      {routeUsesProductHeader(pathname) ? (
        <View style={[styles.headerSurface, { backgroundColor: palette.ground }]}>
          <View
            style={[
              styles.headerInner,
              {
                width: shellWidth,
                marginHorizontal: 'auto',
              },
            ]}
          >
            <ProductHeader
              compact={compact}
              hideAccount={designLabPreview}
              hideLogo
              previewColors={palette}
              narrow={width < 360}
              onHome={homeControls?.onHome}
              onAnother={homeControls?.onAnother}
              showAnother={Boolean(
                pathname === '/' &&
                  homeControls?.showAnother,
              )}
            />
          </View>
        </View>
      ) : null}

      <View
        key={pathname}
        nativeID="sportabase-main"
        role="main"
        style={styles.content}
      >
        {children}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    flex: 1,
  },
  headerSurface: {
    flexShrink: 0,
    zIndex: 10,
  },
  headerInner: {
    alignSelf: 'center',
    maxWidth: 1256,
  },
  content: {
    flex: 1,
    minHeight: 0,
  },
});
