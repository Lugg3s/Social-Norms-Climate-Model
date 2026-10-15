"""Persistent, individually replaceable workers with per-task wall-clock limits.

Unlike Future.result(timeout=...), termination actually stops the timed-out
computation. Spawn keeps behavior consistent on Windows and avoids fork state.
"""
from __future__ import annotations

import multiprocessing as mp
import math
from multiprocessing.connection import wait
import signal
import sys
from contextlib import redirect_stdout, redirect_stderr
import traceback
from datetime import datetime
from time import monotonic


class _WorkerStream:
    """Forward Python console output to the parent, the sole log-file writer."""

    def __init__(self, connection, stream):
        self.connection = connection
        self.stream = stream

    def write(self, text):
        if text:
            self.connection.send(("output", self.stream, text))
        return len(text)

    def flush(self):
        pass

    def write_log_only(self, text):
        self.connection.send(("log_only", self.stream, text))


def _worker(connection, function):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        connection.send(("ready",))
        while True:
            task = connection.recv()
            if task is None:
                return
            started = monotonic()
            connection.send(("started", started,
                             datetime.now().astimezone().isoformat(timespec="milliseconds")))
            try:
                with redirect_stdout(_WorkerStream(connection, "stdout")), \
                     redirect_stderr(_WorkerStream(connection, "stderr")):
                    result = function(task)
                outcome = dict(status="completed", result=result)
            except BaseException as error:
                outcome = dict(status="failed", error_type=type(error).__name__,
                               error_message=str(error), traceback=traceback.format_exc())
            outcome["elapsed_seconds"] = monotonic() - started
            connection.send(("finished", outcome))
    finally:
        connection.close()


def _stop(slot):
    process = slot["process"]
    if process.is_alive():
        process.terminate()
    process.join(timeout=2)
    if process.is_alive():
        process.kill()
        process.join(timeout=2)
    if process.is_alive():
        raise RuntimeError(f"Could not stop worker {process.pid}")
    slot["connection"].close()
    process.close()


def bounded_map(function, tasks, workers, timeout_seconds):
    """Yield (input_index, outcome) in completion order, preserving task identity.

    The deadline starts in the child when it begins a task, not when queued.
    Worker startup has a separate 120-second watchdog. Other active workers
    continue when one is terminated. All children are stopped on interruption.
    """
    if workers < 1 or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("workers and timeout_seconds must be positive")
    tasks = list(tasks)
    context = mp.get_context("spawn")
    slots = []
    next_index = 0
    completed = 0

    def launch():
        parent, child = context.Pipe()
        process = context.Process(target=_worker, args=(child, function))
        try:
            process.start()
        except BaseException:
            parent.close()
            child.close()
            raise
        child.close()
        return dict(process=process, connection=parent, index=None, started=None,
                    started_at=None, launched=monotonic(), ready=False)

    def dispatch(slot):
        nonlocal next_index
        if next_index < len(tasks):
            slot.update(index=next_index, started=None, started_at=None,
                        dispatched=monotonic())
            slot["connection"].send(tasks[next_index])
            next_index += 1

    try:
        for _ in range(min(workers, len(tasks))):
            slots.append(launch())
        while completed < len(tasks):
            readable = wait([s["connection"] for s in slots], timeout=.1)
            for slot in list(slots):
                connection = slot["connection"]
                if connection in readable:
                    try:
                        message = connection.recv()
                    except (EOFError, OSError):
                        message = ("crashed",)
                    kind = message[0]
                    if kind == "ready":
                        slot["ready"] = True
                        dispatch(slot)
                    elif kind == "started":
                        slot.update(started=message[1], started_at=message[2])
                    elif kind == "output":
                        stream = getattr(sys, message[1])
                        stream.write(message[2])
                        stream.flush()
                    elif kind == "log_only":
                        stream = getattr(sys, message[1])
                        if hasattr(stream, "write_log_only"):
                            stream.write_log_only(message[2])
                    elif kind == "finished":
                        index = slot["index"]
                        outcome = dict(message[1], worker_pid=slot["process"].pid,
                                       started_at=slot["started_at"])
                        slot.update(index=None, started=None)
                        completed += 1
                        dispatch(slot)
                        yield index, outcome
                    else:
                        raise RuntimeError(f"Worker {slot['process'].pid} exited unexpectedly")

                now = monotonic()
                if not slot["ready"] and now-slot["launched"] > 120:
                    raise RuntimeError("Worker startup exceeded 120 seconds")
                if slot["index"] is None:
                    continue
                if slot["started"] is None:
                    if now-slot["dispatched"] > 120:
                        raise RuntimeError("Worker did not acknowledge its assigned task")
                    continue
                # Output must not postpone a deadline for a noisy stuck worker.
                if now-slot["started"] >= timeout_seconds:
                    index = slot["index"]
                    outcome = dict(status="timed_out", elapsed_seconds=now-slot["started"],
                                   worker_pid=slot["process"].pid, started_at=slot["started_at"])
                    _stop(slot)
                    slots.remove(slot)
                    completed += 1
                    if next_index < len(tasks):
                        slots.append(launch())
                    yield index, outcome
    finally:
        for slot in slots:
            _stop(slot)
