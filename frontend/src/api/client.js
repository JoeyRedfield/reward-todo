let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

function getErrorMessage(error, fallback) {
  if (error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

async function request(path, options) {
  const response = await fetch(`/api${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    ...options,
  });

  let payload = null;
  if (response.status !== 204) {
    try {
      payload = await response.json();
    } catch {}
  }

  if (
    response.status === 401 &&
    unauthorizedHandler &&
    payload?.detail === "Authentication required"
  ) {
    unauthorizedHandler();
  }

  if (!response.ok) {
    let detail = "request failed";
    if (payload) {
      detail = payload.detail || detail;
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }

  return payload;
}

export async function login(payload) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function register(payload) {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logout() {
  return request("/auth/logout", {
    method: "POST",
  });
}

export async function fetchCurrentUser() {
  return request("/auth/me");
}

export async function changePassword(payload) {
  return request("/auth/change-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchDailyTasks(date) {
  return request(`/daily-tasks?date=${encodeURIComponent(date)}`);
}

export async function completeDailyTask(taskId, actualDurationMinutes) {
  return request(`/daily-tasks/${taskId}/complete`, {
    method: "POST",
    body: JSON.stringify(
      actualDurationMinutes === undefined
        ? {}
        : { actual_duration_minutes: actualDurationMinutes }
    ),
  });
}

export async function fetchRewardSummary() {
  return request("/rewards/summary");
}

export async function fetchRewardLedger(limit = 20) {
  return request(`/rewards/ledger?limit=${limit}`);
}

export async function spendReward(amount, reason) {
  return request("/rewards/spend", {
    method: "POST",
    body: JSON.stringify({ amount, reason }),
  });
}

export async function fetchProjects() {
  return request("/task-projects");
}

export async function createProject(name) {
  return request("/task-projects", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function updateProject(projectId, payload) {
  return request(`/task-projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function fetchTaskTemplates(projectId) {
  const query =
    projectId === undefined || projectId === null
      ? ""
      : `?project_id=${encodeURIComponent(projectId)}`;
  return request(`/task-templates${query}`);
}

export async function createTaskTemplate(payload) {
  return request("/task-templates", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createDailyTask(payload) {
  return request("/daily-tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export { getErrorMessage };
