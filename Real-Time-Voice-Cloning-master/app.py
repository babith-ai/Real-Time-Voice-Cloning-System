"""
Flask web app for Real-Time Voice Cloning.
Allows users to record a voice sample and synthesize speech.
"""

import os
import io
from pathlib import Path
import numpy as np
from flask import Flask, render_template, request, jsonify, send_file
import torch
import soundfile as sf
import logging

from encoder import inference as encoder
from encoder.params_model import model_embedding_size as speaker_embedding_size
from synthesizer.inference import Synthesizer
from vocoder import inference as vocoder
from utils.default_models import ensure_default_models

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max file size

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global model instances
encoder_model = None
synthesizer_model = None
vocoder_model = None


def load_models():
    """Load all models into memory."""
    global encoder_model, synthesizer_model, vocoder_model
    
    if encoder_model is None:
        logger.info("Loading models...")
        ensure_default_models(Path("saved_models"))
        
        encoder.load_model(Path("saved_models/default/encoder.pt"))
        encoder_model = True
        
        synthesizer_model = Synthesizer(Path("saved_models/default/synthesizer.pt"), verbose=False)
        vocoder.load_model(Path("saved_models/default/vocoder.pt"), verbose=False)
        vocoder_model = True
        
        logger.info("Models loaded successfully")


@app.route('/')
def index():
    """Serve the main UI page."""
    return render_template('index.html')


@app.route('/api/record', methods=['POST'])
def handle_record():
    """
    Receives recorded audio from frontend and extracts speaker embedding.
    Returns embedding info for synthesis.
    """
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400
        
        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({"error": "No audio file selected"}), 400
        
        # Read audio bytes
        audio_data = audio_file.read()
        logger.info(f"Received audio file: {audio_file.filename}, size: {len(audio_data)} bytes")
        
        # Load audio using soundfile
        try:
            audio_bytes = io.BytesIO(audio_data)
            wav, sr = sf.read(audio_bytes)
        except Exception as sf_err:
            logger.warning(f"Soundfile failed: {sf_err}, trying librosa...")
            import librosa
            audio_bytes = io.BytesIO(audio_data)
            wav, sr = librosa.load(audio_bytes, sr=None)
        
        logger.info(f"Loaded audio: sr={sr}, length={len(wav)} samples, duration={len(wav)/sr:.2f}s")
        
        # Resample to encoder sample rate if needed
        if sr != encoder.sampling_rate:
            import librosa
            logger.info(f"Resampling from {sr} to {encoder.sampling_rate}")
            wav = librosa.resample(wav, orig_sr=sr, target_sr=encoder.sampling_rate)
        
        # Ensure audio is float32 and in valid range
        wav = wav.astype(np.float32)
        if np.max(np.abs(wav)) > 0:
            wav = wav / np.max(np.abs(wav))
        
        # Preprocess and embed
        logger.info(f"Processing recording ({len(wav)} samples)")
        preprocessed = encoder.preprocess_wav(wav)
        logger.info(f"Preprocessed: {len(preprocessed)} samples")
        embed = encoder.embed_utterance(preprocessed)
        logger.info(f"Embedding created: shape={embed.shape}")
        
        # Store embedding in session or return it for next request
        return jsonify({
            "success": True,
            "message": "Voice recorded and processed successfully",
            "embedding_shape": list(embed.shape),
            "embedding": embed.tolist()  # Convert to list for JSON
        }), 200
    
    except Exception as e:
        logger.error(f"Error processing recording: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to process recording: {str(e)}"}), 500


@app.route('/api/synthesize', methods=['POST'])
def handle_synthesize():
    """
    Receives text and speaker embedding, synthesizes speech, and returns audio.
    """
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        embedding_list = data.get('embedding', None)
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        if embedding_list is None:
            return jsonify({"error": "Speaker embedding is required"}), 400
        
        # Convert embedding back to numpy array
        embed = np.array(embedding_list, dtype=np.float32)

        # Optional speed parameter: <1.0 slows down, >1.0 speeds up
        # Default 1.0 (no change)
        speed = float(data.get('speed', 1.0))
        
        logger.info(f"Synthesizing: '{text}'")
        
        # Synthesize mel spectrogram
        texts = [text]
        embeds = [embed]
        specs = synthesizer_model.synthesize_spectrograms(texts, embeds)
        spec = specs[0]
        
        # Generate waveform
        logger.info("Generating waveform...")
        wav = vocoder.infer_waveform(spec, normalize=True, batched=True)
        
        # Postprocess (pad a bit to avoid cutoff)
        wav = np.pad(wav, (0, synthesizer_model.sample_rate), mode="constant")
        wav = encoder.preprocess_wav(wav)

        # Normalize
        wav = wav / np.max(np.abs(wav)) * 0.99 if np.max(np.abs(wav)) > 0 else wav

        # Apply time-stretching if requested (slows/speeds without changing pitch)
        if abs(speed - 1.0) > 1e-6:
            try:
                import librosa
                logger.info(f"Applying time-stretch: rate={speed}")
                # librosa.effects.time_stretch expects a 1-D numpy array (mono)
                # Our outputs are mono, but if not, convert to mono
                if wav.ndim > 1:
                    wav_mono = np.mean(wav, axis=1)
                else:
                    wav_mono = wav

                # librosa expects floats in (-inf, +inf) but normalized — keep current dtype
                stretched = librosa.effects.time_stretch(wav_mono.astype(np.float32), rate=speed)

                # After stretching, ensure amplitude normalization again
                if np.max(np.abs(stretched)) > 0:
                    stretched = stretched / np.max(np.abs(stretched)) * 0.99

                wav = stretched.astype(np.float32)
            except Exception as ts_err:
                logger.warning(f"Time-stretch failed or librosa missing: {ts_err}. Skipping speed change.")
        
        # Convert to bytes
        audio_bytes = io.BytesIO()
        sf.write(audio_bytes, wav.astype(np.float32), synthesizer_model.sample_rate, format='WAV')
        audio_bytes.seek(0)
        
        logger.info("Synthesis complete")
        
        return send_file(
            audio_bytes,
            mimetype='audio/wav',
            as_attachment=True,
            download_name='synthesized_output.wav'
        )
    
    except Exception as e:
        logger.error(f"Error during synthesis: {str(e)}")
        return jsonify({"error": f"Synthesis failed: {str(e)}"}), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check and model status."""
    return jsonify({
        "status": "ok",
        "models_loaded": encoder_model is not None and vocoder_model is not None,
        "sample_rate": encoder.sampling_rate
    }), 200


@app.before_request
def startup():
    """Load models on first request."""
    global encoder_model
    if encoder_model is None:
        try:
            load_models()
        except Exception as e:
            logger.error(f"Failed to load models: {str(e)}")
            return jsonify({"error": "Failed to load models"}), 500


if __name__ == '__main__':
    logger.info("Starting Voice Cloning UI server...")
    app.run(debug=True, host='127.0.0.1', port=5000, threaded=True)
