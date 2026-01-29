import { useState, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Upload, X, Download, Loader2, Play } from 'lucide-react';

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

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file || !file.type.startsWith('image/')) return;

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

  return (
    <motion.div
      className="w-full"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.4 }}
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-0 right-0 text-eclair-text hover:opacity-60 transition-opacity"
      >
        <X size={24} />
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-8">
        {/* Left side - Image upload */}
        <div
          className={`relative border-2 border-dashed border-eclair-border/60 rounded-lg aspect-video flex items-center justify-center cursor-pointer transition-all hover:border-eclair-text/60 ${
            imagePreview ? 'p-0' : 'p-6'
          }`}
          onClick={() => fileInputRef.current?.click()}
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
        >
          {imagePreview ? (
            <img
              src={imagePreview}
              alt="Preview"
              className="w-full h-full object-cover rounded-lg"
            />
          ) : (
            <div className="text-center">
              <Upload className="mx-auto mb-3 text-eclair-text/60" size={36} />
              <p className="text-eclair-text/80 text-base">
                Drop image or click
              </p>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            className="hidden"
          />
        </div>

        {/* Right side - Video output or prompt */}
        <div className="border-2 border-eclair-border/60 rounded-lg aspect-video flex items-center justify-center bg-black/10">
          {videoUrl ? (
            <video
              src={videoUrl}
              controls
              autoPlay
              loop
              className="w-full h-full object-contain rounded-lg"
            />
          ) : (
            <div className="text-center text-eclair-text/40 p-6">
              <Play size={36} className="mx-auto mb-3 opacity-40" />
              <p className="text-sm">Video appears here</p>
            </div>
          )}
        </div>
      </div>

      {/* Prompt and controls */}
      <div className="mt-6 flex flex-col sm:flex-row gap-4">
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe how the image should animate..."
          className="flex-1 bg-transparent border-2 border-eclair-border/60 rounded-lg px-4 py-3 text-eclair-text placeholder:text-eclair-text/40 focus:outline-none focus:border-eclair-text/60 text-lg"
          onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
        />
        
        <button
          onClick={handleGenerate}
          disabled={isGenerating || !image || !prompt.trim()}
          className="px-8 py-3 bg-eclair-text text-eclair-bg font-medium text-lg rounded-lg transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 whitespace-nowrap"
        >
          {isGenerating ? (
            <>
              <Loader2 className="animate-spin" size={20} />
              Generating...
            </>
          ) : (
            <>
              <Play size={20} />
              Generate
            </>
          )}
        </button>

        {videoUrl && (
          <button
            onClick={handleDownload}
            className="px-6 py-3 border-2 border-eclair-text text-eclair-text font-medium rounded-lg transition-all hover:bg-eclair-text hover:text-eclair-bg flex items-center justify-center gap-2"
          >
            <Download size={20} />
          </button>
        )}
      </div>

      {/* Error message */}
      {error && (
        <p className="text-red-400 text-sm mt-3">{error}</p>
      )}
    </motion.div>
  );
}
