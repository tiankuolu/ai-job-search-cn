import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, terminal, type RunDetail, type RunEvent } from '../types';

type Options = {
  onError: (message: string | null) => void;
  onOpen: (run: RunDetail) => void;
  onFinished: () => Promise<void> | void;
};

export type RunMetrics = { callCount: number; toolCount: number; tokens: number; latency: number };

export function useRunStream({ onError, onOpen, onFinished }: Options) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [streamState, setStreamState] = useState('');
  const [playback, setPlayback] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const selectionVersion = useRef(0);
  const pending = useRef<RunEvent[]>([]);
  const frame = useRef<number | null>(null);
  const runRef = useRef<RunDetail | null>(run);
  const errorRef = useRef(onError);
  const openRef = useRef(onOpen);
  const finishedRef = useRef(onFinished);
  runRef.current = run;
  errorRef.current = onError;
  openRef.current = onOpen;
  finishedRef.current = onFinished;

  const loadRun = useCallback(async (id: string) => {
    const version = ++selectionVersion.current;
    setPlaying(false);
    setPlayback(null);
    errorRef.current(null);
    try {
      const value = await api<RunDetail>(`/runs/${id}`);
      if (version !== selectionVersion.current) return;
      setRun(value);
      setEvents(value.trace.events || []);
      pending.current = [];
      openRef.current(value);
    } catch (reason) {
      if (version === selectionVersion.current) errorRef.current((reason as Error).message);
    }
  }, []);

  const reset = useCallback(() => {
    selectionVersion.current += 1;
    setRun(null);
    setEvents([]);
    setPlayback(null);
    setPlaying(false);
  }, []);

  const activeId = run && !terminal(run.status) ? run.run_id : null;
  useEffect(() => {
    if (!activeId) return;
    const last = runRef.current?.trace.events?.at(-1)?.seq || 0;
    const source = new EventSource(`/api/runs/${activeId}/events?after=${last}`);
    setStreamState('connecting');
    source.onopen = () => setStreamState('connected');
    source.onmessage = message => {
      const event: RunEvent = JSON.parse(message.data);
      pending.current.push(event);
      if (frame.current !== null) return;
      frame.current = requestAnimationFrame(() => {
        frame.current = null;
        const batch = pending.current;
        pending.current = [];
        if (!batch.length) return;
        setEvents(current => {
          const known = new Set(current.map(item => item.seq));
          return [...current, ...batch.filter(item => !known.has(item.seq))].sort((a, b) => a.seq - b.seq);
        });
      });
    };
    source.onerror = () => setStreamState('reconnecting');
    source.addEventListener('end', () => {
      source.close();
      setStreamState('');
      api<RunDetail>(`/runs/${activeId}`)
        .then(value => {
          if (runRef.current?.run_id === activeId) {
            setRun(value);
            setEvents(value.trace.events || []);
          }
          return finishedRef.current();
        })
        .catch(reason => errorRef.current(reason.message));
    });
    return () => { source.close(); setStreamState(''); if (frame.current !== null) cancelAnimationFrame(frame.current); frame.current = null; pending.current = []; };
  }, [activeId]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setPlayback(current => {
      if (current === null || current >= events.length) {
        setPlaying(false);
        return current;
      }
      return current + 1;
    }), 650);
    return () => window.clearInterval(timer);
  }, [playing, events.length]);

  const visibleEvents = useMemo(() => playback === null ? events : events.slice(0, playback), [events, playback]);
  const metrics = useMemo<RunMetrics>(() => {
    const liveCalls = visibleEvents.filter(event => ['llm.finished', 'llm.failed'].includes(event.type));
    return {
      callCount: run?.source === 'legacy' ? run.trace.calls.length : visibleEvents.filter(event => event.type === 'llm.started').length,
      tokens: run?.source === 'legacy' ? run.trace.total_tokens : liveCalls.reduce((sum, event) => sum + (event.data.prompt_tokens || 0) + (event.data.completion_tokens || 0), 0),
      latency: run?.source === 'legacy' ? run.trace.calls.reduce((sum, call) => sum + call.latency_ms, 0) : liveCalls.reduce((sum, event) => sum + (event.data.latency_ms || 0), 0),
      toolCount: run?.source === 'legacy' ? run.trace.calls.reduce((sum, call) => sum + call.tool_calls.length, 0) : visibleEvents.filter(event => event.type === 'tool.started').length,
    };
  }, [run, visibleEvents]);

  return { run, events, visibleEvents, metrics, streamState, playback, setPlayback, playing, setPlaying, loadRun, reset };
}
