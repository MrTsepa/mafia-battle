"""
Run recorder that saves game events to files.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from threading import Lock


class RunRecorder:
    """Records game events to files in a run directory."""
    
    def __init__(self, runs_dir: str = "runs"):
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(exist_ok=True)
        self.current_run_dir: Optional[Path] = None
        self.events_file: Optional[Path] = None
        self.metadata_file: Optional[Path] = None
        self._lock = Lock()
        self._event_count = 0
    
    def create_run(self, run_name: Optional[str] = None) -> str:
        """
        Create a new run directory.
        
        Args:
            run_name: Optional custom run name. If None, generates timestamp-based name.
            
        Returns:
            The run name (directory name)
        """
        if run_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_name = f"run_{timestamp}"
        
        self.current_run_dir = self.runs_dir / run_name
        self.current_run_dir.mkdir(exist_ok=True)
        
        self.events_file = self.current_run_dir / "events.jsonl"
        self.metadata_file = self.current_run_dir / "metadata.json"
        self._event_count = 0
        
        return run_name
    
    def record_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Record an event to the events file (JSONL format).
        
        Args:
            event_type: Type of event
            data: Event data
        """
        if not self.events_file:
            return
        
        with self._lock:
            event = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "data": data,
                "sequence": self._event_count
            }
            self._event_count += 1
            
            with open(self.events_file, 'a') as f:
                f.write(json.dumps(event) + '\n')
    
    def save_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Save run metadata to metadata.json.
        
        Args:
            metadata: Metadata dictionary
        """
        if not self.metadata_file:
            return
        
        with self._lock:
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
    
    def get_run_path(self) -> Optional[Path]:
        """Get the current run directory path."""
        return self.current_run_dir
    
    def list_runs(self) -> list[Dict[str, Any]]:
        """
        List all available runs.
        
        Returns:
            List of run info dictionaries
        """
        runs = []
        if not self.runs_dir.exists():
            return runs
        
        for run_dir in sorted(self.runs_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            
            metadata_file = run_dir / "metadata.json"
            events_file = run_dir / "events.jsonl"
            
            run_info = {
                "name": run_dir.name,
                "path": str(run_dir),
                "has_metadata": metadata_file.exists(),
                "has_events": events_file.exists(),
            }
            
            # Try to load metadata
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        run_info["metadata"] = json.load(f)
                except:
                    pass
            
            # Count events
            if events_file.exists():
                try:
                    with open(events_file, 'r') as f:
                        run_info["event_count"] = sum(1 for _ in f)
                except:
                    run_info["event_count"] = 0
            
            runs.append(run_info)
        
        return runs

