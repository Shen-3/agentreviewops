import React from "react";

export type ApiKeyStorageMode = "session" | "local";

export const API_KEY_LOCAL_STORAGE_KEY = "agentreviewops.apiKey";
export const API_KEY_SESSION_STORAGE_KEY = "agentreviewops.sessionApiKey";
export const API_KEY_STORAGE_MODE_KEY = "agentreviewops.apiKeyStorageMode";

export function useLocalStorage<T>(key: string, initialValue: T) {
  const [value, setValue] = React.useState<T>(() => {
    const stored = window.localStorage.getItem(key);
    if (!stored) {
      return initialValue;
    }
    try {
      return JSON.parse(stored) as T;
    } catch {
      return initialValue;
    }
  });

  React.useEffect(() => {
    window.localStorage.setItem(key, JSON.stringify(value));
  }, [key, value]);

  return [value, setValue] as const;
}

export function readStoredApiKey() {
  const sessionKey = window.sessionStorage.getItem(API_KEY_SESSION_STORAGE_KEY);
  if (sessionKey) {
    return { apiKey: sessionKey, mode: "session" as const };
  }
  const localKey = window.localStorage.getItem(API_KEY_LOCAL_STORAGE_KEY);
  if (localKey) {
    return { apiKey: localKey, mode: "local" as const };
  }
  return { apiKey: "", mode: "session" as const };
}

export function storeApiKey(apiKey: string, mode: ApiKeyStorageMode) {
  if (mode === "local") {
    window.sessionStorage.removeItem(API_KEY_SESSION_STORAGE_KEY);
    window.localStorage.setItem(API_KEY_LOCAL_STORAGE_KEY, apiKey);
    return;
  }
  window.localStorage.removeItem(API_KEY_LOCAL_STORAGE_KEY);
  window.sessionStorage.setItem(API_KEY_SESSION_STORAGE_KEY, apiKey);
}

export function clearStoredApiKey() {
  window.localStorage.removeItem(API_KEY_LOCAL_STORAGE_KEY);
  window.sessionStorage.removeItem(API_KEY_SESSION_STORAGE_KEY);
}

