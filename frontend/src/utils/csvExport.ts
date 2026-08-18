/**
 * Reusable CSV download utility.
 * Future modules (Hospitals, Clinics, Doctors, …) reuse this helper.
 */

/** Trigger a browser download of a CSV blob with the given filename. */
export function triggerCsvDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** Extract the filename from a Content-Disposition header, with fallback. */
export function filenameFromDisposition(header: string | undefined, fallback: string): string {
  if (!header) return fallback;
  const match = /filename="?([^";]+)"?/i.exec(header);
  return match ? match[1] : fallback;
}
