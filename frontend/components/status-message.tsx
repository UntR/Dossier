export function StatusMessage({ error, message }: { error?: string | null; message?: string | null }) {
  if (!error && !message) return null;
  return (
    <p className={`text-sm ${error ? "text-rose-700" : "text-emerald-700"}`}>
      {error ?? message}
    </p>
  );
}
