import { motion } from 'framer-motion';
import { slideInFromRight } from '@/lib/animations';

interface VerticalTextProps {
  text: string;
  className?: string;
  delay?: number;
}

export function VerticalText({ text, className = '', delay = 0 }: VerticalTextProps) {
  return (
    <motion.span
      className={`text-eclair-text text-[11px] tracking-[0.15em] uppercase whitespace-nowrap ${className}`}
      variants={slideInFromRight}
      initial="hidden"
      animate="visible"
      transition={{ delay }}
      style={{
        writingMode: 'vertical-rl',
        textOrientation: 'mixed',
      }}
    >
      {text}
    </motion.span>
  );
}
