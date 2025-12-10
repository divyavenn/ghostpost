import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface AnimatedListItemProps {
  children: ReactNode;
  /** Unique key for AnimatePresence tracking */
  itemKey: string;
  /** Animation variant: 'scale' (default), 'slide-right', 'slide-left', 'fade' */
  variant?: "scale" | "slide-right" | "slide-left" | "fade";
  /** Duration in seconds */
  duration?: number;
  /** Custom styles */
  style?: React.CSSProperties;
  /** Class name */
  className?: string;
}

const variants = {
  scale: {
    initial: { opacity: 0, scale: 0.8 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.8 },
  },
  "slide-right": {
    initial: { opacity: 0, x: -50 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: 150 },
  },
  "slide-left": {
    initial: { opacity: 0, x: 50 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -150 },
  },
  fade: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
};

/**
 * Wraps content with enter/exit animations.
 * Use with AnimatePresence for exit animations to work.
 *
 * @example
 * <AnimatePresence>
 *   {items.map(item => (
 *     <AnimatedListItem key={item.id} itemKey={item.id} variant="scale">
 *       <YourComponent />
 *     </AnimatedListItem>
 *   ))}
 * </AnimatePresence>
 */
export function AnimatedListItem({
  children,
  itemKey,
  variant = "scale",
  duration = 0.3,
  style,
  className,
}: AnimatedListItemProps) {
  const selectedVariant = variants[variant];

  return (
    <motion.div
      key={itemKey}
      initial={selectedVariant.initial}
      animate={selectedVariant.animate}
      exit={selectedVariant.exit}
      transition={{
        duration,
        ease: "easeInOut",
      }}
      style={style}
      className={className}
      layout
    >
      {children}
    </motion.div>
  );
}

export default AnimatedListItem;
