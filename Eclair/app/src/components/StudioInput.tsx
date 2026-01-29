import { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ImagePlus, X, Download, ArrowUp } from 'lucide-react';

interface StudioInputProps {
  onClose: () => void;
}

export function StudioInput({ onClose }: StudioInputProps) {
  const [image, setImage] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
        throw new Error(data.error || 'Generation failed');
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

  return (
    <motion.div
      className="w-full flex flex-col items-center justify-center min-h-[400px]"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.4 }}
    >
      {/* Close button - top right */}
      <button
        onClick={onClose}
        className="absolute top-0 right-0 text-eclair-text/60 hover:text-eclair-text transition-colors"
      >
        <X size={20} />
      </button>

      <AnimatePresence mode="wait">
        {/* Video Result */}
        {videoUrl ? (
          <motion.div
            key="video"
            className="flex flex-col items-center gap-6 w-full max-w-2xl"
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
            className="flex flex-col items-center gap-6"
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
            className="flex flex-col items-center gap-6 w-full max-w-xl"
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
              <div className="flex items-center gap-3 bg-eclair-bg border border-eclair-border/60 rounded-2xl px-4 py-3 shadow-sm focus-within:border-eclair-text/40 transition-colors">
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
                  placeholder="Describe how it should move..."
                  className="flex-1 bg-transparent text-eclair-text placeholder:text-eclair-text/40 focus:outline-none text-base"
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

            {/* Helper text */}
            <p className="text-eclair-text/40 text-xs">
              Upload an image, describe the motion, and generate
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
