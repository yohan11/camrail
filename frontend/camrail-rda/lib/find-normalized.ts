/**
 * Helper to find `needle` in `haystack`, ignoring variations in whitespace,
 * line breaks, and casing, while returning the exact slice indices in the original `haystack`.
 */
export function findNormalized(
  haystack: string,
  needle: string
): { start: number; end: number } | null {
  if (!haystack || !needle) return null;

  // Build normalized version of haystack with an index mapping:
  // normIndex -> original char index in haystack
  const indexMap: number[] = [];
  let normHaystack = "";
  let inWhitespace = false;

  for (let i = 0; i < haystack.length; i++) {
    const char = haystack[i];
    if (/\s/.test(char)) {
      if (!inWhitespace && normHaystack.length > 0) {
        normHaystack += " ";
        indexMap.push(i);
        inWhitespace = true;
      }
    } else {
      normHaystack += char.toLowerCase();
      indexMap.push(i);
      inWhitespace = false;
    }
  }

  // Normalize needle (collapse multiple spaces/newlines, trim, lowercase)
  const normNeedle = needle
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();

  if (!normNeedle) return null;

  let matchIdx = normHaystack.indexOf(normNeedle);

  // If exact match wasn't found, try without trailing punctuation on needle
  if (matchIdx === -1) {
    const strippedNeedle = normNeedle.replace(/[.,:;!?]+$/, "").trim();
    if (strippedNeedle.length > 5) {
      matchIdx = normHaystack.indexOf(strippedNeedle);
      if (matchIdx !== -1) {
        const startOrig = indexMap[matchIdx];
        const endNorm = Math.min(matchIdx + strippedNeedle.length - 1, indexMap.length - 1);
        const endOrig = indexMap[endNorm] + 1;
        return { start: startOrig, end: endOrig };
      }
    }
  }

  if (matchIdx === -1) return null;

  const startOrig = indexMap[matchIdx];
  const endNorm = Math.min(matchIdx + normNeedle.length - 1, indexMap.length - 1);
  const endOrig = indexMap[endNorm] + 1;

  return { start: startOrig, end: endOrig };
}
