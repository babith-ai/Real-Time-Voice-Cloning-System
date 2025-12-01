# Voice Cloning Studio - Web UI

A modern, interactive web-based interface for the Real-Time Voice Cloning project. Record a voice sample and synthesize speech in a few clicks!

## Features

✨ **Modern Web Interface**
- Clean, intuitive design with step-by-step workflow
- Real-time audio visualization (waveform)
- Responsive mobile-friendly layout

🎤 **Voice Recording**
- Browser-based microphone recording (no file uploads needed)
- Visual recording timer
- Waveform display
- Playback of your recorded sample

🎵 **Speech Synthesis**
- Synthesize any text using your recorded voice
- Up to 500 characters per synthesis
- Real-time generation status

⬇️ **Output Management**
- Built-in audio player for synthesized speech
- One-click WAV download
- Play/pause controls

## Installation

1. **Ensure the main project is set up:**
   ```bash
   # Go to project root
   cd Real-Time-Voice-Cloning
   
   # Install uv package manager (if not already installed)
   pip install uv
   ```

2. **Flask is already added to `pyproject.toml`**. No extra steps needed.

## Running the Web UI

```powershell
# From the project root, use uv to run the Flask app
uv run --extra cpu app.py
```

Or if you prefer to use the activated venv directly:

```powershell
# Activate venv
.venv\Scripts\Activate.ps1

# Run Flask app
python app.py
```

The server will start at **http://127.0.0.1:5000**

## Usage

1. **Open Browser**: Go to `http://127.0.0.1:5000`

2. **Record Voice Sample**
   - Click "Start Recording"
   - Speak naturally for 3-10 seconds
   - Click "Stop Recording"
   - Review the waveform and play back
   - Click "Use This Recording" to confirm

3. **Synthesize Speech**
   - Enter text (up to 500 characters)
   - Click "Synthesize Speech"
   - Wait for processing (typically 1-2 minutes on CPU)

4. **Listen & Download**
   - Play the generated speech in the browser
   - Download the WAV file
   - Share or use as needed

## Tips for Best Results

### Recording Quality
- Use a **quiet environment** to reduce background noise
- Speak **clearly and naturally**
- Keep **consistent volume**
- Record for **3-10 seconds** (longer = better embedding)

### Synthesis Quality
- Use **natural, flowing text** without special characters
- Keep sentences **under 20 words** per synthesis
- Avoid **rapid emotional shifts** in text
- Use **punctuation** for natural pauses (commas, periods)

### Microphone Access
- Allow microphone access when prompted by your browser
- Check browser settings if access is denied
- Some corporate firewalls may block audio APIs

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Microphone permission denied" | Enable microphone in browser settings (Settings → Site Settings → Microphone) |
| Synthesis is very slow | This is normal on CPU. GPU will be 10-20x faster. Models are large and inference takes time. |
| Audio quality is poor | Record a longer sample (5-10 seconds) with less background noise |
| Page won't load | Check that `http://127.0.0.1:5000` is correct in address bar; make sure Flask server is running |
| Blank page / errors in console | Check terminal for Flask errors; try refreshing browser (Ctrl+R) |

## File Structure

```
.
├── app.py                      # Flask backend (routes, inference)
├── templates/
│   └── index.html             # Main UI page (HTML)
├── static/
│   ├── app.js                 # Frontend logic (recording, synthesis)
│   └── style.css              # Styling
└── saved_models/default/
    ├── encoder.pt             # Speaker encoder
    ├── synthesizer.pt         # Tacotron synthesizer
    └── vocoder.pt             # WaveRNN vocoder
```

## Technical Details

### Backend (Flask)
- **`/api/record`** - Receives recorded audio, extracts speaker embedding
- **`/api/synthesize`** - Generates speech from text + embedding
- **`/api/health`** - Health check endpoint

### Frontend (JS)
- Uses **Web Audio API** for recording
- **Canvas** for waveform visualization
- **Fetch API** for backend communication
- Handles loading states and user feedback

### Models
- **Encoder**: Extracts speaker embedding from 5-10 second voice sample
- **Synthesizer** (Tacotron): Converts text to mel-spectrograms
- **Vocoder** (WaveRNN): Converts mel-spectrograms to audio waveform

## Performance Notes

⏱️ **CPU Inference Times (Approximate)**
- Recording processing: 5-10 seconds
- Text synthesis: 30-60 seconds
- Vocoder generation: 30-120 seconds (depends on text length)
- **Total per synthesis**: 1-3 minutes

💻 **GPU would be 10-20x faster** (if available)

## Advanced Usage

### Command Line Synthesis
If you prefer the original CLI:
```powershell
uv run --extra cpu demo_cli.py
```

### Custom Output Path
Currently outputs are served/downloaded from the browser. To save to disk:
- Download from the web UI, or
- Modify `app.py` to save to a specific folder

## Future Enhancements

- [ ] Upload reference audio instead of recording
- [ ] Batch synthesis from text files
- [ ] Voice quality scoring
- [ ] Real-time waveform recording visualization
- [ ] GPU support toggle in UI
- [ ] Multiple voice samples / voice mixing

## License

Same as the main Real-Time Voice Cloning project.

## Support

For issues related to:
- **Voice cloning models**: See main README.md
- **Web UI**: Check this file or raise an issue
- **Recording/Microphone**: Check browser developer console (F12)
