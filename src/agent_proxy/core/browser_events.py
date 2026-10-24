"""Bounded observations of browser events, with explicit completion states.

An event's action_id is a time association, not proof that an action caused it.
Downloads stay pending until save_as and hashing have both finished.
"""
import asyncio
import hashlib
import os
import re
import time
import uuid
from collections import deque
from pathlib import Path


class BrowserEvents:
    MAX_EVENTS = 200
    MAX_DOWNLOADS = 100

    def __init__(self, download_dir):
        self._download_dir = download_dir
        self.events = deque(maxlen=self.MAX_EVENTS)
        self.downloads = deque(maxlen=self.MAX_DOWNLOADS)
        self.dialogs = {}
        self.download_tasks = set()
        self._waiters = set()
        self._sequence = 0
        self.action_id = None

    def record(self, kind, **details):
        self._sequence += 1
        entry = {"sequence": self._sequence, "timestamp": time.time(), "kind": kind,
                 "observed_during_action": self.action_id, **details}
        self.events.append(entry)
        return entry

    def timeline(self, limit=50):
        if not isinstance(limit, int) or not 1 <= limit <= self.MAX_EVENTS:
            raise ValueError(f"limit must be between 1 and {self.MAX_EVENTS}")
        return [dict(item) for item in list(self.events)[-limit:]]

    def pending_dialogs(self, tab_id=None):
        return [dict(info) for _, info in self.dialogs.values()
                if tab_id is None or info["tab_id"] == tab_id]

    def dialog_waiter(self, tab_id):
        future = asyncio.get_running_loop().create_future()
        pair = (tab_id, future)
        self._waiters.add(pair)
        future.add_done_callback(lambda _: self._waiters.discard(pair))
        return future

    def on_dialog(self, dialog, tab_id):
        dialog_id = "dialog_" + uuid.uuid4().hex[:12]
        info = {"id": dialog_id, "tab_id": tab_id, "type": dialog.type,
                "message": dialog.message, "default_value": dialog.default_value,
                "status": "pending"}
        self.dialogs[dialog_id] = (dialog, info)
        self.record("dialog", **info)
        for wanted_tab, future in tuple(self._waiters):
            if wanted_tab == tab_id and not future.done():
                future.set_result(dict(info))

    async def handle_dialog(self, accept, prompt_text=None, tab_id=None):
        pending = self.pending_dialogs(tab_id)
        if not pending:
            raise RuntimeError("No pending dialog on the active tab")
        dialog_id = pending[0]["id"]
        dialog, info = self.dialogs[dialog_id]
        if prompt_text is not None and (not accept or info["type"] != "prompt"):
            raise ValueError("prompt_text is only valid when accepting a prompt dialog")
        if accept:
            await dialog.accept(prompt_text=prompt_text)
        else:
            await dialog.dismiss()
        self.dialogs.pop(dialog_id, None)
        result = {**info, "status": "accepted" if accept else "dismissed"}
        self.record("dialog_resolved", **result)
        return result

    def drop_tab_dialogs(self, tab_id):
        for dialog_id, (_, info) in list(self.dialogs.items()):
            if info["tab_id"] == tab_id:
                self.dialogs.pop(dialog_id, None)
                self.record("dialog_closed", **{**info, "status": "page_closed"})

    def on_download(self, download, tab_id):
        entry = {"id": "download_" + uuid.uuid4().hex[:12], "tab_id": tab_id,
                 "url": download.url, "filename": download.suggested_filename,
                 "status": "pending", "timestamp": time.time()}
        self.downloads.append(entry)
        self.record("download", **entry)
        task = asyncio.create_task(self._save_download(download, entry))
        self.download_tasks.add(task)
        task.add_done_callback(self.download_tasks.discard)

    @staticmethod
    def _file_metadata(path):
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return os.path.getsize(path), digest.hexdigest()

    async def _save_download(self, download, entry):
        try:
            directory = self._download_dir()
            if not directory:
                raise RuntimeError("No download directory configured for this session")
            directory = Path(directory).resolve()
            directory.mkdir(parents=True, exist_ok=True)
            # suggested_filename is remote input; never allow path components,
            # Windows device names, alternate streams or duplicate-file overwrites.
            name = re.sub(r'[^\w. -]', "_", entry["filename"]).strip(" .")[:140] or "download"
            destination = directory / f"{entry['id']}_{name}"
            entry["saved_path"] = str(destination)
            await download.save_as(str(destination))
            failure = await download.failure()
            if failure:
                raise RuntimeError(str(failure))
            size, digest = await asyncio.to_thread(self._file_metadata, destination)
            entry.update(status="completed", size=size, sha256=digest)
        except asyncio.CancelledError:
            entry.update(status="cancelled", error="Session closed before download completed")
            raise
        except Exception as exc:
            entry.update(status="failed", error=str(exc))
        finally:
            self.record("download_updated", **entry)

    def get_downloads(self):
        return [dict(item) for item in self.downloads]

    async def stop(self):
        tasks = list(self.download_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for _, future in tuple(self._waiters):
            future.cancel()
        self.dialogs.clear()
