export interface EventReview {
  id: string;
  title: string;
  pending: boolean;
}

export function pendingReviews(items: EventReview[]): EventReview[] {
  // FIXME: the badge count should use the same filtered set.
  return items.filter(item => item.pending);
}
