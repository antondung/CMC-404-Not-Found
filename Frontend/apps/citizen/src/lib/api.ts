// Thin API client for the Citizen portal. Talks to the BE3 gateway envelope format:
//   success => { ok: true, data: <T>, meta: {...} }
//   error   => { ok: false, data: { message, code, details }, meta: {...} }
import { apiFetchErrorMessage, resolveApiBase } from './apiBase';

export function getApiBase(): string {
  return resolveApiBase();
}

/** @deprecated use getApiBase() — kept for existing imports */
export const API_BASE = resolveApiBase();

// Absolute URL for a public raw legal file (browser navigates/downloads directly).
export function fileUrl(fileId: string): string {
  return `${resolveApiBase()}/citizen/legal/files/${encodeURIComponent(fileId)}`;
}

export interface ApiEnvelope<T> {
  ok: boolean;
  data: T;
  meta?: Record<string, unknown>;
}

async function parse<T>(res: Response): Promise<T> {
  const json = (await res.json().catch(() => null)) as ApiEnvelope<T> | null;
  if (!res.ok || !json || json.ok !== true) {
    const message =
      (json?.data as { message?: string } | undefined)?.message ??
      `Yêu cầu thất bại (HTTP ${res.status})`;
    throw new Error(message);
  }
  return json.data;
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const base = resolveApiBase();
  if (!base) {
    throw new Error(apiFetchErrorMessage(new Error('Failed to fetch'), base));
  }
  try {
    return await fetch(`${base}${path}`, init);
  } catch (err) {
    throw new Error(apiFetchErrorMessage(err, base));
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await request(path, {
    headers: { Accept: 'application/json' },
  });
  return parse<T>(res);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  });
  return parse<T>(res);
}
