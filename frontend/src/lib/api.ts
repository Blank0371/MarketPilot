// Temporary dev control for switching between mock data and backend endpoint.
export type DataMode = "mock" | "endpoint";

// ─── Types ────────────────────────────────────────────────────────────────────

export type ExtractDescriptionsResponse = {
  descriptions: string[];
};

// ─── Config ───────────────────────────────────────────────────────────────────

const BACKEND_BASE = "http://127.0.0.1:8003";

// ─── Extraction endpoint ──────────────────────────────────────────────────────

/**
 * POST /api/extract — send a free-form business idea and receive a list of
 * market signal descriptions from the backend extraction agent.
 *
 * Throws a user-readable error when:
 * - the network request fails (backend not running, CORS, etc.)
 * - the HTTP response is not 2xx
 * - the response body is not valid JSON
 * - the response shape is not { descriptions: string[] }
 */
export async function extractDescriptionsFromEndpoint(
  userInput: string,
): Promise<ExtractDescriptionsResponse> {
  let response: Response;
  try {
    response = await fetch(`${BACKEND_BASE}/api/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userInput }),
    });
  } catch {
    throw new Error(
      `Backend extraction failed. Check that the backend is running on ${BACKEND_BASE}.`,
    );
  }

  if (!response.ok) {
    throw new Error(
      `Backend extraction failed (HTTP ${response.status}). Check that the backend is running on ${BACKEND_BASE}.`,
    );
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error(
      "Backend returned a non-JSON response. Check the /api/extract endpoint.",
    );
  }

  if (
    typeof data !== "object" ||
    data === null ||
    !("descriptions" in data) ||
    !Array.isArray((data as { descriptions: unknown }).descriptions)
  ) {
    throw new Error(
      "Backend returned an unexpected shape — expected { descriptions: string[] }.",
    );
  }

  return data as ExtractDescriptionsResponse;
}
