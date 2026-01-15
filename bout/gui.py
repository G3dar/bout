"""
BOUT GUI - Drag & Drop Video Transcription Interface.
"""
import os
import sys
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path
from datetime import datetime

# Check for drag and drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False


class BoutGUI:
    """Main GUI application for BOUT."""

    def __init__(self):
        # Create main window
        if DND_AVAILABLE:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()

        self.root.title("BOUT - Video Transcription")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Variables
        self.video_path = tk.StringVar()
        self.model_var = tk.StringVar(value="medium")
        self.diarize_var = tk.BooleanVar(value=True)
        self.is_processing = False
        self.log_queue = queue.Queue()
        self.start_time = None

        # Build UI
        self._create_widgets()

        # Start log consumer
        self._consume_log_queue()

    def _create_widgets(self):
        """Create all UI widgets."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1: Transcription
        self.tab_transcribe = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_transcribe, text="  Transcribir  ")

        # Tab 2: History
        self.tab_history = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_history, text="  Historial  ")

        # Build tabs
        self._create_transcribe_tab()
        self._create_history_tab()

    def _create_transcribe_tab(self):
        """Create transcription tab content."""
        parent = self.tab_transcribe

        # Main container
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === Header ===
        header = ttk.Label(
            main_frame,
            text="BOUT v2.0 - Transcripcion de Video",
            font=('Segoe UI', 16, 'bold')
        )
        header.pack(pady=(0, 10))

        # === Drop Zone ===
        self._create_drop_zone(main_frame)

        # === Options ===
        self._create_options(main_frame)

        # === Progress ===
        self._create_progress(main_frame)

        # === Log Area ===
        self._create_log_area(main_frame)

        # === Buttons ===
        self._create_buttons(main_frame)

    def _create_history_tab(self):
        """Create history tab content."""
        parent = self.tab_history

        main_frame = ttk.Frame(parent, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === Header with stats ===
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text="Historial de Transcripciones",
            font=('Segoe UI', 14, 'bold')
        ).pack(side=tk.LEFT)

        # Refresh button
        refresh_btn = ttk.Button(
            header_frame,
            text="Actualizar",
            command=self._refresh_history
        )
        refresh_btn.pack(side=tk.RIGHT)

        # === Stats Frame ===
        stats_frame = ttk.LabelFrame(main_frame, text="Estadisticas", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        self.stats_label = ttk.Label(stats_frame, text="Cargando...")
        self.stats_label.pack(fill=tk.X)

        # === History List ===
        list_frame = ttk.LabelFrame(main_frame, text="Transcripciones Recientes", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview for history
        columns = ("fecha", "video", "duracion", "modelo", "hablantes", "estado")
        self.history_tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show='headings',
            selectmode='browse'
        )

        # Column headings
        self.history_tree.heading("fecha", text="Fecha")
        self.history_tree.heading("video", text="Video")
        self.history_tree.heading("duracion", text="Duracion")
        self.history_tree.heading("modelo", text="Modelo")
        self.history_tree.heading("hablantes", text="Hablantes")
        self.history_tree.heading("estado", text="Estado")

        # Column widths
        self.history_tree.column("fecha", width=120, anchor='center')
        self.history_tree.column("video", width=300)
        self.history_tree.column("duracion", width=80, anchor='center')
        self.history_tree.column("modelo", width=80, anchor='center')
        self.history_tree.column("hablantes", width=80, anchor='center')
        self.history_tree.column("estado", width=80, anchor='center')

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click to open file
        self.history_tree.bind('<Double-1>', self._on_history_double_click)

        # === Buttons ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            btn_frame,
            text="Abrir Documento",
            command=self._open_selected_document
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            btn_frame,
            text="Abrir Carpeta",
            command=self._open_output_folder
        ).pack(side=tk.LEFT)

        # Load history
        self._refresh_history()

    def _create_drop_zone(self, parent):
        """Create drag & drop zone."""
        drop_frame = ttk.LabelFrame(parent, text="Video", padding="10")
        drop_frame.pack(fill=tk.X, pady=(0, 10))

        # Drop area
        self.drop_label = ttk.Label(
            drop_frame,
            text="Arrastra un video aqui\no haz clic para seleccionar",
            font=('Segoe UI', 11),
            anchor='center',
            justify='center'
        )
        self.drop_label.pack(fill=tk.X, pady=20)

        # Bind click to open file dialog
        self.drop_label.bind('<Button-1>', self._select_file)
        drop_frame.bind('<Button-1>', self._select_file)

        # Setup drag and drop if available
        if DND_AVAILABLE:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind('<<Drop>>', self._on_drop)
            drop_frame.drop_target_register(DND_FILES)
            drop_frame.dnd_bind('<<Drop>>', self._on_drop)

        # Selected file display
        self.file_label = ttk.Label(
            drop_frame,
            textvariable=self.video_path,
            font=('Segoe UI', 9),
            foreground='#0066cc'
        )
        self.file_label.pack(fill=tk.X)

    def _create_options(self, parent):
        """Create options panel."""
        options_frame = ttk.LabelFrame(parent, text="Opciones", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))

        # Grid layout
        options_inner = ttk.Frame(options_frame)
        options_inner.pack(fill=tk.X)

        # Model selection
        ttk.Label(options_inner, text="Modelo Whisper:").grid(row=0, column=0, sticky='w', padx=(0, 10))
        model_combo = ttk.Combobox(
            options_inner,
            textvariable=self.model_var,
            values=["tiny", "base", "small", "medium", "large"],
            state="readonly",
            width=15
        )
        model_combo.grid(row=0, column=1, sticky='w')

        # Model info
        ttk.Label(
            options_inner,
            text="(medium recomendado para balance velocidad/calidad)",
            font=('Segoe UI', 8),
            foreground='gray'
        ).grid(row=0, column=2, sticky='w', padx=(10, 0))

        # Diarization checkbox
        diarize_check = ttk.Checkbutton(
            options_inner,
            text="Identificar hablantes (diarization)",
            variable=self.diarize_var
        )
        diarize_check.grid(row=1, column=0, columnspan=3, sticky='w', pady=(10, 0))

    def _create_progress(self, parent):
        """Create progress section."""
        progress_frame = ttk.LabelFrame(parent, text="Progreso", padding="10")
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        # Status label
        self.status_label = ttk.Label(
            progress_frame,
            text="Esperando video...",
            font=('Segoe UI', 10)
        )
        self.status_label.pack(fill=tk.X)

        # Progress bar
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode='determinate',
            length=400
        )
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))

        # Stage label
        self.stage_label = ttk.Label(
            progress_frame,
            text="",
            font=('Segoe UI', 9),
            foreground='gray'
        )
        self.stage_label.pack(fill=tk.X, pady=(5, 0))

    def _create_log_area(self, parent):
        """Create log viewer."""
        log_frame = ttk.LabelFrame(parent, text="Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=8,
            font=('Consolas', 9),
            wrap=tk.WORD,
            state='disabled'
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _create_buttons(self, parent):
        """Create action buttons."""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X)

        # Start button
        self.start_btn = ttk.Button(
            button_frame,
            text="Iniciar Transcripcion",
            command=self._start_transcription,
            style='Accent.TButton'
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Open output folder button
        self.output_btn = ttk.Button(
            button_frame,
            text="Abrir Carpeta Output",
            command=self._open_output_folder
        )
        self.output_btn.pack(side=tk.LEFT)

        # Clear log button
        clear_btn = ttk.Button(
            button_frame,
            text="Limpiar Log",
            command=self._clear_log
        )
        clear_btn.pack(side=tk.RIGHT)

    def _refresh_history(self):
        """Refresh history list and stats."""
        try:
            from .history import get_history_manager

            manager = get_history_manager()
            entries = manager.get_all()
            stats = manager.get_stats()

            # Update stats
            stats_text = (
                f"Total: {stats['total_transcriptions']} transcripciones  |  "
                f"Duracion total: {stats['total_duration_hours']:.1f} horas  |  "
                f"Caracteres: {stats['total_characters']:,}"
            )
            self.stats_label.config(text=stats_text)

            # Clear treeview
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)

            # Add entries
            for entry in entries:
                self.history_tree.insert('', tk.END, iid=entry.id, values=(
                    entry.date_formatted,
                    entry.video_name[:40] + "..." if len(entry.video_name) > 40 else entry.video_name,
                    entry.duration_formatted,
                    entry.model,
                    entry.speakers_found if entry.diarization else "-",
                    "OK" if entry.status == "completed" else "Error"
                ))

        except Exception as e:
            self.stats_label.config(text=f"Error cargando historial: {e}")

    def _on_history_double_click(self, event):
        """Handle double-click on history item."""
        self._open_selected_document()

    def _open_selected_document(self):
        """Open the selected document from history."""
        selection = self.history_tree.selection()
        if not selection:
            return

        try:
            from .history import get_history_manager

            entry_id = selection[0]
            manager = get_history_manager()
            entry = manager.get_by_id(entry_id)

            if entry and os.path.exists(entry.output_path):
                if sys.platform == 'win32':
                    os.startfile(entry.output_path)
                elif sys.platform == 'darwin':
                    os.system(f'open "{entry.output_path}"')
                else:
                    os.system(f'xdg-open "{entry.output_path}"')
            else:
                messagebox.showerror("Error", "El archivo ya no existe")

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo: {e}")

    def _select_file(self, event=None):
        """Open file dialog to select video."""
        if self.is_processing:
            return

        filetypes = [
            ("Video files", "*.mp4 *.avi *.mkv *.mov *.wmv *.webm *.m4v *.flv"),
            ("All files", "*.*")
        ]

        filepath = filedialog.askopenfilename(
            title="Seleccionar video",
            filetypes=filetypes
        )

        if filepath:
            self._set_video(filepath)

    def _on_drop(self, event):
        """Handle file drop."""
        if self.is_processing:
            return

        # Parse dropped file path
        filepath = event.data

        # Handle paths with spaces (wrapped in {})
        if filepath.startswith('{') and filepath.endswith('}'):
            filepath = filepath[1:-1]

        # Handle multiple files - take first one
        if ' ' in filepath and not os.path.exists(filepath):
            filepath = filepath.split()[0]

        if os.path.exists(filepath):
            self._set_video(filepath)

    def _set_video(self, filepath):
        """Set the video path."""
        self.video_path.set(filepath)
        filename = os.path.basename(filepath)
        self.drop_label.config(text=f"Video seleccionado:\n{filename}")
        self._log(f"Video seleccionado: {filename}")

    def _start_transcription(self):
        """Start the transcription process."""
        if not self.video_path.get():
            self._log("ERROR: No hay video seleccionado", error=True)
            return

        if self.is_processing:
            return

        self.is_processing = True
        self.start_btn.config(state='disabled')
        self.progress_bar['value'] = 0
        self.start_time = time.time()

        # Start transcription in separate thread
        thread = threading.Thread(target=self._run_transcription, daemon=True)
        thread.start()

    def _run_transcription(self):
        """Run transcription (in separate thread)."""
        video_path = self.video_path.get()
        model = self.model_var.get()
        diarize = self.diarize_var.get()
        output_path = None
        duration = 0
        speakers_found = 0
        segments_count = 0
        characters_count = 0
        status = "failed"
        error_msg = None

        try:
            self._update_status("Iniciando transcripcion...")
            self._log(f"Procesando: {os.path.basename(video_path)}")
            self._log(f"Modelo: {model}, Diarization: {'Si' if diarize else 'No'}")

            # Import here to avoid slow startup
            from .core.config import get_config
            from .pipeline.orchestrator import Orchestrator
            from .audio import get_video_duration

            # Setup config
            config = get_config()
            config.ensure_directories()
            config.whisper.model = model

            # Get duration
            duration = get_video_duration(Path(video_path))
            self._log(f"Duracion del video: {duration/60:.1f} minutos")

            # Progress stages
            stages = [
                (10, "Extrayendo audio..."),
                (15, "Dividiendo en chunks..."),
                (75, "Transcribiendo..."),
                (85, "Uniendo transcripciones..."),
                (95, "Identificando hablantes..." if diarize else "Finalizando..."),
                (100, "Generando documento...")
            ]

            stage_idx = [0]

            def progress_callback(stage_name):
                if stage_idx[0] < len(stages):
                    progress, msg = stages[stage_idx[0]]
                    self._update_progress(progress)
                    self._update_stage(msg)
                    self._log(msg)
                    stage_idx[0] += 1

            # Create orchestrator
            orchestrator = Orchestrator(config, use_diarization=diarize)

            # Process
            self._update_progress(5)
            self._update_stage("Extrayendo audio...")
            self._log("Extrayendo audio...")

            output_path = orchestrator.process(Path(video_path))

            if output_path:
                # Get stats from job
                job = orchestrator.state_manager.get_job(
                    list(orchestrator.state_manager.get_all_jobs())[0].id if orchestrator.state_manager.get_all_jobs() else None
                )

                if job:
                    segments_count = len(job.segments)
                    characters_count = len(job.transcription_text or "")
                    # Count unique speakers
                    speakers = set(s.speaker for s in job.segments if s.speaker)
                    speakers_found = len(speakers)

                status = "completed"
                self._update_status("Completado!")
                self._update_progress(100)
                self._log(f"Archivo guardado: {output_path}")
                self._log("=" * 50)
                self._log("TRANSCRIPCION COMPLETADA EXITOSAMENTE")
                self._log("=" * 50)

                # Show completion message
                self.root.after(0, lambda: self._show_completion(str(output_path)))
            else:
                self._update_status("Error en la transcripcion")
                self._log("ERROR: La transcripcion fallo", error=True)
                error_msg = "Transcription returned None"

        except Exception as e:
            self._update_status("Error")
            self._log(f"ERROR: {str(e)}", error=True)
            error_msg = str(e)
            import traceback
            self._log(traceback.format_exc(), error=True)

        finally:
            # Save to history
            processing_time = time.time() - self.start_time if self.start_time else 0

            try:
                from .history import get_history_manager
                manager = get_history_manager()
                manager.add_entry(
                    video_name=os.path.basename(video_path),
                    video_path=video_path,
                    output_path=str(output_path) if output_path else "",
                    duration_seconds=duration,
                    model=model,
                    diarization=diarize,
                    speakers_found=speakers_found,
                    segments_count=segments_count,
                    characters_count=characters_count,
                    processing_time_seconds=processing_time,
                    status=status,
                    error=error_msg,
                )
                # Refresh history tab
                self.root.after(0, self._refresh_history)
            except Exception as e:
                self._log(f"Warning: Could not save to history: {e}")

            self.is_processing = False
            self.root.after(0, lambda: self.start_btn.config(state='normal'))

    def _show_completion(self, output_path):
        """Show completion dialog."""
        result = messagebox.askyesno(
            "Transcripcion Completada",
            f"El archivo se guardo en:\n{output_path}\n\n¿Deseas abrir el documento?"
        )
        if result:
            if sys.platform == 'win32':
                os.startfile(output_path)
            elif sys.platform == 'darwin':
                os.system(f'open "{output_path}"')
            else:
                os.system(f'xdg-open "{output_path}"')

    def _open_output_folder(self):
        """Open the output folder in file explorer."""
        try:
            from .core.config import get_config
            config = get_config()
            output_dir = config.output_dir

            if not output_dir.exists():
                output_dir.mkdir(parents=True, exist_ok=True)

            if sys.platform == 'win32':
                os.startfile(str(output_dir))
            elif sys.platform == 'darwin':
                os.system(f'open "{output_dir}"')
            else:
                os.system(f'xdg-open "{output_dir}"')
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta: {e}")

    def _clear_log(self):
        """Clear the log area."""
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')

    def _log(self, message, error=False):
        """Add message to log queue."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put((f"[{timestamp}] {message}", error))

    def _consume_log_queue(self):
        """Consume log messages from queue (runs in main thread)."""
        try:
            while True:
                message, error = self.log_queue.get_nowait()
                self.log_text.config(state='normal')
                if error:
                    self.log_text.insert(tk.END, message + "\n", 'error')
                    self.log_text.tag_config('error', foreground='red')
                else:
                    self.log_text.insert(tk.END, message + "\n")
                self.log_text.see(tk.END)
                self.log_text.config(state='disabled')
        except queue.Empty:
            pass

        # Schedule next check
        self.root.after(100, self._consume_log_queue)

    def _update_status(self, text):
        """Update status label (thread-safe)."""
        self.root.after(0, lambda: self.status_label.config(text=text))

    def _update_stage(self, text):
        """Update stage label (thread-safe)."""
        self.root.after(0, lambda: self.stage_label.config(text=text))

    def _update_progress(self, value):
        """Update progress bar (thread-safe)."""
        self.root.after(0, lambda: self.progress_bar.configure(value=value))

    def run(self):
        """Start the GUI application."""
        self._log("BOUT GUI iniciado")
        if not DND_AVAILABLE:
            self._log("NOTA: Drag & drop no disponible. Instala tkinterdnd2 para habilitarlo.")
            self._log("Puedes hacer clic para seleccionar archivos.")
        self.root.mainloop()


def main():
    """Entry point for GUI."""
    app = BoutGUI()
    app.run()


if __name__ == "__main__":
    main()
