import { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ImagePlus, X, Download, ArrowUp } from 'lucide-react';

const PLACEHOLDER_PHRASES = [
  "Describe how it should move",
  "Anything you want",
  "What happens next",
  "What do you want to see",
];

function useTypingPlaceholder(phrases: string[], typingSpeed = 50, pauseDuration = 2000, deletingSpeed = 30) {
  const [displayText, setDisplayText] = useState('');
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [isTyping, setIsTyping] = useState(true);

  useEffect(() => {
    const currentPhrase = phrases[phraseIndex];
    let timeout: ReturnType<typeof setTimeout>;

    if (isTyping) {
      if (displayText.length < currentPhrase.length) {
        // Still typing
        timeout = setTimeout(() => {
          setDisplayText(currentPhrase.slice(0, displayText.length + 1));
        }, typingSpeed);
      } else {
        // Finished typing, pause then start deleting
        timeout = setTimeout(() => {
          setIsTyping(false);
        }, pauseDuration);
      }
    } else {
      if (displayText.length > 0) {
        // Still deleting
        timeout = setTimeout(() => {
          setDisplayText(displayText.slice(0, -1));
        }, deletingSpeed);
      } else {
        // Finished deleting, move to next phrase
        setPhraseIndex((prev) => (prev + 1) % phrases.length);
        setIsTyping(true);
      }
    }

    return () => clearTimeout(timeout);
  }, [displayText, phraseIndex, isTyping, phrases, typingSpeed, pauseDuration, deletingSpeed]);

  return displayText;
}

interface StudioInputProps {
  onClose: () => void;
  inline?: boolean;
}

export function StudioInput({ onClose, inline = false }: StudioInputProps) {
  const [image, setImage] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const animatedPlaceholder = useTypingPlaceholder(PLACEHOLDER_PHRASES);

  const handleImageUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const previewUrl = URL.createObjectURL(file);
    setImagePreview(previewUrl);

    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = reader.result as string;
      setImage(base64);
    };
    reader.readAsDataURL(file);
    setError(null);
    setVideoUrl(null);
  }, []);

  const handleGenerate = async () => {
    if (!image || !prompt.trim()) {
      setError('Please upload an image and enter a prompt');
      return;
    }

    setIsGenerating(true);
    setError(null);
    setVideoUrl(null);

    try {
      const response = await fetch('/api/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          image: image,
          prompt: prompt.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        const errorMsg = data.details 
          ? `${data.error}: ${data.details}` 
          : (data.error || 'Generation failed');
        console.error('Generation error:', data);
        throw new Error(errorMsg);
      }

      if (data.video) {
        setVideoUrl(data.video);
      } else if (data.url) {
        setVideoUrl(data.url);
      } else {
        throw new Error('No video in response');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate video');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = () => {
    if (!videoUrl) return;
    const link = document.createElement('a');
    link.href = videoUrl;
    link.download = `eclair-video-${Date.now()}.mp4`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const removeImage = () => {
    setImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const canGenerate = image && prompt.trim() && !isGenerating;

  const content = (
    <AnimatePresence mode="wait">
      {/* Video Result */}
      {videoUrl ? (
        <motion.div
          key="video"
          className="flex flex-col items-center gap-6 w-full"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.3 }}
        >
          <video
            src={videoUrl}
            controls
            autoPlay
            loop
            className="w-full aspect-video rounded-xl shadow-2xl"
          />
          <div className="flex gap-4">
            <button
              onClick={handleDownload}
              className="flex items-center gap-2 px-6 py-2 text-eclair-text/80 hover:text-eclair-text transition-colors text-sm"
            >
              <Download size={18} />
              Download
            </button>
            <button
              onClick={() => setVideoUrl(null)}
              className="flex items-center gap-2 px-6 py-2 text-eclair-text/80 hover:text-eclair-text transition-colors text-sm"
            >
              Create another
            </button>
          </div>
        </motion.div>
      ) : isGenerating ? (
        /* Loading State */
        <motion.div
          key="loading"
          className="flex flex-col items-center justify-center gap-6 py-12"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
        >
          {/* Progress Animation */}
          <div className="relative w-24 h-24">
            <svg className="w-full h-full animate-spin" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="currentColor"
                strokeWidth="4"
                className="text-eclair-border/30"
              />
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="currentColor"
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray="80 200"
                className="text-eclair-text"
              />
            </svg>
          </div>
          <p className="text-eclair-text/60 text-lg">Generating your video...</p>
        </motion.div>
      ) : (
        /* Input State */
        <motion.div
          key="input"
          className="flex flex-col items-center gap-6 w-full"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
        >
          {/* Uploaded Image Preview */}
          <AnimatePresence>
            {imagePreview && (
              <motion.div
                className="relative"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
              >
                <img
                  src={imagePreview}
                  alt="Preview"
                  className="max-w-xs max-h-48 rounded-lg object-cover shadow-lg"
                />
                <button
                  onClick={removeImage}
                  className="absolute -top-2 -right-2 w-6 h-6 bg-eclair-bg border border-eclair-border rounded-full flex items-center justify-center text-eclair-text/60 hover:text-eclair-text transition-colors"
                >
                  <X size={14} />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Chat Input Box */}
          <div className="w-full relative">
            <div className="flex items-center gap-3 bg-black/20 border border-eclair-border/40 rounded-2xl px-4 py-3 focus-within:border-eclair-text/40 transition-colors">
              {/* Image Upload Icon */}
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-eclair-text/50 hover:text-eclair-text transition-colors"
                title="Upload image"
              >
                <ImagePlus size={22} />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageUpload}
                className="hidden"
              />

              {/* Text Input */}
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder={animatedPlaceholder}
                className="flex-1 bg-transparent text-eclair-text placeholder:text-eclair-text/40 placeholder:text-center focus:outline-none text-base text-center"
                onKeyDown={(e) => e.key === 'Enter' && canGenerate && handleGenerate()}
              />

              {/* Generate Button */}
              <button
                onClick={handleGenerate}
                disabled={!canGenerate}
                className={`w-8 h-8 rounded-full flex items-center justify-center transition-all ${
                  canGenerate
                    ? 'bg-eclair-text text-eclair-bg hover:opacity-80'
                    : 'bg-eclair-border/30 text-eclair-text/30 cursor-not-allowed'
                }`}
              >
                <ArrowUp size={18} />
              </button>
            </div>
          </div>

          {/* Error message */}
          {error && (
            <p className="text-red-400 text-sm">{error}</p>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );

  // Inline mode: no backdrop/modal, just the content
  if (inline) {
    return content;
  }

  // Modal mode: backdrop + modal wrapper
  return (
    <>
      {/* Backdrop */}
      <motion.div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.3 }}
        onClick={onClose}
      />
      
      {/* Modal Content */}
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.3 }}
      >
        <motion.div
          className="relative w-full max-w-2xl bg-eclair-bg/95 backdrop-blur-md border border-eclair-border/60 rounded-3xl p-8 shadow-2xl pointer-events-auto"
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
        >
          {/* Close button - top right */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-eclair-text/60 hover:text-eclair-text transition-colors"
          >
            <X size={20} />
          </button>

          <div className="pt-4">
            {content}
          </div>
        </motion.div>
      </motion.div>
    </>
  );
}
