import { motion } from 'framer-motion';
import { fadeIn } from '@/lib/animations';

interface InfoBlockProps {
  label: string;
  value: string;
  subValue?: string;
  delay?: number;
}

export function InfoBlock({ label, value, subValue, delay = 0 }: InfoBlockProps) {
  return (
    <motion.div
      className="flex flex-col gap-1"
      variants={fadeIn}
      initial="hidden"
      animate="visible"
      transition={{ delay }}
    >
      <span className="text-eclair-text-muted text-xs tracking-[0.1em] uppercase font-medium">
        {label}
      </span>
      <span className="text-eclair-text text-sm font-normal">
        {value}
      </span>
      {subValue && (
        <span className="text-eclair-text-muted text-sm font-normal">
          {subValue}
        </span>
      )}
    </motion.div>
  );
}
