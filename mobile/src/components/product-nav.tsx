import { useProductTheme } from '../theme/product-theme';
import { usePathname, useRouter } from 'expo-router';
import {
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAccount } from '../lib/account-context';

const ITEMS = [
  { label: 'Analyze', route: '/' },
  { label: 'Discover', route: '/explore' },
  { label: 'Watches', route: '/watchlists' },
  { label: 'Alerts', route: '/alerts' },
  { label: 'Settings', route: '/settings' },
] as const;

export function ProductNav() {
  const { colors,scale }=useProductTheme();
  const router = useRouter();
  const pathname = usePathname();
  const insets = useSafeAreaInsets();
  const { signedIn } = useAccount();

  return (
    <View
      style={[
        styles.shell,
        {
          backgroundColor: colors.surface, borderTopColor: colors.border,
          paddingBottom: Math.max(insets.bottom, 8),
        },
      ]}
    >
      <View style={styles.inner}>
        {ITEMS.map((item) => {
          const active =
            item.route === '/'
              ? pathname === '/'
              : pathname.startsWith(item.route) || (item.route === '/settings' && ['/activity', '/notifications'].some(route => pathname.startsWith(route)));

          return (
            <Pressable
              key={item.route}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              onPress={() => {
                if (!active) {
                  const accountRequired = ['/', '/watchlists', '/alerts'].includes(item.route);
                  router.replace(accountRequired && !signedIn ? '/settings' : item.route);
                }
              }}
              style={({ pressed }) => [
                styles.item,
                active && styles.itemActive,
                pressed && styles.itemPressed,
              ]}
            >
              <View
                style={[
                  styles.dot,
                  active && styles.dotActive,
                ]}
              />
              <Text
                style={[
                  styles.label,
                  active && styles.labelActive,
                  {color:active?colors.text:colors.muted,fontSize:12*scale},
                ]}
              >
                {item.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  shell: {
    backgroundColor: '#080b09',
    borderTopColor: '#202620',
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: 14,
    paddingTop: 8,
  },
  inner: {
    alignSelf: 'center',
    flexDirection: 'row',
    gap: 4,
    maxWidth: 720,
    width: '100%',
  },
  item: {
    alignItems: 'center',
    borderRadius: 12,
    flex: 1,
    gap: 5,
    minHeight: 44,
    paddingHorizontal: 4,
    paddingVertical: 7,
  },
  itemActive: {
    backgroundColor: 'rgba(118, 245, 63, 0.08)',
  },
  itemPressed: {
    opacity: 0.68,
  },
  dot: {
    backgroundColor: '#59635c',
    borderRadius: 999,
    height: 4,
    width: 16,
  },
  dotActive: {
    backgroundColor: '#76f53f',
    width: 24,
  },
  label: {
    color: '#8e9991',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.35,
  },
  labelActive: {
    color: '#f4f7f4',
  },
});
