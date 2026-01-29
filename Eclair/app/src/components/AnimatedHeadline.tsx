import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';

interface AnimatedHeadlineProps {
  phrases: string[];
  className?: string;
  interval?: number;
}

export function AnimatedHeadline({ phrases, className = '', interval = 4000 }: AnimatedHeadlineProps) {
  const [currentIndex, setCurrentIndex] = useState(() => Math.floor(Math.random() * phrases.length));

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentIndex((prev) => {
        // Pick a random index different from the current one
        let next = Math.floor(Math.random() * phrases.length);
        while (next === prev && phrases.length > 1) {
          next = Math.floor(Math.random() * phrases.length);
        }
        return next;
      });
    }, interval);

    return () => clearInterval(timer);
  }, [phrases.length, interval]);

  const words = phrases[currentIndex].split(' ');

  return (
    <div className={`text-eclair-text font-normal leading-[1.05] tracking-tight relative min-h-[3.5em] ${className}`}>
      <AnimatePresence mode="wait">
        <motion.h1
          key={currentIndex}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
          className="flex flex-wrap absolute top-0 left-0 right-0"
        >
          {words.map((word, index) => (
            <motion.span
              key={index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ 
                duration: 0.4, 
                delay: index * 0.08,
                ease: [0.4, 0, 0.2, 1] 
              }}
              className="inline-block mr-[0.25em]"
            >
              {word}
            </motion.span>
          ))}
        </motion.h1>
      </AnimatePresence>
    </div>
  );
}
