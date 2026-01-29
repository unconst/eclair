import { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, X, Download, Loader2, Play } from 'lucide-react';

interface StudioProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Studio({ isOpen, onClose }: StudioProps) {
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

    // Create preview URL
    const previewUrl = URL.createObjectURL(file);
    setImagePreview(previewUrl);

    // Convert to base64
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

      // Assuming the API returns a video URL or base64 video
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

  const handleClose = () => {
    setImage(null);
    setImagePreview(null);
    setPrompt('');
    setVideoUrl(null);
    setError(null);
    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-eclair-bg"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4 }}
        >
          {/* Close button */}
          <button
            onClick={handleClose}
            className="absolute top-8 right-8 text-eclair-text hover:opacity-60 transition-opacity"
          >
            <X size={32} />
          </button>

          {/* Studio content */}
          <motion.div
            className="w-full max-w-4xl px-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ delay: 0.1, duration: 0.4 }}
          >
            {/* Title */}
            <h1 className="text-eclair-text text-4xl md:text-5xl lg:text-6xl font-normal mb-12 text-center">
              Studio
            </h1>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Left side - Input */}
              <div className="space-y-6">
                {/* Image upload area */}
                <div
                  className={`relative border-2 border-dashed border-eclair-border/60 rounded-lg aspect-video flex items-center justify-center cursor-pointer transition-all hover:border-eclair-text/60 ${
                    imagePreview ? 'p-0' : 'p-8'
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
                      <Upload className="mx-auto mb-4 text-eclair-text/60" size={48} />
                      <p className="text-eclair-text/80 text-lg">
                        Drop an image or click to upload
                      </p>
                      <p className="text-eclair-text/50 text-sm mt-2">
                        PNG, JPG up to 10MB
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

                {/* Prompt input */}
                <div>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Describe how the image should animate..."
                    className="w-full h-32 bg-transparent border-2 border-eclair-border/60 rounded-lg p-4 text-eclair-text placeholder:text-eclair-text/40 focus:outline-none focus:border-eclair-text/60 resize-none"
                  />
                </div>

                {/* Error message */}
                {error && (
                  <p className="text-red-400 text-sm">{error}</p>
                )}

                {/* Generate button */}
                <button
                  onClick={handleGenerate}
                  disabled={isGenerating || !image || !prompt.trim()}
                  className="w-full py-4 bg-eclair-text text-eclair-bg font-medium text-lg rounded-lg transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="animate-spin" size={24} />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Play size={24} />
                      Generate Video
                    </>
                  )}
                </button>
              </div>

              {/* Right side - Video output */}
              <div className="space-y-6">
                <div className="border-2 border-eclair-border/60 rounded-lg aspect-video flex items-center justify-center bg-black/20">
                  {videoUrl ? (
                    <video
                      src={videoUrl}
                      controls
                      autoPlay
                      loop
                      className="w-full h-full object-contain rounded-lg"
                    />
                  ) : (
                    <div className="text-center text-eclair-text/40">
                      <Play size={48} className="mx-auto mb-4 opacity-40" />
                      <p>Your video will appear here</p>
                    </div>
                  )}
                </div>

                {/* Download button */}
                {videoUrl && (
                  <motion.button
                    onClick={handleDownload}
                    className="w-full py-4 border-2 border-eclair-text text-eclair-text font-medium text-lg rounded-lg transition-all hover:bg-eclair-text hover:text-eclair-bg flex items-center justify-center gap-3"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <Download size={24} />
                    Download Video
                  </motion.button>
                )}
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
