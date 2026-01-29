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

    const response = await fetch('https://chutes-wan-2-2-i2v-14b-fast.chutes.ai/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        fps: 16,
        fast: true,
        image: image,
        prompt: prompt,
        guidance_scale: 1,
        guidance_scale_2: 1,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Chutes API error:', errorText);
      return res.status(response.status).json({ error: 'Generation failed', details: errorText });
    }

    const data = await response.json();
    return res.status(200).json(data);
  } catch (error) {
    console.error('Error generating video:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
}
