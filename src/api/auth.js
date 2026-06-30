import { apiFetch } from "./client";

export async function authCheck() {
  return apiFetch("/api/auth-check");
}

export async function login(email, password) {
  return apiFetch("/api/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(email, password) {
  return apiFetch("/api/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function logout() {
  return apiFetch("/api/logout", {
    method: "POST",
  });
}
