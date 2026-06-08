/** Default cluster used in nav links until a cluster picker exists. */
export const DEFAULT_CLUSTER_ID = "fortytwo";

export function clusterStatusPath(clusterId = DEFAULT_CLUSTER_ID) {
  return `/cluster/${clusterId}/status`;
}

export function clusterDocsPath(clusterId = DEFAULT_CLUSTER_ID) {
  return `/cluster/${clusterId}/docs`;
}
