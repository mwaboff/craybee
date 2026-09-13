import styles from "./HexLoader.module.css";

type HexLoaderProps = {
  /** CSS size of the loader, e.g. "1.1em" or "48px". Defaults to "1.2em" so it inherits the surrounding text size. */
  size?: string;
  className?: string;
};

const HEX_COUNT = 6;

export function HexLoader({ size = "1.2em", className }: HexLoaderProps) {
  return (
    <span
      className={[styles.hexLoader, className].filter(Boolean).join(" ")}
      style={{ "--hex-loader-size": size } as React.CSSProperties}
      role="status"
      aria-label="Loading"
    >
      {Array.from({ length: HEX_COUNT }, (_, i) => (
        <span key={i} className={styles.hex} style={{ "--i": i } as React.CSSProperties} />
      ))}
    </span>
  );
}
