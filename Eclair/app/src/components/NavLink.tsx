import { motion } from 'framer-motion';
import { fadeIn } from '@/lib/animations';

interface NavLinkProps {
  href?: string;
  onClick?: () => void;
  children: React.ReactNode;
  delay?: number;
}

export function NavLink({ href, onClick, children, delay = 0 }: NavLinkProps) {
  const className = "text-eclair-text text-2xl font-normal block transition-all duration-300 ease-out hover:opacity-60 hover:translate-x-2 cursor-pointer";

  if (onClick) {
    return (
      <motion.button
        onClick={onClick}
        className={className}
        variants={fadeIn}
        initial="hidden"
        animate="visible"
        transition={{ delay }}
      >
        {children}
      </motion.button>
    );
  }

  return (
    <motion.a
      href={href}
      className={className}
      variants={fadeIn}
      initial="hidden"
      animate="visible"
      transition={{ delay }}
    >
      {children}
    </motion.a>
  );
}
