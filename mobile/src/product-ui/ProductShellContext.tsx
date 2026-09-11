import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type PropsWithChildren,
} from 'react';

type HomeControls = {
  onHome: () => void;
  onAnother: () => void;
  showAnother: boolean;
};

type ProductShellContextValue = {
  homeControls: HomeControls | null;
  registerHomeControls: (
    controls: HomeControls | null,
  ) => void;
};

const ProductShellContext =
  createContext<ProductShellContextValue>({
    homeControls: null,
    registerHomeControls: () => {},
  });

export function ProductShellProvider({
  children,
}: PropsWithChildren) {
  const [homeControls, setHomeControls] =
    useState<HomeControls | null>(null);

  const registerHomeControls = useCallback(
    (controls: HomeControls | null) => {
      setHomeControls(controls);
    },
    [],
  );

  return (
    <ProductShellContext.Provider
      value={{
        homeControls,
        registerHomeControls,
      }}
    >
      {children}
    </ProductShellContext.Provider>
  );
}

export function useProductShell() {
  return useContext(ProductShellContext);
}

export function useProductHomeControls(
  controls: HomeControls,
) {
  const { registerHomeControls } =
    useProductShell();

  useEffect(() => {
    registerHomeControls(controls);

    return () => registerHomeControls(null);
  }, [controls, registerHomeControls]);
}
