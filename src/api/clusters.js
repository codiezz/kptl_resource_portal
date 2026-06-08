import { apiFetch } from "./client";

export async function listClusters() {
  return apiFetch("/api/clusters");
}

export async function getClusterHealth(
  clusterId,
  { start, end } = {}
) {
  const body = {};
  if (start) body.start = start;
  if (end) body.end = end;

  return apiFetch(
    `/api/clusters/${encodeURIComponent(clusterId)}/health`,
    {
      method: "POST",
      body: JSON.stringify(body),
    }
  );
}
