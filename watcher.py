import logging
import signal
import threading
from pathlib import Path
import os

from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver
import pipeline

logger = logging.getLogger(__name__)


class PDFHandler(FileSystemEventHandler):

    def _handle(self, src_path: str) -> None:
        path = Path(src_path)
        # Only process ori_*.pdf files
        if path.suffix.lower() != ".pdf" or not path.name.startswith("ori_"):
            return
        
        output_path = pipeline.derive_output_path(path)
        logger.info("New PDF detected, translating: %s -> %s", path.name, output_path.name)
        threading.Thread(target=pipeline.main, args=(str(path), str(output_path)), daemon=True).start()
    

    def on_created(self, event: FileCreatedEvent) -> None:
        self._handle(event.src_path)
    

    def on_modified(self, event: FileModifiedEvent) -> None:
        self._handle(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        self._handle(event.dest_path)


def _preflight() -> None:
    """Verify required secrets are available before starting the watch loop."""
    missing = [k for k in ("ANTHROPIC_API_KEY", "DEEPL_API_KEY") if not os.getenv(k)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")


def start(folder: str) -> None:
    _preflight()

    watch_path = Path(folder).expanduser()
    if not watch_path.is_dir():
        raise ValueError(f"Watch folder does not exist: {watch_path}")
    
    handler = PDFHandler()
    observer = PollingObserver()
    observer.schedule(handler, str(watch_path), recursive=True)
    logger.info("Watching for PDFs: %s", watch_path)
    observer.start()

    signal.signal(signal.SIGTERM, lambda s, f: observer.stop())
    try:
        observer.join()
    except KeyboardInterrupt:
        observer.stop()
