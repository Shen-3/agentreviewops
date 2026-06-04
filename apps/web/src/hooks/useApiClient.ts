import React from "react";

import { createApiClient } from "../api/client";

export function useApiClient(baseUrl: string, apiKey: string) {
  return React.useMemo(() => createApiClient({ baseUrl, apiKey }), [apiKey, baseUrl]);
}

