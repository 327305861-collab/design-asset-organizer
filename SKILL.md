---
name: design-asset-organizer
license: MIT
description: 为图片素材生成可搜索的中文文件名，或安全批量重命名本地 JPG、JPEG、PNG、WebP 图片。适用于图片命名、素材整理、批量改名；不处理非图片文件。Name image assets in Chinese or safely rename local images.
---

# Design Asset Organizer

Turn visual content into stable Chinese search keywords. Optimize for finding the asset months later, not for prose, creativity, or exhaustive description.

## Required reference

Read [references/naming-rules.md](references/naming-rules.md) before naming images. It is the source of truth for keyword order, controlled vocabulary, length, and output format.
Resolve references and scripts relative to THIS loaded SKILL.md, not the user's working directory. Use the discovered skill root's absolute path; never hard-code a particular username, OS, or install location.

## Workflow

1. Establish the ordered input set and preserve each source extension. For a local folder, include only the requested scope and supported image formats; do not recurse unless the user asks.
2. Inspect every image visually using the host's available image-viewing tools. If local WebP or another supported image cannot be viewed, use a temporary preview when a converter is available, preserving the original. If images or visual tools are unavailable, say which images cannot be inspected and ask for accessible images; do not invent names from filenames alone. Read nearby existing filenames when available and reuse established vocabulary for equivalent visuals.
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
   Use absolute source paths and store the plan and manifest in a writable location. Resolve duplicate proposed names with a stable distinguishing keyword or numeric suffix before applying. Skip files whose names already match. Only process folders the host can read and write; do not broaden permissions on your own.
2. Find a working Python 3.9+ interpreter: try the host's configured Python, `python`, `python3`, or Windows `py -3`; verify its version. No pip packages, separate API key, or external image service are needed by the helper. If none works, return naming suggestions and explain that actual renaming requires Python; do not pretend files were renamed or bypass the helper's checks.
3. Preview and validate with the actual interpreter and absolute script/plan paths (quote paths containing spaces):

   `python "<skill-root>/scripts/apply_rename_plan.py" "<absolute-plan.json>"`

4. Resolve every reported collision or invalid name. If the user has requested actual renaming, apply with:

   `python "<skill-root>/scripts/apply_rename_plan.py" "<absolute-plan.json>" --apply`

5. Retain the generated manifest so the operation can be reversed. To restore the original names at the user's request:

   `python "<skill-root>/scripts/apply_rename_plan.py" --rollback "<absolute-manifest.json>" --apply`

The helper refuses existing targets, handles rename cycles, and writes a recovery manifest before changes. Only report success after a zero exit code. A prepared manifest means execution may have been interrupted: inspect actual files and report the manifest path instead of blindly retrying. For installation or interpreter problems, run the absolute path to `scripts/doctor.py` with the working interpreter.

After applying, report the ordered mappings only. Add a short manifest path only when a local rename occurred. Do not rename unsupported files, move directories, delete originals, or alter image contents.
