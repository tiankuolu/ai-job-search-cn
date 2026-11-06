import { useCallback, useEffect, useState } from 'react';
import { api, type Job, type Meta, type Run } from '../types';

export function useWorkspace() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api<Meta>('/meta', { signal: controller.signal }),
      api<Job[]>('/jobs', { signal: controller.signal }),
      api<Run[]>('/runs', { signal: controller.signal }),
    ])
      .then(([configuration, knownJobs, history]) => {
        setMeta(configuration);
        setJobs(knownJobs);
        setRuns(history);
        setLoading(false);
      })
      .catch(reason => {
        if (!controller.signal.aborted) {
          setError(String(reason.message));
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [knownJobs, history, configuration] = await Promise.all([api<Job[]>('/jobs'), api<Run[]>('/runs'), api<Meta>('/meta')]);
      setJobs(knownJobs);
      setRuns(history);
      setMeta(configuration);
    } catch (reason) {
      setError((reason as Error).message);
    }
  }, []);

  return { meta, jobs, runs, loading, error, setError, refresh };
}
