# Jarvis / Lali a Pooli - SD1.5 reference workflow

1. Before drawing, call `character_studio_status` and `character_studio_lessons` for the selected character. Original approved references in `studio_library/refs` are immutable.
2. Check `local_comfy_status` and then use `local_comfy_reference_study` with character `lali` or `pooli`. It uses the matching approved fullbody reference COPY in ComfyUI input, not an ungrounded text-to-image prompt.
3. Workflows: `sd15_lali_reference_api.json`, `sd15_pooli_reference_api.json`. Model: `sd15-pruned-emaonly.safetensors`, 512x768, denoise 0.28, low VRAM GTX 1060 6 GB. ComfyUI local API 127.0.0.1:8188.
4. Output is an unapproved single-frame candidate. It is NOT a completed turnaround, multi-frame animation, consistent side/back pose, or publishable Reel. Do not use image slicing, fake flat sprite rotations, or silently replace masters.
5. Review full body, paws, feet, tail, clothing, identity, and reference match. Use `character_studio_ingest` and `character_studio_visual_review`; human approval required for promotion to a master. Record mistakes via `character_studio_record_lesson`.
6. For walk, turn, sit, expressions: create and validate actual distinct full-body poses/frames before Godot import. Reject inconsistent outputs. Never upload or publish without separate owner approval.
7. Text-to-image SD1.5 img2img does NOT guarantee identity preservation; reference conditioning, manually corrected turnaround sheets, and frame-to-frame QA may still be required.
