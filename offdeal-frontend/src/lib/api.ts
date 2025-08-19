const BASE = process.env.NEXT_PUBLIC_API_BASE?.replace(/\/+$/, "") || "";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const msg = await res.text().catch(() => "");
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Prospects
  async listProspects() {
    return j<import("../types").Prospect[]>(
      await fetch(`${BASE}/prospects`, { cache: "no-store" })
    );
  },
  async createProspect(payload: Partial<import("../types").Prospect>) {
    return j<import("../types").Prospect>(
      await fetch(`${BASE}/prospects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
    );
  },

  // Decks
  async generateDeck(prospectId: number) {
    return j<import("../types").Deck>(
      await fetch(`${BASE}/decks/${prospectId}/generate`, { method: "POST" })
    );
  },
  async renderDeck(deckId: number) {
    return j<import("../types").Deck>(
      await fetch(`${BASE}/decks/${deckId}/render`, { method: "POST" })
    );
  },
  async updateDeck(deckId: number, payload: { title?: string; slides: any[] }) {
    return j<import("../types").Deck>(
      await fetch(`${BASE}/decks/${deckId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
    );
  },

  // Emails
  async generateEmails(prospectId: number) {
    return j<import("../types").EmailBatch>(
      await fetch(`${BASE}/emails/${prospectId}/generate`, { method: "POST" })
    );
  },
  async listEmails(prospectId: number) {
    return j<import("../types").EmailBatch>(
      await fetch(`${BASE}/emails/${prospectId}`)
    );
  },
  async updateEmail(id: number, payload: { subject?: string; body?: string }) {
    return j<import("../types").EmailItem>(
      await fetch(`${BASE}/emails/item/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
    );
  },
};
