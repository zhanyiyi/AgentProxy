import asyncio
import json
import logging
import os
import socket
import time
import uuid
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Optional

import anyio

from .mitm_controller import MitmController
from .browser_controller import BrowserController
from .workflow_state import CheckpointStore
from ..models import SessionConfig
from ..config import RuleConfig, load_rule_config

logger = logging.getLogger("agent_proxy.session")


class SessionManager:
    def __init__(self, config: Optional[SessionConfig] = None,
                 rule_config: Optional[RuleConfig] = None,
                 user_config_path: Optional[str] = None):
        self.config = config or SessionConfig()
        self.session_id = uuid.uuid4().hex
        if self.config.db_path is None:
            db_path = Path.cwd() / ".agentproxy" / "sessions" / self.session_id / "traffic.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.config = self.config.model_copy(update={"db_path": str(db_path)})
        elif self.config.db_path != ":memory:":
            db_path = Path(self.config.db_path).expanduser().resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.config = self.config.model_copy(update={"db_path": str(db_path)})
        # Rule pack: explicit > path-loaded > bundled defaults.
        if rule_config is not None:
            self.rules = rule_config
        else:
            self.rules = load_rule_config(user_config_path)
        self.mitm = MitmController(db_path=self.config.db_path, rules=self.rules)
        self.browser = BrowserController(
            proxy_host=self.config.proxy_host,
            proxy_port=self.config.proxy_port,
            headless=self.config.headless,
            ignore_https_errors=self.config.ignore_https_errors,
            timeout=self.config.browser_timeout,
            profile_dir=self.config.profile_dir,
            unsafe_disable_web_security=self.config.unsafe_disable_web_security,
        )
        self._session_active = False
        self._last_mitm_error: Optional[str] = None
        self._lifecycle_lock = asyncio.Lock()
        self.state = "idle"
        self._cleanup_error: Optional[str] = None
        self.browser.download_dir = str(Path(self.config.db_path).parent / "downloads")
        self.browser.shutdown_timeout = self.config.shutdown_timeout
        self._workflow_lock = asyncio.Lock()
        self._checkpoints: Optional[CheckpointStore] = None

    @property
    def checkpoints(self) -> CheckpointStore:
        # Construct once per manager: opening a persisted cursor reconciles an
        # old process's in-flight step, not the current process's running step.
        if self._checkpoints is None:
            self._checkpoints = CheckpointStore(self.mitm.db)
        return self._checkpoints

    async def _cursor(self, method: str, *args, **kwargs):
        # These short transactions are part of the workflow lock's lifetime.
        # AnyIO waits for its worker on cancellation instead of abandoning a
        # write that could otherwise overwrite the next step after lock release.
        return await anyio.to_thread.run_sync(partial(getattr(self.checkpoints, method), *args, **kwargs))

    def _active_browser_page(self) -> Optional[Dict[str, Any]]:
        return next((tab for tab in self.browser.list_tabs() if tab["active"]), None)

    async def _remember_browser_page(self, *, status: Optional[str] = None) -> Optional[Dict[str, Any]]:
        page = self._active_browser_page()
        if page is None:
            return None
        return await self._cursor(
            "observe", {**page, "instance_id": self.session_id},
            context=self.browser.active, status=status,
        )

    async def remember_browser_page(self, *, status: Optional[str] = None):
        async with self._workflow_lock:
            return await self._remember_browser_page(status=status)

    async def _restore_browser_position(self, context: str) -> Dict[str, Any]:
        """Rebind a live page locally; never open URLs or replay a browser step."""
        checkpoint = await self._cursor("latest", context)
        tabs = [tab for tab in self.browser.list_tabs() if tab["context"] == context]
        active = next((tab for tab in tabs if tab["active"]), None)
        page = None
        if checkpoint is None:
            page = active
        elif checkpoint.get("instance_id") == self.session_id:
            # A tab can navigate after a primitive returns. Its local identity
            # remains valid, but tab IDs are never trusted across processes.
            page = next((tab for tab in tabs if tab["tab_id"] == checkpoint["tab_id"]), None)
        if page is None and checkpoint and checkpoint.get("url"):
            matches = [tab for tab in tabs if tab["url"] == checkpoint["url"]]
            if len(matches) == 1:
                page = matches[0]
        if page is None:
            return {"status": "resume_required", "checkpoint": checkpoint,
                    "actions_replayed": 0,
                    "next_step": "Open or select the saved page, then inspect it before acknowledging the checkpoint."}
        rebound = (active is None or active["tab_id"] != page["tab_id"] or
                   bool(checkpoint and (checkpoint.get("tab_id") != page["tab_id"] or
                                        checkpoint.get("instance_id") != self.session_id)))
        if rebound:
            page = await self.browser.select_tab(page["tab_id"])
        status = checkpoint.get("status") if checkpoint else "ready"
        if status not in ("needs_review", "requires_dialog", "inflight"):
            status = "restored" if rebound else "ready"
        return {"status": status, "page": page, "checkpoint": checkpoint,
                "actions_replayed": 0, "rebound": rebound}

    async def observe_browser(self, frame: Optional[str] = None, incremental: bool = True) -> Dict[str, Any]:
        async with self._workflow_lock:
            recovery = await self._restore_browser_position(self.browser.active)
            if recovery["status"] == "resume_required":
                return recovery
            snapshot = await self.browser.snapshot(frame=frame, incremental=incremental)
            snapshot["checkpoint"] = await self._remember_browser_page()
            snapshot["recovery"] = recovery
            return snapshot

    async def navigate_browser(self, url: str, wait_until: str = "domcontentloaded") -> str:
        async with self._workflow_lock:
            context = self.browser.active
            cursor = await self._cursor("latest", context)
            unresolved = bool(cursor and cursor["status"] in ("needs_review", "inflight"))
            await self._remember_browser_page()
            if not unresolved:
                await self._cursor("begin", {"action": "navigate", "target": url}, context=context)
            started = time.monotonic()
            try:
                result = await self.browser.navigate(url, wait_until=wait_until)
                try:
                    navigation = json.loads(result)
                except json.JSONDecodeError:
                    raise RuntimeError(result) from None
            except BaseException as exc:
                with anyio.CancelScope(shield=True):
                    await self._cursor("interrupted", type(exc).__name__, context=context)
                raise
            page = {**(self._active_browser_page() or {}), "title": navigation.get("title")}
            receipt = {"id": "action_" + uuid.uuid4().hex, "timestamp": time.time(),
                       "context": context, "action": "navigate", "target": url,
                       "elapsed_ms": round((time.monotonic() - started) * 1000),
                       "status": "completed", "action_status": "completed",
                       "completion_scope": "browser_primitive", "page": page, "result": navigation}
            # Explicit navigation may be needed to inspect a restarted page.
            # It must not resolve the preceding unknown business operation.
            receipt["checkpoint"] = (await self._remember_browser_page() if unresolved
                                     else await self._cursor("finish", receipt))
            await asyncio.to_thread(self.mitm.db.save_action, receipt)
            return json.dumps({**navigation, "checkpoint": receipt["checkpoint"]})

    async def act_browser(self, action: str, *, selector: Optional[str] = None,
                          value: Optional[str] = None, frame: Optional[str] = None,
                          delay: int = 50, ref: Optional[str] = None,
                          snapshot_id: Optional[str] = None) -> Dict[str, Any]:
        async with self._workflow_lock:
            context = self.browser.active
            recovery = await self._restore_browser_position(context)
            if recovery["status"] in ("resume_required", "needs_review", "inflight"):
                return {**recovery, "action_status": "not_started"}
            await self._remember_browser_page()
            await self._cursor("begin", {"action": action, "selector": selector, "ref": ref, "frame": frame},
                               context=context)
            try:
                receipt = await self.browser.act(action, selector=selector, value=value, frame=frame,
                                                 delay=delay, ref=ref, snapshot_id=snapshot_id)
            except ValueError:
                # Parameter and ref validation happens before the primitive is
                # started. Rejecting a stale observation is a known non-action,
                # so refreshing the snapshot does not need recovery approval.
                rejected = {"id": "action_" + uuid.uuid4().hex, "context": context,
                            "action": action, "target": ref or selector,
                            "status": "not_started", "action_status": "not_started"}
                await self._cursor("finish", rejected)
                await asyncio.to_thread(self.mitm.db.save_action, rejected)
                raise
            except BaseException as exc:
                # The intent was committed before execution. Preserve unknown
                # results and omit Playwright logs that can contain typed values.
                with anyio.CancelScope(shield=True):
                    await self._cursor("interrupted", type(exc).__name__, context=context)
                raise
            receipt["checkpoint"] = await self._cursor("finish", receipt)
            await asyncio.to_thread(self.mitm.db.save_action, receipt)
            return receipt

    async def checkpoint_browser(self, operation: str = "inspect", context: Optional[str] = None) -> Dict[str, Any]:
        if operation not in ("inspect", "save", "restore", "acknowledge"):
            raise ValueError("operation must be inspect, save, restore, or acknowledge")
        async with self._workflow_lock:
            context = context or self.browser.active
            if operation == "inspect":
                return {"checkpoint": await self._cursor("latest", context)}
            if operation == "save":
                if context != self.browser.active or self._active_browser_page() is None:
                    raise RuntimeError("Select an open page before saving its checkpoint")
                return {"checkpoint": await self._remember_browser_page()}
            recovery = await self._restore_browser_position(context)
            if operation == "acknowledge" and recovery["status"] != "resume_required":
                # Acknowledgement selects where a new step may begin. It does
                # not change the previous action's unknown/pending outcome.
                recovery["checkpoint"] = await self._remember_browser_page(status="ready")
                recovery["status"] = "ready"
            return recovery

    async def clear_capture(self) -> None:
        async with self._workflow_lock:
            await self._cursor("reset")
            await asyncio.to_thread(self.mitm.db.clear)

    async def change_browser_tab(self, operation: str, tab_id: str) -> Dict[str, Any]:
        async with self._workflow_lock:
            if operation == "select":
                result = await self.browser.select_tab(tab_id)
            else:
                result = await self.browser.close_tab(tab_id)
            await self._remember_browser_page()
            return result

    async def change_browser_context(self, name: str) -> str:
        async with self._workflow_lock:
            result = self.browser.use_context(name)
            await self._remember_browser_page()
            return result

    async def resolve_browser_dialog(self, accept: bool, prompt_text: Optional[str] = None) -> Dict[str, Any]:
        async with self._workflow_lock:
            result = await self.browser.handle_dialog(accept, prompt_text=prompt_text)
            await self._remember_browser_page(status="ready")
            return result

    async def _stop_resources(self, stop_proxy: bool) -> Dict[str, str]:
        # Both cleanup branches run even if one resource refuses to close.
        operations = [self.browser.stop()]
        if stop_proxy:
            operations.append(self.mitm.stop(timeout=self.config.shutdown_timeout))
        results = await asyncio.gather(*operations, return_exceptions=True)
        errors = []
        for result in results:
            if isinstance(result, BaseException):
                errors.append(str(result) or type(result).__name__)
                logger.error("session cleanup failed", exc_info=(type(result), result, result.__traceback__))
        if errors:
            raise RuntimeError("; ".join(errors))
        return {"browser": results[0], "proxy": results[1] if stop_proxy else "Proxy retained"}

    async def _cleanup(self, stop_proxy: bool = True) -> Dict[str, str]:
        """Give cleanup its own deadline and finish it before releasing the lock.

        Shielding keeps a cancelled MCP call from abandoning acquired handles.
        The original cancellation still reaches the caller after cleanup.
        """
        self._cleanup_error = None
        task = asyncio.create_task(asyncio.wait_for(
            self._stop_resources(stop_proxy), timeout=self.config.shutdown_timeout))
        cancelled = False
        try:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    # More than one cancellation can arrive while cleanup is
                    # running. Keep the lifecycle lock until the bounded task
                    # finishes, then propagate cancellation to the caller.
                    cancelled = True
            result = task.result()
        except Exception as e:
            self._cleanup_error = str(e) or type(e).__name__
            logger.exception("session cleanup failed")
            if cancelled:
                raise asyncio.CancelledError() from e
            raise
        if cancelled:
            raise asyncio.CancelledError()
        return result

    async def _run_start(self, operation, *, keep_proxy: bool = False) -> str:
        async with self._lifecycle_lock:
            if self.state == "active" and not self.mitm.running:
                self.state = "failed"
                self._session_active = False
            if self.state == "failed" and not keep_proxy and not self._cleanup_error:
                # A background proxy failure can leave a live browser and
                # writer behind. Reconcile them before allocating replacements.
                await self._cleanup()
            if not keep_proxy and self._session_active:
                return "Session already active. Use session_stop first."
            if self._cleanup_error:
                raise RuntimeError("Previous cleanup failed; call session_stop before restarting: " + self._cleanup_error)
            self.state = "starting"
            logger.info("session_starting id=%s keep_proxy=%s", self.session_id, keep_proxy)
            try:
                result = await asyncio.wait_for(operation(), timeout=self.config.startup_timeout)
            except BaseException:
                try:
                    await self._cleanup(stop_proxy=not keep_proxy)
                except asyncio.CancelledError:
                    # _cleanup finishes its bounded task before propagating a
                    # later cancellation. Preserve the original startup error.
                    pass
                except Exception:
                    # _cleanup records its failure; preserve the startup error.
                    logger.exception("cleanup after startup failure did not complete")
                finally:
                    self.state = "failed" if self._cleanup_error else ("active" if keep_proxy and self.mitm.running else "idle")
                    self._session_active = bool(keep_proxy and self.mitm.running)
                raise
            self.state = "active" if self._session_active else "idle"
            return result

    async def _safe_mitm_start(self, port: int) -> Optional[str]:
        """Try to start the mitm proxy. Returns the success string on bind,
        or None on failure (caller renders an error payload). Centralised so
        all three session entry points report port-conflict errors the same
        way."""
        try:
            return await self.mitm.start(port=port, host=self.config.proxy_host)
        except Exception as e:
            logger.error("mitm proxy start failed on port %s: %s", port, e)
            self._last_mitm_error = str(e)
            return None

    def _mitm_start_error_payload(self, port: int, mode: str) -> str:
        return json.dumps({
            "status": "error",
            "mode": mode,
            "error": self._last_mitm_error or "mitmproxy failed to start",
            "proxy_port": port,
            "hint": (
                f"Check whether something else is bound to "
                f"{self.config.proxy_host}:{port} "
                f"(`ss -ltnp 'sport = :{port}'`) or pick a different port."
            ),
        })

    async def start_session(self, proxy_port: Optional[int] = None, headless: Optional[bool] = None, profile_dir: Optional[str] = None, unsafe_disable_web_security: Optional[bool] = None) -> str:
        return await self._run_start(lambda: self._start_session(
            proxy_port, headless, profile_dir, unsafe_disable_web_security))

    async def _start_session(self, proxy_port, headless, profile_dir, unsafe_disable_web_security) -> str:
        if self._session_active:
            return "Session already active. Use session_stop first."

        port = proxy_port or self.config.proxy_port
        hl = headless if headless is not None else self.config.headless

        self.mitm.port = port
        self.browser.proxy_port = port
        self.browser.headless = hl
        if profile_dir is not None:
            self.browser.profile_dir = profile_dir or None
        if unsafe_disable_web_security is not None:
            self.browser.unsafe_disable_web_security = unsafe_disable_web_security

        proxy_result = await self._safe_mitm_start(port)
        if proxy_result is None:
            return self._mitm_start_error_payload(port, mode="full")
        logger.info("Proxy started: %s", proxy_result)

        browser_result = await self.browser.start()
        logger.info("Browser started: %s", browser_result)

        self._session_active = True
        return json.dumps({
            "status": "session_started",
            "proxy": proxy_result,
            "browser": browser_result,
            "proxy_port": port,
            "headless": hl,
            "profile_dir": self.browser.profile_dir,
            "contexts": self.browser.list_contexts(),
            "active_context": self.browser.active,
            "unsafe_disable_web_security": self.browser.unsafe_disable_web_security,
        })

    async def connect_cdp_session(self, endpoint_url: str = "http://127.0.0.1:9222", proxy_port: Optional[int] = None) -> str:
        return await self._run_start(lambda: self._connect_cdp_session(endpoint_url, proxy_port))

    async def _connect_cdp_session(self, endpoint_url, proxy_port) -> str:
        if self._session_active:
            return "Session already active. Use session_stop first."

        port = proxy_port or self.config.proxy_port
        self.mitm.port = port
        self.browser.proxy_port = port

        proxy_result = await self._safe_mitm_start(port)
        if proxy_result is None:
            return self._mitm_start_error_payload(port, mode="cdp")
        logger.info("Proxy started: %s", proxy_result)

        browser_result = await self.browser.connect_cdp(endpoint_url=endpoint_url)
        logger.info("Browser connected over CDP: %s", browser_result)

        self._session_active = True
        return json.dumps({
            "status": "session_started",
            "mode": "cdp",
            "proxy": proxy_result,
            "browser": browser_result,
            "proxy_port": port,
            "cdp_endpoint": endpoint_url,
        })

    async def start_mitm_only(self, proxy_port: Optional[int] = None) -> str:
        """Start only the mitmproxy listener — no Playwright browser, no CDP.
        For passive capture from external clients (system Chrome/Firefox, mobile
        device, curl, scripts) that point their HTTP(S) proxy at us. The agent
        keeps full read-only access to traffic via traffic_*/site_map/findings.

        browser_*/browse_and_capture/traffic_replay_via_browser will fail (no
        live page); traffic_replay (curl_cffi) still works."""
        return await self._run_start(lambda: self._start_mitm_only(proxy_port))

    async def _start_mitm_only(self, proxy_port) -> str:
        if self._session_active:
            return "Session already active. Use session_stop first."

        port = proxy_port or self.config.proxy_port
        self.mitm.port = port

        proxy_result = await self._safe_mitm_start(port)
        if proxy_result is None:
            return self._mitm_start_error_payload(port, mode="mitm_only")
        logger.info("Proxy started (browser-less): %s", proxy_result)
        self._session_active = True

        return json.dumps({
            "status": "session_started",
            "mode": "mitm_only",
            "proxy": proxy_result,
            "proxy_port": port,
            "proxy_host": self.config.proxy_host,
            "hint": (
                f"Point browsers / curl / mobile devices at "
                f"http://{self.config.proxy_host}:{port}. For HTTPS, install "
                f"~/.mitmproxy/mitmproxy-ca-cert.pem (see README "
                f"'HTTPS pages load but the address bar shows Not Secure')."
            ),
        })

    async def attach_browser(
        self,
        headless: Optional[bool] = None,
        profile_dir: Optional[str] = None,
        unsafe_disable_web_security: Optional[bool] = None,
        hydrate_host: Optional[str] = None,
    ) -> str:
        """Hot-attach a Playwright browser to an existing mitm-only session.
        The mitm proxy is reused at its current port (no restart, no flow
        loss). Required state: mitm running, browser NOT running.

        Use it to upgrade a passive capture session into an active one
        without losing the flows you've already collected — common when
        you started with the external browser logged in and now want the
        agent to drive a context against the same target.

        Args:
            headless / profile_dir / unsafe_disable_web_security: same
                semantics as session_start; default to the SessionConfig
                values.
            hydrate_host: optional shortcut — after the browser starts,
                hydrate the default context with cookies + auth headers
                from the traffic DB for this host. Equivalent to calling
                browser_hydrate_from_traffic afterwards."""
        return await self._run_start(lambda: self._attach_browser(
            headless, profile_dir, unsafe_disable_web_security, hydrate_host), keep_proxy=True)

    async def _attach_browser(self, headless, profile_dir, unsafe_disable_web_security, hydrate_host) -> str:
        if not self._session_active or not self.mitm.running:
            return json.dumps({
                "status": "error",
                "error": (
                    "No active mitm session to attach to. Call "
                    "session_start_proxy_only first, or use session_start "
                    "to do both at once."
                ),
            })
        if self.browser.running:
            return json.dumps({
                "status": "error",
                "error": (
                    "Browser is already running. Use session_stop and a "
                    "fresh session_start if you need to reconfigure it."
                ),
            })

        # Reuse the live mitm port (do NOT restart the proxy).
        self.browser.proxy_port = self.mitm.port
        if headless is not None:
            self.browser.headless = headless
        if profile_dir is not None:
            self.browser.profile_dir = profile_dir or None
        if unsafe_disable_web_security is not None:
            self.browser.unsafe_disable_web_security = unsafe_disable_web_security

        try:
            browser_result = await self.browser.start()
            logger.info("Browser attached: %s", browser_result)
        except Exception as e:
            # Don't drop the mitm — caller can still use it passively.
            await self._cleanup(stop_proxy=False)
            return json.dumps({
                "status": "error",
                "error": f"browser failed to start: {e}",
                "mitm_still_running": True,
            })

        result: Dict[str, Any] = {
            "status": "browser_attached",
            "browser": browser_result,
            "proxy_port": self.mitm.port,
            "headless": self.browser.headless,
            "profile_dir": self.browser.profile_dir,
            "contexts": self.browser.list_contexts(),
            "active_context": self.browser.active,
        }
        if hydrate_host:
            hydrate_raw = await self.hydrate_browser_from_traffic(host=hydrate_host)
            result["hydrate"] = json.loads(hydrate_raw)
        return json.dumps(result, indent=2)

    async def stop_session(self) -> str:
        async with self._lifecycle_lock:
            self.state = "stopping"
            logger.info("session_stopping id=%s", self.session_id)
            try:
                results = await self._cleanup()
            except BaseException:
                self.state = "failed" if self._cleanup_error else "idle"
                self._session_active = False
                raise
            self._session_active = False
            self.state = "idle"
            return json.dumps({"status": "session_stopped", **results})

    async def browse_and_capture(self, url: str, wait_until: str = "domcontentloaded", actions: Optional[List[Dict]] = None) -> str:
        if not self._session_active:
            return "No active session. Use session_start first."

        nav_result = await self.navigate_browser(url, wait_until=wait_until)
        receipts = []
        for action in actions or []:
            action_type = action.get("type")
            if action_type == "wait":
                await asyncio.sleep(action.get("duration", 1))
                continue
            if action_type not in ("click", "fill", "press"):
                raise ValueError(f"Unsupported workflow action: {action_type}")
            receipt = await self.act_browser(
                action_type, selector=action.get("selector"),
                value=action.get("key", "Enter") if action_type == "press" else action.get("value"),
            )
            receipts.append(receipt)
            # An explicit batch uses the same checkpoints as individual tools.
            # Stop at a pending decision; later steps must not run on an
            # unconfirmed page state, and the batch is never replayed on resume.
            if receipt["status"] != "completed":
                break

        traffic = self.mitm.db.get_summary(limit=20)

        return json.dumps({
            "status": receipts[-1]["status"] if receipts else "completed",
            "actions": receipts,
            "navigation": nav_result if isinstance(nav_result, str) else json.loads(nav_result),
            "captured_requests": len(traffic),
            "recent_traffic": traffic[:10],
        })

    def _proxy_listening(self) -> bool:
        """TCP probe the proxy port. Distinguishes 'we think it's running'
        from 'it's actually accepting connections' — surfaces the case where
        mitmproxy crashed silently or never bound."""
        if not self.mitm.running:
            return False
        try:
            with socket.create_connection((self.config.proxy_host, self.mitm.port), timeout=0.3):
                return True
        except OSError:
            return False

    def get_status(self) -> Dict[str, Any]:
        if self.state == "active" and not self.mitm.running:
            self.state = "failed"
            self._session_active = False
        return {
            "session_id": self.session_id,
            "state": self.state,
            "db_path": self.config.db_path,
            "writer": self.mitm.flow_writer.get_status(),
            "proxy_error": self.mitm.last_error,
            "cleanup_error": self._cleanup_error,
            "session_active": self._session_active,
            "proxy_running": self.mitm.running,
            "proxy_listening": self._proxy_listening(),
            "browser_running": self.browser.running,
            "proxy_port": self.mitm.port,
            "proxy_host": self.config.proxy_host,
            "traffic_count": self.mitm.db.count_flows(),
            "interception_rules": len(self.mitm.interceptor.rules),
            "profile_dir": self.browser.profile_dir,
            "contexts": self.browser.list_contexts(),
            "active_context": self.browser.active,
        }

    async def hydrate_browser_from_traffic(
        self,
        host: str,
        context: str = "default",
        limit: int = 200,
    ) -> str:
        """Seed a live browser context with cookies + auth headers extracted
        from the traffic DB for `host`. Use case: external browser was
        already logged in, mitm captured the session, now we want the
        internal Playwright context to replay against the same target
        without re-doing the login.

        Cookies go into the context (so requests originated from any page
        in the context carry them). Auth headers are injected via a
        host-scoped route handler so they ride ONLY on requests to `host`
        (or its subdomains) — never leaking the credential cross-origin.

        Returns a JSON status payload."""
        if not self.browser.running:
            return json.dumps({
                "status": "error",
                "error": "Browser is not running. Use session_start or session_attach_browser first.",
            })
        ctx = self.browser.contexts.get(context)
        page = self.browser.pages.get(context)
        if ctx is None or page is None:
            return json.dumps({
                "status": "error",
                "error": f"Unknown context '{context}'. Available: {self.browser.list_contexts()}",
            })

        state = self.mitm.db.collect_session_state(host=host, limit=limit)
        if not state["cookies"] and not state["headers"]:
            return json.dumps({
                "status": "no_state_found",
                "host": state["host"],
                "stats": state["stats"],
                "hint": (
                    f"No cookies / auth headers seen for '{host}' in the "
                    f"last {limit} flows. Drive the external browser through "
                    f"a logged-in page first, then retry."
                ),
            })

        injected_cookies = 0
        if state["cookies"]:
            try:
                await ctx.add_cookies(state["cookies"])
                injected_cookies = len(state["cookies"])
            except Exception as e:
                return json.dumps({
                    "status": "error",
                    "error": f"add_cookies failed: {e}",
                    "host": state["host"],
                })

        injected_headers = {}
        if state["headers"]:
            try:
                # Host-scoped injection — do NOT use page.set_extra_http_headers,
                # which would attach these credentials to every origin the page
                # touches (cross-origin credential leak).
                await self.browser.add_scoped_auth_headers(
                    context, state["host"], state["headers"]
                )
                injected_headers = state["headers"]
            except Exception as e:
                return json.dumps({
                    "status": "partial",
                    "host": state["host"],
                    "cookies_injected": injected_cookies,
                    "headers_error": str(e),
                })

        return json.dumps({
            "status": "ok",
            "host": state["host"],
            "context": context,
            "cookies_injected": injected_cookies,
            "headers_injected": list(injected_headers.keys()),
            "stats": state["stats"],
        }, indent=2)

    async def replay_via_browser(
        self,
        flow_id: str,
        method: Optional[str] = None,
        headers_override: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        timeout_ms: int = 30000,
        context: str = "default",
    ) -> str:
        """Replay using a named browser context (cookies/session live).
        Cold-hot resolution:
          1. Live context with this name -> use it.
          2. Cold profile_dir/<name>_state.json on disk -> hydrate a fresh context, use it.
          3. Cold profile but no live browser -> curl_cffi + storage_state cookies fallback.
          4. Nothing matches -> plain curl_cffi replay (default identity)."""
        flow_obj = self.mitm.db.get_flow_object(flow_id)
        if not flow_obj:
            return json.dumps({"error": "Flow not found"})
        target_method = (method or flow_obj.method).upper()
        target_headers = dict(flow_obj.headers or {})
        for k in ("Host", "Content-Length", "Content-Encoding", "Cookie"):
            target_headers.pop(k, None)
            target_headers.pop(k.lower(), None)
        if headers_override:
            target_headers.update(headers_override)
        target_body = body if body is not None else flow_obj.body

        # Replay-correlation nonce — stripped by the recorder before forwarding
        # and stored on the captured flow, so we map the result back even under
        # concurrent replays to the same endpoint.
        import uuid as _uuid
        replay_nonce = _uuid.uuid4().hex
        target_headers["X-AgentProxy-Replay"] = replay_nonce

        # Step 1: live context
        ctx_label = context
        if self.browser.running and self.browser._browser is not None:
            if context not in self.browser.contexts:
                # Step 2: try cold hydrate
                hydrated = await self.browser.ensure_context_from_profile(context)
                if not hydrated:
                    return json.dumps({
                        "error": f"context '{context}' has no live session and no saved profile. "
                                 "Login first or use session_create_context.",
                    })
            try:
                before_ts = time.time()
                result = await self.browser.request_fetch(
                    url=flow_obj.url,
                    method=target_method,
                    headers=target_headers,
                    data=target_body,
                    timeout=timeout_ms,
                    context=context,
                )
                # Find the matching captured flow (proxy already labelled it).
                import asyncio as _aio
                new_flow_id = None
                for _ in range(10):
                    new_flow_id = (self.mitm.db.find_replay_match_by_nonce(replay_nonce)
                                   or self.mitm.db.find_replay_match(flow_obj.url, target_method, before_ts))
                    if new_flow_id:
                        break
                    await _aio.sleep(0.1)
                return json.dumps({
                    "via": "browser_context",
                    "context": ctx_label,
                    "status_code": result["status"],
                    "size": result["body_size"],
                    "new_flow_id": new_flow_id,
                    "headers": result["headers"],
                    "body_preview": (result["body"] or "")[:2000],
                }, indent=2)
            except Exception as e:
                return json.dumps({"via": "browser_context", "error": str(e)})

        # Step 3: browser not running, but maybe a saved profile exists
        if self.browser.profile_dir:
            state_path = os.path.join(self.browser.profile_dir, f"{context}_state.json")
            if os.path.exists(state_path):
                return await self.mitm.replay_with_storage_state(
                    flow_id=flow_id,
                    storage_state_path=state_path,
                    method=method,
                    headers=headers_override,
                    body=body,
                    timeout=timeout_ms / 1000.0,
                    context_label=context,
                )

        # Step 4: nothing — fall back to default-identity replay
        return await self.mitm.replay_request(
            flow_id=flow_id, method=method,
            headers=headers_override, body=body,
            timeout=timeout_ms / 1000.0,
        )
