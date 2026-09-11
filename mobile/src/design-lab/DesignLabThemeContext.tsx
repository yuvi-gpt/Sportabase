import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { darkPalette, getDesignLabPalette, type DesignLabPalette, type DesignLabTheme } from './design-lab-theme';

type DesignLabThemeValue = { palette: DesignLabPalette; theme: DesignLabTheme };

const DesignLabThemeContext = createContext<DesignLabThemeValue>({ palette: darkPalette, theme: 'dark' });

export function DesignLabThemeProvider({ children, theme }: { children: ReactNode; theme: DesignLabTheme }) {
  const value = useMemo(() => ({ palette: getDesignLabPalette(theme), theme }), [theme]);
  return <DesignLabThemeContext.Provider value={value}>{children}</DesignLabThemeContext.Provider>;
}

export function useDesignLabTheme() {
  return useContext(DesignLabThemeContext);
}
