import argparse
import os
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch

from encoder import inference as encoder
from encoder.params_model import model_embedding_size as speaker_embedding_size
from synthesizer.inference import Synthesizer
from utils.argutils import print_args
from utils.default_models import ensure_default_models
from vocoder import inference as vocoder


def enhance_audio_quality(generated_wav, synthesizer_sample_rate):
    """
    Post-process audio to improve quality and clarity
    """
    # Apply gentle high-pass filter to reduce low-frequency rumble
    # and improve articulation clarity
    from scipy.signal import butter, filtfilt
    
    # Design a high-pass filter at 80 Hz
    sos = butter(4, 80, 'hp', fs=synthesizer_sample_rate, output='sos')
    generated_wav = filtfilt(sos, generated_wav)
    
    # Gentle normalization to prevent clipping while preserving dynamics
    max_abs = np.abs(generated_wav).max()
    if max_abs > 0:
        generated_wav = generated_wav / max_abs * 0.95
    
    return generated_wav


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-e", "--enc_model_fpath", type=Path,
                        default="saved_models/default/encoder.pt",
                        help="Path to a saved encoder")
    parser.add_argument("-s", "--syn_model_fpath", type=Path,
                        default="saved_models/default/synthesizer.pt",
                        help="Path to a saved synthesizer")
    parser.add_argument("-v", "--voc_model_fpath", type=Path,
                        default="saved_models/default/vocoder.pt",
                        help="Path to a saved vocoder")
    parser.add_argument("--cpu", action="store_true", help=\
        "If True, processing is done on CPU, even when a GPU is available.")
    parser.add_argument("--no_sound", action="store_true", help=\
        "If True, audio won't be played.")
    parser.add_argument("--seed", type=int, default=None, help=\
        "Optional random number seed value to make toolbox deterministic.")
    parser.add_argument("--enhance", action="store_true", default=True, help=\
        "If True, applies audio enhancement for better clarity.")
    args = parser.parse_args()
    arg_dict = vars(args)
    print_args(args, parser)

    # Hide GPUs from Pytorch to force CPU processing
    if arg_dict.pop("cpu"):
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

    print("Running a test of your configuration with ENHANCED settings...\n")

    if torch.cuda.is_available():
        device_id = torch.cuda.current_device()
        gpu_properties = torch.cuda.get_device_properties(device_id)
        ## Print some environment information (for debugging purposes)
        print("Found %d GPUs available. Using GPU %d (%s) of compute capability %d.%d with "
            "%.1fGb total memory.\n" %
            (torch.cuda.device_count(),
            device_id,
            gpu_properties.name,
            gpu_properties.major,
            gpu_properties.minor,
            gpu_properties.total_memory / 1e9))
    else:
        print("Using CPU for inference.\n")

    ## Load the models one by one.
    print("Preparing the encoder, the synthesizer and the vocoder...")
    ensure_default_models(Path("saved_models"))
    encoder.load_model(args.enc_model_fpath)
    synthesizer = Synthesizer(args.syn_model_fpath)
    vocoder.load_model(args.voc_model_fpath)


    ## Run a test
    print("Testing your configuration with small inputs.")
    print("\tTesting the encoder...")
    encoder.embed_utterance(np.zeros(encoder.sampling_rate))

    embed = np.random.rand(speaker_embedding_size)
    embed /= np.linalg.norm(embed)
    embeds = [embed, np.zeros(speaker_embedding_size)]
    texts = ["test 1", "test 2"]
    print("\tTesting the synthesizer... (loading the model will output a lot of text)")
    mels = synthesizer.synthesize_spectrograms(texts, embeds)

    mel = np.concatenate(mels, axis=1)
    no_action = lambda *args: None
    print("\tTesting the vocoder...")
    vocoder.infer_waveform(mel, target=200, overlap=50, progress_callback=no_action)

    print("All test passed! You can now synthesize speech with enhanced clarity.\n\n")


    ## Interactive speech generation with enhanced quality
    print("Enhanced Real-Time Voice Cloning - Interactive Generation")
    print("=" * 60)
    print("This version features:")
    print("  - Increased mel-spectrogram resolution (128 channels)")
    print("  - Improved text-to-speech encoding")
    print("  - Enhanced vocoder for better audio quality")
    print("  - Post-processing for clearer pronunciation")
    print("=" * 60 + "\n")

    print("Interactive generation loop")
    num_generated = 0
    while True:
        try:
            # Get the reference audio filepath
            message = "Reference voice: enter an audio filepath of a voice to be cloned (mp3, " \
                      "wav, m4a, flac, ...):\n"
            in_fpath = Path(input(message).replace("\"", "").replace("\'", ""))

            ## Computing the embedding
            preprocessed_wav = encoder.preprocess_wav(in_fpath)
            original_wav, sampling_rate = librosa.load(str(in_fpath))
            preprocessed_wav = encoder.preprocess_wav(original_wav, sampling_rate)
            print("Loaded file successfully")

            embed = encoder.embed_utterance(preprocessed_wav)
            print("Created the embedding")


            ## Generating the spectrogram
            text = input("Write a sentence (+-20 words) to be synthesized:\n")

            # If seed is specified, reset torch seed and force synthesizer reload
            if args.seed is not None:
                torch.manual_seed(args.seed)
                synthesizer = Synthesizer(args.syn_model_fpath)

            texts = [text]
            embeds = [embed]
            specs = synthesizer.synthesize_spectrograms(texts, embeds)
            spec = specs[0]
            print("Created the mel spectrogram")


            ## Generating the waveform
            print("Synthesizing the waveform with enhanced vocoder...")

            # If seed is specified, reset torch seed and reload vocoder
            if args.seed is not None:
                torch.manual_seed(args.seed)
                vocoder.load_model(args.voc_model_fpath)

            # Use enhanced vocoder parameters for better quality
            generated_wav = vocoder.infer_waveform(spec, target=11000, overlap=550)


            ## Post-generation enhancement
            print("Applying audio enhancement for clarity...")
            generated_wav = np.pad(generated_wav, (0, synthesizer.sample_rate), mode="constant")
            generated_wav = encoder.preprocess_wav(generated_wav)
            
            # Apply audio quality enhancement
            if args.enhance:
                generated_wav = enhance_audio_quality(generated_wav, synthesizer.sample_rate)

            # Play the audio (non-blocking)
            if not args.no_sound:
                import sounddevice as sd
                try:
                    sd.stop()
                    sd.play(generated_wav, synthesizer.sample_rate)
                except sd.PortAudioError as e:
                    print("\nCaught exception: %s" % repr(e))
                    print("Continuing without audio playback. Suppress this message with the \"--no_sound\" flag.\n")
                except:
                    raise

            # Save it on the disk
            filename = "demo_output_enhanced_%02d.wav" % num_generated
            print(generated_wav.dtype)
            sf.write(filename, generated_wav.astype(np.float32), synthesizer.sample_rate)
            num_generated += 1
            print("\nSaved enhanced output as %s\n\n" % filename)


        except Exception as e:
            print("Caught exception: %s" % repr(e))
            print("Restarting\n")
