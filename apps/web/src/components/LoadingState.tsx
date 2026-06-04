export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return <div className="empty-state">{message}</div>;
}

