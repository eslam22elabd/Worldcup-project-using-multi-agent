/**
 * stripMarkdown — removes common markdown syntax from Week 3 agent
 * output (headers, bold/italic markers, bullet dashes) so messages
 * render as clean plain text instead of showing raw "##", "**" etc.
 *
 * Intentionally a lightweight regex pass, not a full markdown parser --
 * the goal is just to strip visual noise, not to re-render formatting.
 */

export function stripMarkdown(text) {
  if (!text) return "";

  return text
    .replace(/^#{1,6}\s+/gm, "") // ### Heading -> Heading
    .replace(/\*\*(.*?)\*\*/g, "$1") // **bold** -> bold
    .replace(/__(.*?)__/g, "$1") // __bold__ -> bold
    .replace(/\*(.*?)\*/g, "$1") // *italic* -> italic
    .replace(/_(.*?)_/g, "$1") // _italic_ -> italic
    .replace(/^[-*]\s+/gm, "") // - bullet / * bullet -> (removed)
    .replace(/`{1,3}([^`]*)`{1,3}/g, "$1") // `code` / ```code``` -> code
    .replace(/[ \t]+\n/g, "\n") // trailing spaces before line breaks
    .trim();
}
