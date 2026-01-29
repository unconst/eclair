export default async function handler(req, res) {
  // Only allow POST
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const apiKey = process.env.CHUTES_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: 'API key not configured' });
  }

  try {
    const { image, prompt } = req.body;

    if (!image || !prompt) {
      return res.status(400).json({ error: 'Image and prompt are required' });
    }

    // Strip the data URL prefix if present - Chutes API expects raw base64
    let rawBase64 = image;
    if (image.includes(',')) {
      rawBase64 = image.split(',')[1];
    }

    const response = await fetch('https://chutes-wan-2-2-i2v-14b-fast.chutes.ai/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        fps: 16,
        fast: true,
        image: rawBase64,
        prompt: prompt,
        frames: 81,
        resolution: "480p",
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Chutes API error:', errorText);
      return res.status(response.status).json({ error: 'Generation failed', details: errorText });
    }

    const contentType = response.headers.get('content-type') || '';
    
    // Check if response is binary video data (not JSON)
    if (contentType.includes('video') || contentType.includes('octet-stream')) {
      const videoBuffer = await response.arrayBuffer();
      const videoBase64 = Buffer.from(videoBuffer).toString('base64');
      const videoDataUrl = `data:video/mp4;base64,${videoBase64}`;
      return res.status(200).json({ video: videoDataUrl });
    }

    // Try to parse as JSON
    const responseText = await response.text();
    
    // Check if it looks like binary data (MP4 magic bytes)
    if (responseText.startsWith('ftyp') || (responseText.length > 4 && responseText.charCodeAt(4) === 0x66)) {
      const videoBase64 = Buffer.from(responseText, 'binary').toString('base64');
      const videoDataUrl = `data:video/mp4;base64,${videoBase64}`;
      return res.status(200).json({ video: videoDataUrl });
    }

    try {
      const data = JSON.parse(responseText);
      return res.status(200).json(data);
    } catch (parseError) {
      // Assume it's video data
      const videoBase64 = Buffer.from(responseText, 'binary').toString('base64');
      const videoDataUrl = `data:video/mp4;base64,${videoBase64}`;
      return res.status(200).json({ video: videoDataUrl });
    }
  } catch (error) {
    console.error('Error generating video:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
