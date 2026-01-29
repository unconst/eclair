import { useState } from 'react';
import { HeroSection } from '@/sections/HeroSection';
import { Studio } from '@/components/Studio';
import './App.css';

function App() {
  const [isStudioOpen, setIsStudioOpen] = useState(false);

  return (
    <main className="min-h-screen bg-eclair-bg">
      <HeroSection onStudioClick={() => setIsStudioOpen(true)} />
      <Studio isOpen={isStudioOpen} onClose={() => setIsStudioOpen(false)} />
    </main>
  );
}

export default App;
