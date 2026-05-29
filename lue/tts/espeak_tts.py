"""eSpeak TTS implementation for the Lue eBook reader."""

import os
import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from rich.console import Console

from .base import TTSBase
from .. import config


class EspeakTTS(TTSBase):
    """
    A lightweight, offline TTS implementation using eSpeak.
    
    eSpeak is a compact open source software text-to-speech synthesizer
    that generates speech from text files or from the command line.
    This model enables fully offline TTS functionality without requiring
    internet connectivity or large language models.
    """
    
    @property
    def name(self) -> str:
        # Must match the filename: espeak_tts.py -> "espeak"
        return "espeak"

    @property
    def output_format(self) -> str:
        # eSpeak outputs WAV format
        return "wav"

    def __init__(self, console: Console, voice: str = None, lang: str = None):
        super().__init__(console, voice, lang)
        self.espeak_path = None
        
        # If the user doesn't provide a voice via --voice, use the default from config.py
        if self.voice is None:
            self.voice = config.TTS_VOICES.get(self.name)
        
        # If the user doesn't provide a language via --lang, use the default from config.py
        if self.lang is None:
            self.lang = config.TTS_LANGUAGE_CODES.get(self.name)

    async def initialize(self) -> bool:
        """
        Prepare the espeak model. Check for espeak installation.
        
        This checks if espeak is available on the system path and initializes
        the model for TTS synthesis.
        """
        loop = asyncio.get_running_loop()
        
        def _blocking_init():
            # Check if espeak is installed and accessible
            try:
                result = subprocess.run(
                    ["espeak", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return None
        
        try:
            self.console.print("[cyan]Initializing eSpeak TTS model...[/cyan]")
            
            espeak_info = await loop.run_in_executor(None, _blocking_init)
            
            if not espeak_info:
                self.console.print("[bold red]Error: 'espeak' command not found.[/bold red]")
                self.console.print("[yellow]Please install espeak to use this TTS model.[/yellow]")
                self.console.print("[yellow]  macOS: brew install espeak[/yellow]")
                self.console.print("[yellow]  Ubuntu/Debian: sudo apt install espeak[/yellow]")
                self.console.print("[yellow]  Fedora: sudo dnf install espeak[/yellow]")
                logging.error("espeak is not installed or not in PATH.")
                return False

            self.initialized = True
            self.console.print(f"[green]eSpeak TTS model initialized successfully.[/green]")
            self.console.print(f"[dim]{espeak_info}[/dim]")
            return True
        except Exception as e:
            self.console.print(f"[bold red]An unexpected error occurred during eSpeak initialization: {e}[/bold red]")
            logging.error("eSpeak async initialization failed.", exc_info=True)
            return False

    async def generate_audio(self, text: str, output_path: str):
        """
        Generate audio from text and save it to the given path.
        
        This is a synchronous function run in a separate thread to avoid
        blocking the async event loop.
        """
        if not self.initialized:
            raise RuntimeError("eSpeak has not been initialized.")

        def _blocking_generate():
            try:
                # Build espeak command with appropriate parameters
                # -w: write to WAV file
                # -v: voice (use language code if available)
                # -s: speed (words per minute, default 150)
                # -p: pitch (0-99, default 50)
                
                voice_param = self.voice if self.voice else "en"
                speed = "150"  # Default speed in words per minute
                
                cmd = [
                    "espeak",
                    "-w", output_path,  # Write to WAV file
                    "-v", voice_param,   # Voice/language
                    "-s", speed,         # Speed
                    text
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr or f"espeak exited with code {result.returncode}"
                    raise RuntimeError(f"eSpeak generation failed: {error_msg}")
                
                # Verify the output file was created
                if not os.path.exists(output_path):
                    raise RuntimeError(f"eSpeak did not create output file: {output_path}")
                    
            except subprocess.TimeoutExpired:
                raise RuntimeError("eSpeak audio generation timed out")
            except Exception as e:
                logging.error(f"Error during eSpeak audio generation: {e}", exc_info=True)
                raise e
        
        # Run the blocking generation in a separate thread
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _blocking_generate)

    async def get_raw_timing_data(self, text: str, output_path: str):
        """
        Extract raw word timing data from eSpeak.
        
        eSpeak does not provide precise word-level timing information through
        its command-line interface, so we return an empty list and let the
        timing calculator use fallback estimation.
        
        Returns:
            List: Empty list (eSpeak doesn't provide word timing data)
        """
        if not self.initialized:
            raise RuntimeError("eSpeak has not been initialized.")
        
        def _blocking_generate():
            try:
                # Generate the audio file
                voice_param = self.voice if self.voice else "en"
                speed = "150"  # Default speed in words per minute
                
                cmd = [
                    "espeak",
                    "-w", output_path,
                    "-v", voice_param,
                    "-s", speed,
                    text
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr or f"espeak exited with code {result.returncode}"
                    raise RuntimeError(f"eSpeak generation failed: {error_msg}")
                
                if not os.path.exists(output_path):
                    raise RuntimeError(f"eSpeak did not create output file: {output_path}")
                
                # eSpeak doesn't provide timing data, so return empty list
                # The timing calculator will use fallback estimation
                return []
                
            except subprocess.TimeoutExpired:
                raise RuntimeError("eSpeak audio generation timed out")
            except Exception as e:
                logging.error(f"Error during eSpeak audio generation: {e}", exc_info=True)
                raise e
        
        # Run the blocking generation in a separate thread
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _blocking_generate)
