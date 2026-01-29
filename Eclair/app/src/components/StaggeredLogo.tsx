import { motion } from 'framer-motion';
import { staggerContainer, fadeInDown } from '@/lib/animations';

interface StaggeredLogoProps {
  text: string;
  className?: string;
}

export function StaggeredLogo({ text, className = '' }: StaggeredLogoProps) {
  // Generate staggered lines (each line is one character shorter)
  const lines: string[] = [];
  for (let i = 0; i < text.length; i++) {
    lines.push(text.slice(0, text.length - i));
  }

  return (
    <motion.div
      className={`flex flex-col items-center ${className}`}
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
    >
      {lines.map((line, index) => (
        <motion.span
          key={index}
          variants={fadeInDown}
          className="text-eclair-text font-bold text-xl md:text-2xl tracking-wider leading-tight"
          style={{
            opacity: 1 - index * 0.15, // Slight fade for lower lines
          }}
        >
          {line}
        </motion.span>
      ))}
    </motion.div>
  );
}
