export function StatusMessage({ error, message }: { error?: string | null; message?: string | null }) {
  if (!error && !message) return null;
  return (
    <p className={`rounded-[8px] border px-3 py-2 text-sm ${error ? "border-[#dfb8aa] bg-[#f6e5df] text-[color:var(--dossier-rust)]" : "border-[#b9cfb6] bg-[color:var(--dossier-green-soft)] text-[color:var(--dossier-green)]"}`}>
      {error ?? message}
    </p>
  );
}
