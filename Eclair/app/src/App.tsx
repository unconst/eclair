import { useState } from 'react';
import { HeroSection } from '@/sections/HeroSection';
import './App.css';

function App() {
  const [isStudioOpen, setIsStudioOpen] = useState(false);

  return (
    <main className="min-h-screen bg-eclair-bg">
      <HeroSection 
        isStudioOpen={isStudioOpen}
        onStudioClick={() => setIsStudioOpen(true)} 
        onStudioClose={() => setIsStudioOpen(false)}
      />
    </main>
  );
}

export default App;
