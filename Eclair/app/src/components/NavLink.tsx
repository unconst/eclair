import { motion } from 'framer-motion';
import { fadeIn } from '@/lib/animations';

interface NavLinkProps {
  href: string;
  children: React.ReactNode;
  delay?: number;
}

export function NavLink({ href, children, delay = 0 }: NavLinkProps) {
  return (
    <motion.a
      href={href}
      className="text-eclair-text text-2xl font-normal block transition-all duration-300 ease-out hover:opacity-60 hover:translate-x-2"
      variants={fadeIn}
      initial="hidden"
      animate="visible"
      transition={{ delay }}
    >
      {children}
    </motion.a>
  );
}
