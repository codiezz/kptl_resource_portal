import { apiFetch } from "./client";

export async function authCheck() {
  return apiFetch("/api/auth-check");
}

export async function login(username, password) {
  return apiFetch("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function logout() {
  return apiFetch("/api/logout", {
    method: "POST",
  });
}
