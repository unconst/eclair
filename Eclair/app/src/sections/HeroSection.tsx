import { motion } from 'framer-motion';
import { StaggeredLogo } from '@/components/StaggeredLogo';
import { VerticalText } from '@/components/VerticalText';
import { AnimatedHeadline } from '@/components/AnimatedHeadline';
import { InfoBlock } from '@/components/InfoBlock';
import { NavLink } from '@/components/NavLink';
import { fadeIn } from '@/lib/animations';

export function HeroSection() {
  return (
    <section className="min-h-screen w-full bg-eclair-bg relative overflow-hidden">
      {/* Main Content Container */}
      <div className="w-full min-h-screen px-6 md:px-12 lg:px-16 py-12 md:py-16 lg:py-20 flex flex-col">
        
        {/* Logo Area - Centered at top */}
        <div className="flex justify-center pt-4 md:pt-8">
          <StaggeredLogo text="ECLAIR" />
        </div>

        {/* Hero Content - Left aligned */}
        <div className="flex-1 flex flex-col justify-center mt-8 md:mt-16 lg:mt-24 max-w-5xl">
          {/* Subtitle */}
          <motion.p
            className="text-eclair-text text-base md:text-lg font-normal mb-6 md:mb-8"
            variants={fadeIn}
            initial="hidden"
            animate="visible"
            transition={{ delay: 0.6 }}
          >
            Bittensor AI Video Generation
          </motion.p>

          {/* Main Headline */}
          <AnimatedHeadline 
            phrases={[
              "Where imagination becomes motion.",
              "Where skill becomes production.",
              "Video by the people.",
              "Decentralized Motion Studio."
            ]}
            className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl xl:text-8xl"
            interval={4000}
          />
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
              <NavLink href="#features" delay={1.4}>Incentives</NavLink>
              <NavLink href="#studio" delay={1.5}>Studio</NavLink>
              <NavLink href="#contact" delay={1.6}>Mining</NavLink>
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
        <VerticalText text="ECLAIR.AI" delay={1.2} />
      </div>
    </section>
  );
}
