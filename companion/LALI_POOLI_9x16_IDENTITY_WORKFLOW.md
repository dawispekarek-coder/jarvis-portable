# Lali & Pooli: character identity + vertical 9:16
Research 2026-10-28. For Jarvis production. No cutout puppet animation. Preserve original approved character identity.
## Non-negotiable
Lali: same pink/cream raccoon, large pink bow and pink dress. Pooli: same tan/cream raccoon, blue hoodie, dark trousers and shoulder bag. Keep face, eye markings, paws, ears, proportions and clothes across every frame. Do not crop limbs, distort canvas or create floating/deformed props.
Portrait 9:16 is required throughout storyboard, model and export. Smoke test 288x512; final 1080x1920. Target H.264 video + AAC audio. Do NOT squeeze or crop a 3:4 source to 9:16.
## Proven method from official WanGP guide
1. Keep one approved canonical master for each character, plus front/3-4/side/back and consistent expression sheets. Start/end frames for every scene should derive from the same canonical master, never recursively from previous generated frames. This limits visual drift.
2. VACE: use reference images to inject characters and/or exact control frames. Full-scene first/last frames KEEP the background. Cutout character-only refs may remove background; do not strip scene backgrounds.
3. Motion: supply control video or trajectories; use masks to distinguish face/paws/blanket/door/background. Black mask preserves pixels; white edits. Preview processed mask before generation; save with --save-masks if necessary.
4. Native vertical composition: source storyboard scenes measure 376x504 (3:4). Use VACE spatial outpainting TOP/BOTTOM about 17%/17%, NOT crop/squeeze. Config trial video_guide_outpainting="17 17 0 0". Verify expansion truly applied in output; setting alone is no proof.
5. Test 17 frames and inspect first/middle/last images before long render. Watch for face drift, deforming paws, altered bow, fused blanket, geometry changes and cropped extremities. One MP4 written is not quality approval.
6. Scale into several short overlapping controlled shots with repeated identity anchors. Finish by upscale/interpolation and encode 1080x1920. Never call unreviewed render publishable.
## Installed / test
WanGP: H:\RealJarvis\OptionalPlugins\WanGP
Canonical frames: WanGP\lali_pooli_reference\popcorn_8scenes_clean
Config: WanGP\settings\lali_pooli_VACE_9x16_outpaint_identity_17f.json
Model: Wan VACE 1.3B. Avoid simultaneous GPU jobs; GTX1060 6GB.
## Sources
https://github.com/deepbeepmeep/Wan2GP/blob/main/docs/VACE.md
https://github.com/deepbeepmeep/Wan2GP/blob/main/docs/PROCESSING.md
https://github.com/ali-vilab/VACE/blob/main/UserGuide.md
## Live test 2026-10-28 22:54 local
- New still successfully rendered at 576x1024 true 9:16 with Flux2 Klein 4B using approved current scene and vertical outpainting canvas. Candidate output: H:\RealJarvis\OptionalPlugins\WanGP\outputs\2026-10-28-22h52m43s_seed744230864_Generate one NEW professional 916 vertical 2D STO.jpg
- Visual QA: Lali and Pooli appear complete and roughly design-consistent, but TOP and BOTTOM background bands are visibly blurred. This still is a TEST REFERENCE, **not an approved final keyframe**. Must regenerate coherent sharp outpaint before release.
- Motion test: VACE 1.3B with same 9:16 candidate at first/last frames, 17 frames x 25 steps, config H:\RealJarvis\OptionalPlugins\WanGP\settings\LALI_POOLI_NEW_STILL_9x16_VACE_IDENTITY_TEST_17F.json; check model render log before accepting.
- Jarvis generator companion_reel_imagegen.py now uses 576x1024, current 9x16 scene reference instead of obsolete identity_lock_v1 character visuals, and rejects non-9:16 outputs. Output identity/anatomy still REQUIRES manual visual review.
- Never publish a still with blurred, stretched, empty or mirrored outpaint bands. Never classify pixel-color similarity alone as identity preservation. Inspect video frames 0,25,50,75,100 percent and actual playback for face drift, eyes, fur patterns, bow, outfit, paws, tails and prop separation.

## Animation identity QA 2026-10-28 23:02 (local)
- VACE 17-frame 9:16 identity test SUCCESS at technical encoding but FAIL on appearance: Pooli face markedly changes at midpoint (frame 9/17), then returns at 13-17. Review: WanGP\outputs\LALI_POOLI_9x16_QA_GRID.jpg. Video `2026-10-28-23h00m36s_seed744230864_Original 2D animation starting and ending on the s.mp4` is NOT ACCEPTED. Do not publish or use as canonical input.
- Same exact first and last frame DOES NOT GUARANTEE middle-frame identity. Future video generation must inspect intermediate 25/50/75% images.
- Guided VACE mask test next: settings\LALI_POOLI_VACE_9x16_MASK_ONLY_PAW_TEST.json, video_guide is a frozen 17-frame image, video_mask only opens a small region. Mask overlay currently includes part of Pooli bag, so inspect results carefully; a tighter mask may be necessary.
- Current 9:16 new still has blurred top and bottom background bands; not cleared for final production. Masking cannot fix bad unmasked borders. Need sharp native 9:16 source or true background-only outpainting.

## Mask experiment result 2026-10-28 23:10 local
- Video: WanGP\outputs\2026-10-28-23h09m49s_seed744230864_Preserve the exact original 916 cartoon scene and.mp4; VACE 1.3B, 17 frames at 16 FPS, 25 steps, output successful.
- Masked static guide preserved the unmasked area much better: mean absolute per-pixel difference outside mask 3.57/255, max frame 4.53/255 (includes lossy video encoding). In-mask deviation max 6.58/255. Visible 0/25/50/75/100 frame sheet `WanGP\outputs\LALI_POOLI_9x16_MASKED_QA_GRID.jpg`: Pooli face remains recognizably consistent across inspected frames, unlike prior unmasked midpoint failure.
- Tradeoff: animated paw movement is extremely small; current ellipse mask includes part of messenger bag. Current footage is STILL NOT publishable because the source image has blurred bands top and bottom and the action barely moves. Pixel differences cannot prove anatomy or identity quality.
- Next necessary technical improvement: precise segmented per-object mask (Pooli paw excluding his bag, plus separate independent eye/eyelid masks), guided animation start/end poses from canonical references, native 9:16 background generated cleanly, inspect real intermediate frames. Maintain full original illustration; do not animate cut-out body pieces.
- Jarvis image producer `companion_reel_imagegen.py` now uses current clean canonical reference, I mode and 576x1024 native output, with strict aspect validation. Syntax compiled; full eight-scene integration not yet tested.
