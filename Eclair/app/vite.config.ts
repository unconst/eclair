import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig, type Plugin } from "vite"
import { inspectAttr } from 'kimi-plugin-inspect-react'
import dotenv from 'dotenv'

// Load environment variables from .env file (try multiple locations)
dotenv.config() // ./Eclair/app/.env
dotenv.config({ path: path.resolve(__dirname, '../.env') }) // ./Eclair/.env  
dotenv.config({ path: path.resolve(__dirname, '../../.env') }) // ./.env (project root)

// Plugin to handle /api/generate locally during development
function apiGeneratePlugin(): Plugin {
  return {
    name: 'api-generate',
    configureServer(server) {
      server.middlewares.use('/api/generate', async (req, res) => {
        console.log('\n[API] /api/generate called');
        console.log('[API] Method:', req.method);
        
        if (req.method !== 'POST') {
          res.statusCode = 405;
          res.end(JSON.stringify({ error: 'Method not allowed' }));
          return;
        }

        const apiKey = process.env.CHUTES_API_KEY;
        console.log('[API] CHUTES_API_KEY present:', !!apiKey);
        console.log('[API] CHUTES_API_KEY length:', apiKey?.length || 0);
        
        if (!apiKey) {
          console.error('[API] ERROR: CHUTES_API_KEY not configured');
          res.statusCode = 500;
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ error: 'CHUTES_API_KEY not configured. Set it in your environment or .env file.' }));
          return;
        }

        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', async () => {
          try {
            const { image, prompt } = JSON.parse(body);
            console.log('[API] Prompt:', prompt);
            console.log('[API] Image length:', image?.length || 0);
            console.log('[API] Image prefix:', image?.substring(0, 50) || 'none');

            if (!image || !prompt) {
              console.error('[API] ERROR: Missing image or prompt');
              res.statusCode = 400;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ error: 'Image and prompt are required' }));
              return;
            }

            // Strip the data URL prefix if present - Chutes API expects raw base64
            let rawBase64 = image;
            if (image.includes(',')) {
              rawBase64 = image.split(',')[1];
              console.log('[API] Stripped data URL prefix, raw base64 length:', rawBase64.length);
            }

            const chutesUrl = 'https://chutes-wan-2-2-i2v-14b-fast.chutes.ai/generate';
            console.log('[API] Calling Chutes API:', chutesUrl);
            
            const requestBody = {
              fps: 16,
              fast: true,
              image: rawBase64,
              prompt: prompt,
              frames: 81,
              resolution: "480p",
            };
            console.log('[API] Request body (without image):', { ...requestBody, image: `[${image.length} chars]` });

            const response = await fetch(chutesUrl, {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${apiKey}`,
                'Content-Type': 'application/json',
              },
              body: JSON.stringify(requestBody),
            });

            console.log('[API] Chutes response status:', response.status);
            const contentType = response.headers.get('content-type') || '';
            console.log('[API] Chutes response content-type:', contentType);

            if (!response.ok) {
              const errorText = await response.text();
              console.error('[API] Chutes API error response:', errorText);
              res.statusCode = response.status;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ 
                error: `Chutes API error (${response.status})`, 
                details: errorText,
                status: response.status
              }));
              return;
            }

            // Check if response is binary video data (not JSON)
            if (contentType.includes('video') || contentType.includes('octet-stream')) {
              console.log('[API] Received binary video response');
              const videoBuffer = await response.arrayBuffer();
              const videoBase64 = Buffer.from(videoBuffer).toString('base64');
              const videoDataUrl = `data:video/mp4;base64,${videoBase64}`;
              console.log('[API] Converted to data URL, size:', videoBuffer.byteLength, 'bytes');
              
              res.statusCode = 200;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ video: videoDataUrl }));
              return;
            }

            // Try to parse as JSON (in case API returns URL instead of binary)
            const responseText = await response.text();
            
            // Check if it looks like binary data (starts with MP4 magic bytes)
            if (responseText.startsWith('ftyp') || responseText.charCodeAt(4) === 0x66) {
              console.log('[API] Detected binary video in text response, converting...');
              const encoder = new TextEncoder();
              const videoBytes = encoder.encode(responseText);
              const videoBase64 = Buffer.from(videoBytes).toString('base64');
              const videoDataUrl = `data:video/mp4;base64,${videoBase64}`;
              
              res.statusCode = 200;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ video: videoDataUrl }));
              return;
            }
            
            console.log('[API] Chutes response body (first 200 chars):', responseText.substring(0, 200));
            
            let data;
            try {
              data = JSON.parse(responseText);
            } catch (parseError) {
              console.error('[API] Failed to parse Chutes response as JSON');
              // Last resort: assume it's video data
              const videoBase64 = Buffer.from(responseText, 'binary').toString('base64');
              const videoDataUrl = `data:video/mp4;base64,${videoBase64}`;
              
              res.statusCode = 200;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ video: videoDataUrl }));
              return;
            }
            
            console.log('[API] Chutes response data keys:', Object.keys(data));
            console.log('[API] Success! Returning video data');
            
            res.statusCode = 200;
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify(data));
          } catch (error) {
            console.error('[API] Error generating video:', error);
            res.statusCode = 500;
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ 
              error: 'Internal server error', 
              details: error instanceof Error ? error.message : String(error),
              stack: error instanceof Error ? error.stack : undefined
            }));
          }
        });
      });
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [inspectAttr(), apiGeneratePlugin(), react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
