export type OutboxEntry = { id: string; state: 'pending' | 'sent' };

export function queued(entries: OutboxEntry[]): OutboxEntry[] {
  return entries.filter(entry => entry.state === 'pending');
}
