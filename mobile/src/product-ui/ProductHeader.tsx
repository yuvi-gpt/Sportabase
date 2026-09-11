import { Image } from 'expo-image';
import {
  Link,
  usePathname,
} from 'expo-router';
import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { useAccount } from '../lib/account-context';
import {
  allowlistedAuthDestination,
  type AuthReturnDestination,
} from '../lib/auth-destinations';
import { ProductWordmark } from './ProductWordmark';
import { productFonts, productPalette } from './tokens';

const NAV_ITEMS = [
  { label: 'Analyze', route: '/' },
  { label: 'Discover', route: '/explore' },
  { label: 'Watches', route: '/watchlists' },
  { label: 'Alerts', route: '/alerts' },
  { label: 'Activity', route: '/activity' },
  { label: 'Settings', route: '/settings' },
] as const;

type ProductHeaderProps = {
  compact?: boolean;
  hideAccount?: boolean;
  hideLogo?: boolean;
  narrow?: boolean;
  onHome?: () => void;
  onAnother?: () => void;
  showAnother?: boolean;
  previewColors?: {
    line: string;
    lime: string;
    muted: string;
    secondary: string;
    text: string;
    danger?: string;
    teal?: string;
  };
};

export function ProductHeader({
  compact = false,
  hideAccount = false,
  hideLogo = false,
  narrow = false,
  onHome,
  onAnother,
  showAnother = false,
  previewColors,
}: ProductHeaderProps) {
  const pathname = usePathname();
  const account = useAccount();
  const navigationRef = useRef<ScrollView>(null);
  const [accountError, setAccountError] =
    useState('');

  const returnDestination = useMemo(
    () =>
      allowlistedAuthDestination(pathname),
    [pathname],
  );

  useEffect(() => {
    if (narrow) {
      return;
    }

    if (
      pathname.startsWith('/settings') ||
      pathname.startsWith('/notifications')
    ) {
      navigationRef.current?.scrollToEnd({
        animated: false,
      });
    } else {
      navigationRef.current?.scrollTo({
        animated: false,
        x: 0,
      });
    }
  }, [narrow, pathname]);

  const navigationItems = NAV_ITEMS.map((item) => {
    const active =
      item.route === '/'
        ? pathname === '/'
        : pathname.startsWith(item.route) ||
          (item.route === '/settings' &&
            pathname.startsWith('/notifications'));

    return (
      <Link key={item.route} href={item.route} asChild>
        <Pressable
          aria-current={active ? 'page' : undefined}
          accessibilityRole="link"
          accessibilityState={{ selected: active }}
          onPress={() => {
            setAccountError('');

            if (item.route === '/' && pathname === '/') {
              onHome?.();
            }
          }}
          style={({ pressed }) => [
            styles.navItem,
            narrow && styles.navItemNarrow,
            active && styles.navItemActive,
            active && previewColors && { borderBottomColor: previewColors.lime },
            pressed && styles.pressed,
          ]}
        >
          <Text
            style={[
              styles.navText,
              previewColors && { color: previewColors.secondary },
              narrow && styles.navTextNarrow,
              active && styles.navTextActive,
              active && previewColors && { color: previewColors.text },
            ]}
          >
            {item.label}
          </Text>
        </Pressable>
      </Link>
    );
  });

  const navigation = narrow ? (
    <View
      accessibilityLabel="Primary"
      nativeID="sportabase-primary-nav"
      role="navigation"
      style={styles.navNarrow}
    >
      {navigationItems}
    </View>
  ) : (
    <ScrollView
      accessibilityLabel="Primary"
      horizontal
      nativeID="sportabase-primary-nav"
      ref={navigationRef}
      role="navigation"
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={[
        styles.nav,
        compact && styles.navCompact,
      ]}
      style={styles.navScroller}
    >
      {navigationItems}
    </ScrollView>
  );

  const accountAction = (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={
        account.signedIn
          ? 'Manage Sportabase account'
          : 'Sign in to Sportabase'
      }
      disabled={!account.ready}
      onPress={() => {
        setAccountError('');

        const action = account.signedIn
          ? account.manage()
          : account.signIn(
              false,
              returnDestination,
            );

        void action.catch((problem) => {
          setAccountError(
            problem instanceof Error
              ? problem.message
              : 'Sportabase sign-in is unavailable. Try again from this page.',
          );
        });
      }}
      style={({ pressed }) => [
        styles.account,
        previewColors && { borderColor: previewColors.line },
        !account.ready && styles.disabled,
        pressed && styles.pressed,
      ]}
    >
      <View
        style={[
          styles.accountDot,
          previewColors && { backgroundColor: previewColors.muted },
          account.signedIn &&
            styles.accountDotActive,
          account.signedIn && previewColors && { backgroundColor: previewColors.lime },
        ]}
      />

      <Text style={[styles.accountText, previewColors && { color: previewColors.secondary }]}>
        {!account.ready
          ? 'Account…'
          : account.signedIn
            ? 'Account'
            : 'Sign in'}
      </Text>
    </Pressable>
  );

  return (
    <View
      nativeID="sportabase-product-header"
      role="banner"
      style={[
        styles.header,
        compact && styles.headerCompact,
        previewColors && { borderBottomColor: previewColors.line },
      ]}
    >
      <View
        style={[
          styles.topRow,
          compact && styles.topRowCompact,
          hideAccount && styles.topRowWithoutAccount,
        ]}
      >
        <Link href="/" asChild>
          <Pressable
            accessibilityRole="link"
            accessibilityLabel="Sportabase home"
            onPress={() => {
              if (pathname === '/') {
                onHome?.();
              }
            }}
            style={({ pressed }) => [
              styles.brandButton,
              compact && styles.brandButtonCompact,
              pressed && styles.pressed,
            ]}
          >
            {!hideLogo ? (
              <Image
                source={require(
                  '../../assets/images/sportabase-logo.png'
                )}
                contentFit="contain"
                style={[
                  styles.logo,
                  compact && styles.logoCompact,
                ]}
              />
            ) : null}

            <ProductWordmark compact={compact} color={previewColors?.text} />
          </Pressable>
        </Link>

        {!compact ? (
          <View style={[styles.desktopActions, hideAccount && styles.desktopActionsWithoutAccount]}>
            {navigation}

            {showAnother ? (
              <Pressable
                accessibilityRole="button"
                onPress={onAnother}
                style={({ pressed }) => [
                  styles.another,
                  pressed && styles.pressed,
                ]}
              >
                <View style={[styles.anotherMark, previewColors && { borderColor: previewColors.teal ?? productPalette.teal }]} />

                <Text style={[styles.anotherText, previewColors && { color: previewColors.secondary }]}>
                  Analyze another
                </Text>
              </Pressable>
            ) : null}

            {!hideAccount ? accountAction : null}
          </View>
        ) : (
          hideAccount ? null : accountAction
        )}
      </View>

      {compact ? navigation : null}

      {accountError ? (
        <Text
          accessibilityRole="alert"
          style={[styles.accountError, previewColors?.danger && { color: previewColors.danger }]}
        >
          {accountError}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    minHeight: 92,
    paddingTop: 10,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: productPalette.line,
    gap: 8,
  },
  headerCompact: {
    minHeight: 124,
    paddingTop: 10,
    paddingBottom: 10,
    gap: 6,
  },
  topRow: {
    minHeight: 72,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 24,
  },
  topRowCompact: {
    minHeight: 60,
    gap: 16,
  },
  topRowWithoutAccount: {
    justifyContent: 'flex-start',
  },
  brandButton: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderRadius: 7,
    paddingRight: 8,
    flexShrink: 0,
  },
  brandButtonCompact: {
    minHeight: 52,
    gap: 7,
    paddingRight: 2,
  },
  logo: {
    width: 54,
    height: 54,
  },
  logoCompact: {
    width: 46,
    height: 46,
  },
  desktopActions: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 10,
    minWidth: 0,
  },
  desktopActionsWithoutAccount: {
    justifyContent: 'flex-start',
    marginLeft: 14,
  },
  navScroller: {
    flexShrink: 1,
  },
  nav: {
    alignItems: 'center',
    gap: 22,
  },
  navCompact: {
    gap: 10,
    paddingRight: 10,
  },
  navNarrow: {
    width: '100%',
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    columnGap: 8,
    rowGap: 2,
    paddingTop: 2,
  },
  navItem: {
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: 0,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  navItemActive: {
    borderBottomColor: productPalette.lime,
  },
  navItemNarrow: {
    minWidth: 44,
    paddingHorizontal: 3,
  },
  navText: {
    color: productPalette.secondary,
    fontFamily: productFonts.emphasis,
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 0.05,
  },
  navTextActive: {
    color: productPalette.text,
  },
  navTextNarrow: {
    fontSize: 13,
    textAlign: 'center',
  },
  account: {
    minHeight: 46,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderColor: productPalette.lineStrong,
    borderRadius: 7,
  },
  accountDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: productPalette.muted,
  },
  accountDotActive: {
    backgroundColor: productPalette.lime,
  },
  accountText: {
    color: productPalette.secondary,
    fontFamily: productFonts.emphasis,
    fontSize: 12,
    fontWeight: '800',
  },
  accountError: {
    color: '#FB9AA9',
    fontSize: 13,
    lineHeight: 19,
    paddingBottom: 4,
  },
  another: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 8,
  },
  anotherMark: {
    width: 8,
    height: 8,
    borderRadius: 4,
    borderWidth: 2,
    borderColor: productPalette.teal,
  },
  anotherText: {
    color: productPalette.secondary,
    fontFamily: productFonts.emphasis,
    fontSize: 12,
    fontWeight: '700',
  },
  disabled: {
    opacity: 0.56,
  },
  pressed: {
    opacity: 0.64,
  },
});
