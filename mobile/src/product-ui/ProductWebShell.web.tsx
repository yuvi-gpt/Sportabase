import { usePathname } from 'expo-router';
import { useEffect, type PropsWithChildren } from 'react';
import {
  StyleSheet,
  useWindowDimensions,
  View,
} from 'react-native';

import '../global.css';
import { useProductFonts } from './ProductFonts';
import { ProductHeader } from './ProductHeader';
import { useProductShell } from './ProductShellContext';
import { productPalette } from './tokens';
import { useProductTheme } from '../theme/product-theme';

function routeUsesProductHeader(pathname: string) {
  return pathname !== '/handle-share';
}

export function ProductWebShell({
  children,
}: PropsWithChildren) {
  const pathname = usePathname();
  useProductFonts();
  const { dark } = useProductTheme();
  useEffect(() => {
    document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
    document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute('content', dark ? productPalette.ground : '#f5f7f4');
  }, [dark]);
  const { width } = useWindowDimensions();
  const { homeControls } = useProductShell();
  const compact = width < 980;
  const pageGutter =
    width >= 1200 ? 68 : width >= 700 ? 40 : 20;
  const shellWidth = Math.max(
    Math.min(width - pageGutter * 2, 1304),
    280,
  );

  return (
    <View style={styles.frame}>
      <a
        className="sportabase-skip-link"
        href="#sportabase-main"
        tabIndex={0}
      >
        Skip to content
      </a>

      {routeUsesProductHeader(pathname) ? (
        <View style={styles.headerSurface}>
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
    backgroundColor: productPalette.ground,
    flex: 1,
  },
  headerSurface: {
    backgroundColor: productPalette.ground,
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
