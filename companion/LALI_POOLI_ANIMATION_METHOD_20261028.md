# JARVIS: LALI & POOLI — SIMPLE 2D STORYBOARD ANIMATION (OWNER DIRECTIVE)
GOAL: independently create publishable short vertical reels with two ORIGINAL cute raccoons, inspired by the clarity, pastel charm and visual storytelling of Bubu and Dudu, NOT copied character designs.
OWNER APPROVES: draw as MANY full scene images as needed per video; do not cap frames at 6, 8, 20, or any fixed number. Quality and clarity first.
CHARACTERS: Lali is girl raccoon with pink bow; Pooli boy raccoon with blue hoodie/cap; unmistakable dark eye masks and ringed tails; consistent designs in all frames.
STYLE: soft pastel kawaii 2D illustration; simple shapes and clean readable compositions; no realistic 3D fur, Blender meshes, programmatic ellipses as final character art, or rigid cutout puppets.
PIPELINE:
1. Write a silent visual story: setup, entrance, discovery, emotional reaction, action, resolution. Specify exact door state, character positions, expressions and continuity per shot.
2. Produce a canonical front/side/three-quarter character sheet + expressions and approve appearance BEFORE any video render.
3. Generate or hand-draw each necessary COMPLETE frame or key pose with same identity and background; use any number of images. Prefer coherent redraws of full characters, not cropped limbs or rigid transforms.
4. Choose holds and timing based on comprehension. Use 2-4 key drawings for small expressions and 6-12+ for complex action as needed; no arbitrary limit.
5. Composite 9:16 video with coherent cuts, small camera moves, short sound cues and optional cute babble. No captions. Audio must not obscure the story.
6. QA at full size: compare characters against canonical sheets; verify closed door then OPEN door then entry; Lali notices, runs, embraces; no missing limbs, sliding, shape drift, teleporting without motivated cut.
7. If frames fail QA, REGENERATE THE ART, do not hide defects with transitions. Do not publish without owner review.
FIRST STORY: Pooli returns home, Lali notices him, runs to hug him, both cuddle. Create a shot list and each frame, then actual video.
CURRENT STATUS: previous Godot moving-SVG draft was rejected. A new high-quality 8-panel visual reference exists in the ChatGPT conversation but is NOT YET mounted on this PC. Do not claim to possess it; request a copy or recreate equivalent original artwork.
AUTONOMY: save successful character sheets, prompts, negative examples, per-frame seeds/refs, timing and QA outcomes in studio_library so next video reuses same identities.
## VERIFIED GENERATION TEST 2026-10-28
ComfyUI SD1.5 reference-conditioned Pooli generation SUCCEEDED via workflows/run_sd15_reference.py pooli; output:
H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\training\wholeframe_experiments\provider_studies\pooli_front_978e7f6f001a.png
Visually reviewed on primary display. Character is a recognizable raccoon with blue hoodie and striped tail, but too textured/realistic for owner's soft, simple, pastel kawaii storybook target. REJECT as final approved art. Need stronger flat illustration conditioning and reference consistency before multi-frame video.
Lali reference generation launched as detached AI Commander job 267b07ae25c31025. Verify result and visually review before claiming success.
## LALI TEST AND STYLE BLOCKER
ComfyUI SD1.5 img2img Lali completed: H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\training\wholeframe_experiments\provider_studies\lali_front_250f136af82b.png
Visually checked on main monitor. Lali has pink bow, dark mask, striped tail, but both generated raccoons have over-textured realistic fur, too much fine detail, and do not match the approved simple warm pastel storybook 8-panel art.
ROOT CAUSE: workflows/sd15_lali_reference_api.json and sd15_pooli_reference_api.json feed detailed existing reference images into VAEEncode with denoise=0.28; prompt alone cannot reliably override source visual style. Changing a few adjectives is not a credible fix. DO NOT iterate hundreds of frames from these masters.
NEXT ACTION: obtain a CLEAN, OWNER-APPROVED FLAT/STORYBOOK master reference for both characters; store and SHA lock it. Then use reference-conditioned pose generation with real image guidance and compare at least three poses and two expressions per character against masters. Reject identity drift. Only after QA attempt multi-frame scenes.
Current image generation proof: local img2img functional; style and identity consistency NOT verified; no publishable reel.
## PASTEL STYLE TEST RESULT
Test: workflows/run_pastel_style_test.py, config sd15_pooli_pastel_test_api.json; output:
H:\RealJarvis\OptionalPlugins\JarvisGodot2D\LaliPooli2D_Pilot\training\wholeframe_experiments\provider_studies\pooli_pastel_style_test_8aa44abe.png
Manual screen review: style converted from photorealistic fur to cleaner flat-color cartoon; however malformed cap/ear overlap, unnaturally elongated raised arm, inconsistent design relative to approved pastel storybook. NOT approved. Increased img2img denoise 0.67 improves style but loses identity and anatomy. Do NOT generate video from this image.
TECHNICAL LESSON: SD1.5 vanilla img2img with only prompt and denoise is inadequate for reliable character identity plus novel poses. Need original approved flat master and pose/reference control (e.g. ControlNet OpenPose + reference IP-Adapter or character-specific LoRA), or deliberate human/agent illustrated frame-by-frame workflow. Do not claim any of these are installed or validated.
## OWNER REJECTION — 2026-10-28 — HARD STOP
Owner saw pooli_ipadapter_style_test_9fd3f85a.png and rejected it explicitly: does NOT look like our raccoon. Manual review confirms the image is inconsistent with the approved cute pastel 8-panel Lali/Pooli storyboard. Reject this candidate and all previous photorealistic/SD1.5 candidate character masters for final reels. NO more blind parameter sweeps of the same source image. Do not auto-approve, animate, or publish rejected candidates.
Next prerequisite: obtain the exact approved 8-panel storyboard image as local file and make original character design masters matching its appearance, with explicit owner visual approval. Preserve original approved art and test candidates separately. IPAdapter installation works technically but is not proof of identity fidelity.
## DIRECT OWNER CORRECTION — TRACE, DO NOT GENERATE
JARVIS HIMSELF must trace the owner-approved visual reference. Do not ask ChatGPT to draw characters instead. Do NOT use SD1.5 / IPAdapter to hallucinate a new version of Lali or Pooli.
1. Import exact approved image into Krita as locked reference layer.
2. On a separate layer trace actual contours faithfully, including head shape, dark raccoon eye mask, ears, muzzle, tail rings, clothing, palette. No crude circles/ovals substituted for original contour.
3. Create faithful clean line-art and flat color layers; compare original and trace as an overlay at 50% opacity and fix mismatches.
4. Save editable source .kra and export PNG; show owner BOTH original and traced image side by side. Owner must approve before tracing poses or animation.
5. For additional poses, redraw/trace from original matching pose reference when available; do not distort or cut apart body parts.
BLOCKER: exact approved eight-panel reference is not yet verified to be available locally on this PC. Do not falsely claim it is. Obtain it before tracing.
