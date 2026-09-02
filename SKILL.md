---
name: design-asset-organizer
description: Analyze JPG, JPEG, PNG, and WebP image assets and generate or apply consistent, searchable Chinese filenames from their visible subject, use case, style, color, visual elements, composition, and useful brand text. Use for naming suggestions, uploaded-image batches, or safe local image renaming; do not use for general file organization or non-image files.
---

# Design Asset Organizer

Turn visual content into stable Chinese search keywords. Optimize for finding the asset months later, not for prose, creativity, or exhaustive description.

## Required reference

Read [references/naming-rules.md](references/naming-rules.md) before naming images. It is the source of truth for keyword order, controlled vocabulary, length, and output format.

## Workflow

1. Establish the ordered input set and preserve each source extension. For a local folder, include only the requested scope and supported image formats; do not recurse unless the user asks.
2. Inspect every image visually. Do not infer facts that are not visible. Read nearby existing filenames when available and reuse established vocabulary for equivalent visuals.
3. Select the 5–8 terms the user is most likely to search later. Build the name with the full-width separator `＊`; never use the Windows-invalid ASCII `*`.
4. Check every candidate against the reference: priority order, controlled terms, duplicates, unsupported claims, length, extension, and collision risk.
5. Follow the mode below. Keep the final response limited to results and any essential failure notice.

## Suggestion mode

Use this mode for uploaded images, attached images, or requests that ask only for names.

- For one image, output only the proposed filename. If two genuinely different use cases are equally plausible, add one line beginning `备选命名｜`.
- For multiple images, preserve upload order and output exactly one mapping per line:

  `01｜原文件名 → 新文件名`

- If the original filename is unavailable, use `原图`.
- Do not explain the image or the naming rationale.

## Local rename mode

Use this mode only when the user explicitly asks to rename local files.

1. Create a UTF-8 JSON rename plan with one `source` and one `target` per item. `target` is a filename in the same directory, not a path. Keep the original extension exactly; the helper adds it when omitted.
2. Preview and validate with:

   `python scripts/apply_rename_plan.py <plan.json>`

3. Resolve every reported collision or invalid name. Then apply with:

   `python scripts/apply_rename_plan.py <plan.json> --apply`

4. Retain the generated manifest so the operation can be reversed. To restore the original names:

   `python scripts/apply_rename_plan.py --rollback <manifest.json> --apply`

The helper prevents overwrites, handles rename cycles safely, and writes a rollback manifest. If the helper cannot run, perform equivalent collision checks and preserve a reversible source-to-target mapping before changing files.

After applying, report the ordered mappings only. Add a short manifest path only when a local rename occurred. Do not rename unsupported files, move directories, delete originals, or alter image contents.
