import { motion, AnimatePresence } from 'framer-motion';
import { StaggeredLogo } from '@/components/StaggeredLogo';
import { VerticalText } from '@/components/VerticalText';
import { AnimatedHeadline } from '@/components/AnimatedHeadline';
import { InfoBlock } from '@/components/InfoBlock';
import { NavLink } from '@/components/NavLink';
import { StudioInput } from '@/components/StudioInput';
import { fadeIn } from '@/lib/animations';

interface HeroSectionProps {
  isStudioOpen: boolean;
  onStudioClick: () => void;
  onStudioClose: () => void;
}

const heroSubtitle = "Bittensor for AI Generation";

const heroPhrases = [
  "Video models owned by everyone.",
  "AI video, without gatekeepers.",
  "Decentralized video creation.",
  "AI for the people.",
  "Open video intelligence.",
  "Permissionless creativity at scale.",
  "Innovation without permission.",
  "No labs. No licenses. No kings.",
  "Build intelligence outside the fortress.",
  "Progress shouldn't need approval.",
  "The future of video shouldn't belong to five companies.",
  "Escape centralized AI.",
  "Built by the network.",
  "Owned by its builders.",
  "Trained by the many, not the few.",
  "Video models as public infrastructure.",
  "Collectively trained. Publicly owned.",
  "From the crowd, not the corporation.",
  "When intelligence centralizes, progress stalls.",
  "Open incentives beat closed labs.",
  "Decentralization is how progress survives.",
  "Markets for intelligence, not monopolies.",
  "The antidote to captured AI.",
  "A video commons for the internet.",
  "Let creativity compound.",
  "Intelligence grows faster when it's free.",
  "Open models. Open future.",
  "The camera belongs to everyone.",
];

export function HeroSection({ isStudioOpen, onStudioClick, onStudioClose }: HeroSectionProps) {
  return (
    <section className="min-h-screen w-full bg-eclair-bg relative overflow-hidden">
      {/* Main Content Container */}
      <div className="w-full min-h-screen px-6 md:px-12 lg:px-16 pt-6 md:pt-8 lg:pt-10 pb-12 md:pb-16 lg:pb-20 flex flex-col">
        
        {/* Header with Logo - Top left */}
        <div className="flex items-center justify-between">
          <a 
            href="/" 
            className="cursor-pointer hover:opacity-80 transition-opacity"
            onClick={(e) => {
              e.preventDefault();
              onStudioClose();
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
          >
            <motion.img 
              src="/logo.png" 
              alt="Eclair Logo" 
              className="w-8 h-8 md:w-10 md:h-10"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
            />
          </a>
        </div>

        {/* Staggered Logo - Centered at top */}
        <div className="flex justify-center mt-2 md:mt-4">
          <StaggeredLogo text="ECLAIR" />
        </div>

        {/* Hero Content - Left aligned */}
        <div className="flex-1 flex flex-col justify-center mt-8 md:mt-16 lg:mt-24 max-w-5xl relative">
          <AnimatePresence>
            {!isStudioOpen && (
              <motion.div
                key="headline"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
              >
                {/* Subtitle */}
                <motion.p
                  className="text-eclair-text text-base md:text-lg font-normal mb-6 md:mb-8"
                  variants={fadeIn}
                  initial="hidden"
                  animate="visible"
                  transition={{ delay: 0.6 }}
                >
                  {heroSubtitle}
                </motion.p>

                {/* Main Headline */}
                <AnimatedHeadline 
                  phrases={heroPhrases}
                  className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl xl:text-8xl"
                  interval={4000}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Footer Info Bar */}
        <div className="mt-auto pt-12 md:pt-16 lg:pt-24">
          {/* Divider Line */}
          <motion.div
            className="w-full h-px bg-eclair-border/40 mb-8 md:mb-10"
            initial={{ scaleX: 0, originX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: 1.1, duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
          />

          {/* Info Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12">
            {/* Current Status */}
            <InfoBlock
              label="Current Status"
              value="Live on Mainnet"
              subValue="2025"
              delay={1.2}
            />

            {/* Location */}
            <InfoBlock
              label="Location"
              value="The world; 24/7"
              delay={1.3}
            />

            {/* Navigation */}
            <motion.div
              className="flex flex-col gap-2"
              variants={fadeIn}
              initial="hidden"
              animate="visible"
              transition={{ delay: 1.4 }}
            >
              <NavLink href="https://taomarketcap.com/subnets/28/miners" delay={1.4}>Incentives</NavLink>
              <NavLink onClick={onStudioClick} delay={1.5}>Studio</NavLink>
              <NavLink href="https://github.com/unconst/eclair" delay={1.6}>Mining</NavLink>
            </motion.div>
          </div>
        </div>
      </div>

      {/* Vertical Side Text - Right Side */}
      <div className="hidden lg:flex flex-col items-center gap-6 absolute right-8 top-1/2 -translate-y-1/2">
        <VerticalText text="NO. 0001-EV" delay={1.0} />
        <VerticalText text="SCROLL TO EXPLORE" delay={1.1} />
      </div>

      {/* Far Right Edge Text */}
      <div className="hidden lg:block absolute right-2 top-1/2 -translate-y-1/2">
        <VerticalText text="ECLAIR.EARTH" delay={1.2} />
      </div>

      {/* Studio Input - Slightly below center */}
      <AnimatePresence>
        {isStudioOpen && (
          <motion.div
            key="studio"
            className="absolute inset-0 flex items-center justify-center pt-24 pointer-events-none"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
          >
            <div className="w-full max-w-4xl px-6 pointer-events-auto">
              <StudioInput onClose={onStudioClose} inline />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
