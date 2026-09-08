import { ProductHeader } from '../product-ui/ProductHeader';

export function DesignLabHeader({
  onHome,
  onAnother,
  showAnother,
  mobile = false,
}: {
  onHome: () => void;
  onAnother: () => void;
  showAnother: boolean;
  mobile?: boolean;
}) {
  return (
    <ProductHeader
      compact={mobile}
      onHome={onHome}
      onAnother={onAnother}
      showAnother={showAnother}
    />
  );
}
