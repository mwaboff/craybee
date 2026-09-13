import { useEffect, useRef, useState } from "react";

export type StickToBottom = {
  /** Whether the scroller is currently pinned to its bottom edge. */
  isAtBottom: boolean;
  /** Scroll instantly to the bottom and re-engage sticking. */
  scrollToBottom: () => void;
};

/**
 * Keeps a scrollable container pinned to its bottom edge while content grows
 * (e.g. streaming tokens), but stops the moment the user scrolls away, so
 * they can read back through history without being yanked down.
 *
 * Contract: `ref` is the scroller (`overflow-y: auto`). Its *first element
 * child* is the content wrapper that actually grows -- a `ResizeObserver` is
 * attached there, not on the scroller itself, because the scroller's own
 * size does not change as content is appended.
 */
export function useStickToBottom(
  ref: React.RefObject<HTMLElement | null>,
  threshold = 24,
): StickToBottom {
  const [isAtBottom, setIsAtBottom] = useState(true);
  const isAtBottomRef = useRef(true);

  const setAtBottom = (value: boolean) => {
    isAtBottomRef.current = value;
    setIsAtBottom(value);
  };

  useEffect(() => {
    const scroller = ref.current;
    if (!scroller) return;

    const checkAtBottom = () => {
      const atBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight <= threshold;
      setAtBottom(atBottom);
    };

    scroller.addEventListener("scroll", checkAtBottom);
    checkAtBottom();

    const content = scroller.firstElementChild;
    let observer: ResizeObserver | undefined;
    if (content) {
      observer = new ResizeObserver(() => {
        if (isAtBottomRef.current) {
          scroller.scrollTop = scroller.scrollHeight;
        }
      });
      observer.observe(content);
    }

    return () => {
      scroller.removeEventListener("scroll", checkAtBottom);
      observer?.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref, threshold]);

  const scrollToBottom = () => {
    const scroller = ref.current;
    if (!scroller) return;
    scroller.scrollTop = scroller.scrollHeight;
    setAtBottom(true);
  };

  return { isAtBottom, scrollToBottom };
}
