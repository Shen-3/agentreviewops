export function ErrorState({ message = "Unable to load data." }: { message?: string }) {
  return <div className="empty-state error-state">{message}</div>;
}

