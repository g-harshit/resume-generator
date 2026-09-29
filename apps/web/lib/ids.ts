/** Same shape as the backend's `new_id`: new entries get a stable id the moment
 *  they're created, so React keys and parse notes keep pointing at them. */
export function newId(prefix: string): string {
  const bytes = crypto.getRandomValues(new Uint8Array(4));
  return `${prefix}_${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`;
}
