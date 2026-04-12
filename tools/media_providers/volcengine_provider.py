from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

from core.model_config import get_tool_temperature
from tools.media_providers.base import BaseMediaProvider
from tools.media_providers.registry import register_provider
from tools.volcengine_api import (
    _encode_image_to_data_uri,
    get_tool_vision_model_name,
    local_chat_completions,
    local_generate_image,
    local_generate_reference_image,
    local_generate_video,
    local_query_task_status,
)

_MOCK_TASKS: Dict[str, Dict[str, Any]] = {}


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


# ---------------------------------------------------------------------------
# System prompts — kept as module-level constants for readability
# ---------------------------------------------------------------------------

_SYS_ANALYZE_IMAGE_FULL = """\
You are a senior visual analyst, cinematographer, and prompt engineer. Analyze the provided image exhaustively and return a single valid JSON object (no markdown fences, no commentary).

Required top-level keys:

"meta": { "type" (photograph/illustration/3D render/etc.), "style", "quality", "version": "v2.0" }

"subject": If a person/character → include "demographics" (ethnicity, age_range, gender), "physical" (body_type, build, posture, skin { tone, texture, distinctive_marks }, face { shape, bone_structure, features, expression, micro_expressions, eyes { shape, color, expression, details }, eyebrows, nose, mouth, chin, cheeks }, hair { color, style, length, texture }), "clothing" (overall_style, formality_level, pieces { headwear, top, outer, bottom, accessories, jewelry, footwear }, materials, colors, patterns, condition, cultural_elements), "pose_action" (primary_action, body_language, hand_position, head_position, interaction, movement_implied). If an object → describe category, materials, dimensions, design_elements. If an animal → species, physical_characteristics, behavior.

"emotion_psychology": { "primary_emotion", "secondary_emotions" (array), "emotion_intensity" (1-10), "mood", "psychological_state", "backstory_implications" }

"environment": { "setting" (location_type, indoor_outdoor, urban_rural), "background" (description, complexity, depth), "architectural_elements" (if any), "props" (foreground_objects, background_objects, interactive_props), "atmosphere" (time_of_day, season, weather, temperature_feel, ambiance), "environmental_storytelling" (narrative_clues, symbolic_elements) }

"lighting": { "setup" (overall strategy), "key_light" (direction via clock position, hard/soft, height, color_temperature), "fill" (source, strength), "rim_or_back" (presence, intensity), "practicals" (visible light sources), "contrast" (high/medium/low), "highlight_placement" (array), "shadow_placement" (array), "lighting_pattern" (Rembrandt/butterfly/split/loop/broad/short if face visible) }

"composition": { "shot_type", "framing", "aspect_ratio", "camera_angle", "perspective", "depth_of_field", "focal_points" (array), "rule_of_thirds", "leading_lines", "symmetry", "visual_weight" }

"color_palette": { "dominant_colors" (array), "accent_colors" (array), "color_temperature", "saturation_level", "contrast_level", "color_harmony" }

"technical_details": { "camera_settings" { "focal_length", "aperture", "shutter_speed", "iso" }, "lens_characteristics" { "lens_type", "distortion", "vignetting" }, "post_processing" { "color_grading", "contrast_adjustment", "effects" (array) }, "image_quality" { "resolution", "sharpness", "noise_level", "dynamic_range" } }

"cinematic_references": { "genre" (array), "visual_style" (array), "mood_references" (array), "director_style", "film_era" }

"style_analysis": { "photography_style", "artistic_movement", "era_influence", "cultural_style", "genre", "technique" }

"prompt_bundle": { "prompt_en_flat" (single-paragraph English prompt that could recreate this image), "prompt_zh_flat" (中文等价), "negative" (array of things to avoid), "quality_keywords" (array) }

Be concrete, use film-industry terminology. Every string value must be descriptive — never leave a field as empty string or generic placeholder."""

_SYS_ANALYZE_IMAGE_CHARACTER = """\
You are a senior character designer and visual analyst. Analyze the character(s) in the provided image with extreme precision and return a single valid JSON object.

Required top-level keys:

"meta": { "type": "character_analysis", "style", "quality", "version": "v2.0" }

"subject": {
  "demographics": { "ethnicity", "age_range", "gender", "cultural_background" },
  "physical": {
    "body_type", "height", "build", "posture",
    "skin": { "tone", "texture", "condition", "distinctive_marks" },
    "face": { "shape", "bone_structure", "features", "expression", "micro_expressions",
      "eyes": { "shape", "color", "size", "expression", "details" },
      "eyebrows": { "shape", "thickness", "color" },
      "nose": { "shape", "size", "bridge" },
      "mouth": { "shape", "size", "expression" },
      "chin", "cheeks" },
    "hair": { "color", "style", "length", "texture", "condition", "styling" },
    "facial_hair": { "type", "style", "color" }
  },
  "clothing": {
    "overall_style", "formality_level",
    "pieces": { "headwear", "top", "outer", "bottom", "accessories", "jewelry", "footwear", "bags" },
    "materials", "colors", "patterns", "condition", "fit", "cultural_elements"
  },
  "pose_action": { "primary_action", "secondary_actions", "body_language", "hand_position", "leg_position", "head_position", "interaction", "movement_implied", "energy_level" }
}

"emotion_psychology": { "primary_emotion", "secondary_emotions" (array), "emotion_intensity" (1-10), "emotional_complexity", "mood", "psychological_state", "personality_hints", "backstory_implications", "motivation" }

"prompt_bundle": { "prompt_en_flat" (detailed English prompt to recreate this character), "prompt_zh_flat" (中文等价), "negative" (array), "quality_keywords" (array) }

Be exhaustive. Use specific descriptors — never say "normal" or "average". Every visible detail matters for downstream character consistency."""

_SYS_ANALYZE_IMAGE_ENV = """\
You are a senior production designer and environment artist. Analyze the environment/scene in the provided image with cinematic precision and return a single valid JSON object.

Required top-level keys:

"meta": { "type": "environment_analysis", "style", "quality", "version": "v2.0" }

"environment": {
  "setting": { "location_type", "specific_location", "indoor_outdoor", "urban_rural", "natural_artificial" },
  "geography": { "terrain", "elevation", "climate_zone", "water_features", "vegetation": { "type", "density", "species", "seasonal_state" } },
  "architectural_elements": { "building_style", "structural_elements", "materials", "age_period", "condition", "cultural_markers" },
  "props": { "foreground_objects", "background_objects", "decorative_elements", "functional_items" },
  "atmosphere": { "time_of_day", "season", "weather", "temperature_feel", "humidity_level", "ambiance", "noise_level_visual_hint" },
  "spatial_relationship": { "scale_relationship", "depth_cues", "integration_level" },
  "environmental_storytelling": { "narrative_clues", "mood_enhancement", "symbolic_elements", "contextual_meaning" }
}

"lighting": {
  "natural_lighting": { "sun_position", "sun_angle", "sky_condition", "cloud_cover", "atmospheric_effects" },
  "artificial_lighting": { "street_lights", "building_lights", "decorative_lighting", "practical_sources" },
  "lighting_quality": { "direction", "intensity", "color_temperature", "contrast", "shadows", "volumetric_light" }
}

"composition": { "perspective", "viewpoint", "horizon_line", "foreground", "middle_ground", "background", "depth_cues", "focal_points" (array), "leading_lines", "framing_elements" }

"color_palette": { "dominant_colors" (array), "seasonal_colors" (array), "natural_colors" (array), "color_temperature", "saturation_level", "color_harmony" }

"mood_atmosphere": { "emotional_tone", "ambiance", "energy_level", "tranquility_level", "mystery_level", "drama_level" }

"prompt_bundle": { "prompt_en_flat" (single-paragraph English prompt to recreate this environment), "prompt_zh_flat" (中文等价), "negative" (array), "quality_keywords" (array) }

Use concrete film-industry and architecture terminology. Be specific about materials, weathering, light quality."""

_SYS_DESIGN_CHARACTER = """\
You are a senior character designer for film, animation, and game production. Design a character suitable for AI image generation on a CLEAN WHITE BACKGROUND (character design sheet style).

Return a single valid JSON object with these keys:

"prompt": (string) A detailed English prompt for a text-to-image model. MUST include:
  - "clean white background, single character, full body concept art, 9:16"
  - Complete physical description: face shape, eyes, nose, mouth, skin tone, body type, height impression, build
  - Hair: color, style, length, texture, any styling details
  - Clothing layers: headwear, top, outer layer, bottom, footwear — each with material, color, pattern, fit
  - Accessories & props: by default include only wearable or body-attached accessories that do not add extra subjects or handheld props; weapons, mounts, companions, pets, vehicles, or large handheld props are forbidden unless the user explicitly requests a complete character sheet variant
  - Pose: default standing pose with slight character-revealing attitude
  - Style directive matching the requested art style
  - Quality tags: "ultra detailed, 8k, masterpiece, professional character concept art"

"description": (string) 中文详细描述，包含角色的完整视觉设计、性格暗示、服装设计理念、文化元素解读

"character_sheet_notes": {
  "color_palette": { "primary" (array), "secondary" (array), "accent" (array) },
  "design_keywords": (array of 8-12 design keywords),
  "silhouette_description": (string — how the character reads as a silhouette),
  "cultural_references": (string),
  "personality_through_design": (string — how visual elements convey personality)
}

"negative": (array) Elements to avoid: "complex background", "multiple characters", "multi-view sheet", "turnaround sheet", "pose sheet", "expression sheet", "collage", "text", "watermark", "blurry", "deformed hands", "extra fingers", "anatomical errors"

CRITICAL: The prompt MUST explicitly describe a single full-body character on a pure white background in 9:16 vertical composition. Never output multi-view sheets, turnaround sheets, expression sheets, pose sheets, lineups, or repeated copies of the same character in one image."""

_SYS_DESIGN_SCENE = """\
You are a senior production designer and concept artist for film and animation. Design an environment/scene suitable for AI image generation.

Return a single valid JSON object with these keys:

"prompt": (string) A detailed English prompt for a text-to-image model. MUST include:
  - Location type and specific setting description
  - Architectural style, materials, weathering, age indicators
  - Natural elements: terrain, vegetation, water, sky condition
  - Time of day with specific light quality description
  - Atmospheric conditions: weather, fog, dust, humidity
  - Foreground, middle-ground, background layer descriptions
  - Key props and set dressing details
  - Camera/composition: suggested shot type, perspective, focal length feel
  - Lighting setup: key light direction (clock position), quality (hard/soft), color temperature, fill source, volumetric effects
  - Mood descriptors: 5-8 atmosphere keywords
  - Style directive matching the requested art style
  - Quality tags: "ultra detailed, 8k, masterpiece, cinematic environment concept art, production design"

"description": (string) 中文详细描述，包含场景的空间布局、光影设计、氛围营造、叙事功能、文化背景

"environment_design_notes": {
  "color_palette": { "dominant" (array), "accent" (array), "mood_colors" (array) },
  "lighting_plan": { "key_light", "fill", "practicals", "atmosphere_light", "time_of_day_logic" },
  "spatial_layers": { "foreground", "middle_ground", "background", "sky" },
  "mood_keywords": (array of 6-10 descriptors),
  "cinematic_reference": (string — film/director reference for visual tone),
  "narrative_function": (string — what story purpose this scene serves)
}

"negative": (array) Elements to avoid: "text", "watermark", "UI elements", "blurry", "low quality", "oversaturated"

Use concrete, film-industry terminology. Describe light like a cinematographer, space like an architect."""

_SYS_DESIGN_PROP = """\
You are a senior prop designer and concept artist for film, animation, and game production. Design a prop/object suitable for AI image generation.

Return a single valid JSON object with these keys:

"prompt": (string) A detailed English prompt for a text-to-image model. MUST include:
  - Object type and specific name/function
  - Overall form: shape, proportions, geometric properties, silhouette
  - Primary material with surface treatment (brushed metal, worn leather, polished wood, etc.)
  - Secondary materials and how they combine
  - Color scheme with specific shades (not just "red" but "deep crimson with aged patina")
  - Surface details: engravings, wear marks, scratches, patina, rust, stains
  - Functional elements: mechanisms, joints, handles, blades, buttons
  - Cultural/era indicators: design period, artistic movement, regional influence
  - Scale reference (if helpful)
  - Lighting setup for product-shot quality: studio lighting, soft shadows, gradient background
  - Style directive matching the requested art style
  - Quality tags: "ultra detailed, 8k, masterpiece, professional prop concept art, product photography quality"

"description": (string) 中文详细描述，包含道具的设计理念、材质工艺、文化象征、叙事功能

"prop_design_notes": {
  "materials": { "primary", "secondary", "accents" },
  "dimensions_feel": (string — sense of weight, scale, heft),
  "cultural_context": { "origin", "era", "symbolic_meaning" },
  "wear_and_history": (string — how the prop shows its age/use),
  "interaction_design": (string — how a character would hold/use it),
  "design_keywords": (array of 6-10 keywords)
}

"negative": (array) Elements to avoid: "blurry", "low detail", "text", "watermark", "floating", "incorrect proportions"

Make materials feel tangible — describe how light interacts with each surface."""

_SYS_BREAKDOWN_STORYBOARD = """\
You are an award-winning trailer director, cinematographer, and storyboard artist. Break down the given script into a professional storyboard sequence.

Return a single valid JSON object with these keys:

"story_analysis": {
  "theme": (string — one-sentence theme),
  "logline": (string — one-sentence trailer-style logline),
  "emotional_arc": { "setup", "escalation", "climax", "resolution" — one sentence each },
  "visual_anchors": (array of 3-6 visual consistency anchors: color tone, key props, lighting logic, weather)
}

"cinematic_approach": {
  "shot_progression_strategy": (string — how shots build from wide to close or reverse),
  "camera_movement_plan": (string — movement palette: dolly, crane, handheld, gimbal, etc.),
  "lens_and_exposure": (string — focal length range, depth-of-field tendency, shutter feel),
  "light_and_color": (string — contrast, dominant palette, texture, grain)
}

"segments": (array) Each segment object MUST contain:
  - "shot_id": (string, e.g. "S01")
  - "description": (string — concise visual description of the beat)
  - "duration_seconds": (number)
  - "shot_type": (string — extreme wide / wide / medium wide / medium / medium close-up / close-up / extreme close-up / insert)
  - "camera_height": (string — eye level / low angle / high angle / bird's eye / worm's eye)
  - "camera_movement": (string — static / slow push-in / dolly track / pan / tilt / crane up / handheld shake / orbit)
  - "lens_mm": (number — focal length in mm)
  - "depth_of_field": (string — shallow / medium / deep)
  - "composition_technique": { "id" (1-7), "name" (Rule of thirds / Golden ratio / Symmetry / Diagonal / Leading lines / Framing / Center composition), "execution" (how it's applied) }
  - "lighting_prompt": (string — specific lighting for this shot: key light direction, fill, rim, contrast level, highlight/shadow placement, mood)
  - "lighting_keywords": (array of 5-8 lighting terms)
  - "action_beat": (string — what visibly happens)
  - "sound_atmos": (string — one-sentence audio atmosphere)
  - "emotional_beat": (string — which arc node: setup/escalation/climax/resolution)

Hard requirements for the segments array:
- MUST include at least 1 wide establishing shot, 1 close-up, 1 extreme close-up, 1 dynamic angle (low/high)
- At least 5 different composition techniques must appear across the sequence
- Total durations must sum to approximately the target duration
- Maintain 180-degree rule and eyeline match logic between consecutive shots
- Lighting must be internally consistent (same time of day, same key light logic) while allowing per-shot variation in contrast/rim/fill"""

_SYS_KEYFRAME_PROMPTS = """\
You are a senior cinematographer and visual prompt engineer. Generate exhaustive keyframe image prompts for AI image generation from the given storyboard segments.

Return a single valid JSON object with key "prompts" — an array where each element contains:

"shot_id": (string, matching the segment)

"prompt": (string) A complete English prompt for text-to-image generation. This MUST be a single dense paragraph that fuses ALL of:
  - Subject(s): precise appearance, clothing, pose, action, expression, gaze direction
  - Environment: location details, foreground/middle/background layers, props, set dressing
  - Lighting: key light (direction as clock position, hard/soft, height), fill (source and strength), rim/back light (presence), practicals (visible sources), contrast level, highlight and shadow placement
  - Composition: shot type, camera angle, focal length, depth of field, composition technique name
  - Atmosphere: weather, time of day, mood descriptors, volumetric effects (fog, dust, rain)
  - Style: art style, film reference, color palette, grain/texture
  - Technical: aspect ratio, quality tags (ultra detailed, 8k, masterpiece, cinematic)

"keyframe_json": (object) The exhaustive structured prompt with these exact keys:
  "meta": { "type": "cinematic_keyframe_prompt", "style", "quality", "version": "v2.0", "keyframe_id", "suggested_duration_s", "shot_scale", "composition_technique": { "id" (1-7), "name_en", "name_zh", "execution_notes" } }
  "subject" or "subjects" (array if multiple): { "name", "physical": { "face", "expression", "hair", "build" }, "clothing": { "top", "headwear", "style", "accessories" }, "pose_action" }
  "props": (array) [{ "name", "material", "state", "interaction_with_subject" }]
  "environment": { "location", "time_of_day", "weather", "details", "background", "atmosphere" (array of mood words) }
  "lighting": { "setup", "key_light", "fill", "rim_or_back", "practicals" (array), "contrast" (high/medium/low), "highlight_placement" (array), "shadow_placement" (array), "continuity_note" }
  "composition": { "shot_type", "framing", "aspect_ratio", "focal_point" (array), "leading_lines_or_frame", "screen_direction" }
  "technical_style": { "camera" (focal length, aperture, height, movement), "depth_of_field" (shallow/medium/deep + focus target), "effects" (grain, haze, volumetric), "rendering" }
  "prompt_bundle": { "prompt_zh_flat" (single-paragraph Chinese prompt with aspect ratio), "prompt_en_flat" (English equivalent), "lighting_keywords" (comma-separated string), "negative": ["text overlay", "watermark", "deformed hands", "extra fingers", "blurry"] }

Ensure composition_technique.id uses: 1=Rule of thirds, 2=Golden ratio, 3=Symmetry, 4=Diagonal, 5=Leading lines, 6=Framing, 7=Center composition.
At least 5 different techniques must appear across the sequence. Lighting MUST vary per shot while maintaining overall consistency."""

_SYS_VIDEO_PROMPTS = """\
You are a senior motion director and video prompt engineer specializing in AI video generation (Seedance 2.0 / Kling / Sora class models).

Generate video generation prompts using professional storyboard-script format with time codes.

Return a single valid JSON object with key "prompts" — an array where each element contains:

"shot_id": (string, matching the segment)

"prompt": (string) A complete video prompt in storyboard-script format. Structure:

【Style】{Specific style anchor — name a director, film, or art movement. NEVER use vague "cinematic"}
【Duration】{duration} seconds

[00:00-00:XX] Shot: {Shot Name} ({Shot Type}).
{Scene description with PHYSICAL details — describe what physically happens, not abstract concepts.}
{Character action with specific body language — limb positions, gaze direction, facial micro-expressions.}
{Camera movement instruction — "camera slowly pushes in from medium to close-up" / "tracking shot follows subject left to right" / "static wide shot, slight handheld shake".}
{Sound/atmosphere cue.}

{Consistency constraints: same character design, same lighting logic, realistic physics.}

"motion_keywords": (array of 5-8 motion/camera terms for this shot)

"camera_instruction": {
  "movement_type": (static / push-in / pull-back / pan / tilt / tracking / orbit / crane / handheld),
  "speed": (slow / medium / fast),
  "start_framing": (wide / medium / close-up),
  "end_framing": (wide / medium / close-up),
  "special_effect": (none / slow-motion / speed-ramp / rack-focus / dolly-zoom)
}

Key rules:
- ALWAYS use specific time codes [00:00-00:XX] — never leave timing vague
- ALWAYS anchor style to a specific director/film reference, not generic "cinematic"
- Describe PHYSICAL actions: "dust particles float in slow motion" not "atmospheric feel"
- Each shot prompt must specify camera movement explicitly
- End with consistency constraints for character/lighting/physics continuity
- Keep each shot segment to 3-5 seconds maximum for best AI video generation results"""

_SYS_MULTI_VIEW = """\
You are a professional character layout-sheet artist. Generate a single 16:9 multi-view character board based strictly on reference image 1.

Layout requirements:
- The output is one single collage image in 16:9 ratio
- Left 1/3: one large frontal face close-up portrait
- Right 2/3: three full-body columns in this exact order: front view, 3/4 side view, back view
- No dividing lines, no labels, no text, no watermark, no UI elements

Panel requirements:
- Left 1/3 portrait: frontal close-up, face occupies a large area, complete head silhouette visible, hair must never be cropped out of frame, facial features and hairstyle details must be crisp
- Right column 1: front full-body view, character fully visible from head to shoes, hairstyle and footwear fully shown
- Right column 2: 3/4 side full-body view, character fully visible from head to shoes, hairstyle and footwear fully shown
- Right column 3: back full-body view, character fully visible from head to shoes, hairstyle and footwear fully shown

Consistency requirements:
- All four panels must depict the exact same character identity, outfit, color palette, body proportions, and art style
- Character identity, hairstyle, clothing design, accessories, and color design must follow reference image 1
- Do not change the character's identity
- Do not add props, weapons, extra accessories, extra characters, or environmental storytelling elements
- Use only a plain neutral background; if no neutral background is specified upstream, use a clean white studio background
- Maintain clean production-sheet readability, soft studio lighting, full-body completeness, and high material detail"""

_SYS_EXPRESSION_SHEET = """\
You are a professional character expression-sheet artist. Generate a single-image 3x3 expression board based strictly on reference image 1.

Layout requirements:
- One single image only
- 3x3 grid layout with nine expression panels
- No dividing lines, no labels, no text, no watermark, no UI elements

Panel requirements:
- Each panel is a close-up portrait showing head and upper shoulders only
- Every panel must include a complete head silhouette; hair must never be cropped out of frame
- Facial features, hairstyle, hairline, eyebrow shape, eye shape, nose, mouth, jawline, and skin tone must remain consistent across all nine panels

Required expressions in order:
- Row 1: neutral, happy, laughing
- Row 2: sad, angry, surprised
- Row 3: fearful, disgusted, determined

Consistency requirements:
- All nine panels must depict the exact same character identity, same hairstyle, same outfit neckline/visible accessories, same color palette, and same art style
- Character identity, face design, hairstyle, clothing hints, and accessories must follow reference image 1
- Do not change the character's identity
- Do not add props, weapons, extra accessories, extra characters, or environmental storytelling elements
- Use only a plain neutral background; if no neutral background is specified upstream, use a clean white studio background
- Maintain soft even studio lighting, crisp facial readability, and strong micro-expression clarity"""

_SYS_POSE_SHEET = """\
You are a professional character pose-sheet artist. Generate a single-image 16:9 pose board based strictly on reference image 1.

Layout requirements:
- One single image only
- 3x2 or 3x3 grid layout with clean production-sheet readability
- No dividing lines, no labels, no text, no watermark, no UI elements

Required poses:
- idle standing
- walking mid-stride
- running or sprinting
- signature action pose
- seated or resting pose
- iconic power pose

Panel requirements:
- Every pose must show the complete body from head to shoes
- Hair, hands, feet, footwear, and silhouette must be fully visible and never cropped
- The line of action must be clear and readable in every dynamic pose

Consistency requirements:
- All panels must depict the exact same character identity, outfit, color palette, hairstyle, body proportions, and art style
- Character identity, hairstyle, clothing design, accessories, and color design must follow reference image 1
- Do not change the character's identity
- Do not add props, weapons, extra accessories, extra characters, or environmental storytelling elements unless they already belong to the base design shown in reference image 1
- Use only a plain neutral background; if no neutral background is specified upstream, use a clean white studio background
- Maintain soft studio lighting, full-body completeness, clean anatomy, and realistic cloth/hair reaction to movement"""


@register_provider("volcengine_ark")
class VolcengineArkMediaProvider(BaseMediaProvider):
    supports_multi_view: bool = True
    supports_expression: bool = True
    supports_pose: bool = True
    supports_reference: bool = True

    def _call_llm_json(self, system_prompt: str, user_prompt: str, tool_name: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            resp = local_chat_completions(
                messages, temperature=get_tool_temperature(tool_name),
            )
            content = resp["choices"][0]["message"]["content"]
            return json.loads(_strip_json_fences(content))
        except Exception as e:
            return {"error": str(e), "raw_response": resp if "resp" in locals() else None}

    def _call_vision_llm_json(
        self, system_prompt: str, user_text: str, image_url: str,
    ) -> Dict[str, Any]:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": image_url},
                    {"type": "input_text", "text": f"{system_prompt}\n\n{user_text}"}
                ]
            }
        ]

        try:
            resp = local_chat_completions(
                messages=messages,
                model=get_tool_vision_model_name(),
                temperature=get_tool_temperature("VISION_ANALYZER"),
                is_vision=True
            )
            
            # The API might return different structures depending on the endpoint used for visual models.
            # We'll check for chat completions style first, then fallback to typical response style if needed.
            
            if "choices" in resp and len(resp["choices"]) > 0:
                msg = resp["choices"][0].get("message", {})
                content_obj = msg.get("content", "")
                
                if isinstance(content_obj, list):
                    text_parts = []
                    for part in content_obj:
                        if isinstance(part, dict) and part.get("type") == "output_text":
                            text_parts.append(part.get("text", ""))
                        elif isinstance(part, dict) and part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                    content = "\n".join(text_parts) if text_parts else str(content_obj)
                else:
                    content = str(content_obj)
            elif "output" in resp and "text" in resp["output"]:
                content = resp["output"]["text"]
            else:
                content = str(resp)
            return json.loads(_strip_json_fences(content))
        except Exception as e:
            return {"error": str(e), "raw_response": resp if "resp" in locals() else None}

    # ------------------------------------------------------------------
    # Core generation (unchanged API calls)
    # ------------------------------------------------------------------

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        resp = local_generate_image(
            prompt=prompt, aspect_ratio=aspect_ratio, input_images=input_images,
        )
        if "urls" in resp:
            # It's a mock task from synchronous generation
            task_id = resp["task_id"]
            _MOCK_TASKS[task_id] = {
                "task_id": task_id,
                "status": "completed",
                "result": {"urls": resp["urls"], "url": resp["urls"][0] if resp["urls"] else None}
            }
            return {"task_id": task_id}
        return resp

    def generate_video(
        self,
        prompt: str,
        input_images: Optional[List[str]] = None,
        duration: int = 12,
        aspect_ratio: str = "16:9",
        generate_audio: bool = True,
    ) -> Dict[str, Any]:
        return local_generate_video(
            prompt=prompt,
            input_images=input_images,
            duration=duration,
            aspect_ratio=aspect_ratio,
            generate_audio=generate_audio,
        )

    def query_task_status(self, task_id: str) -> Dict[str, Any]:
        if task_id in _MOCK_TASKS:
            return _MOCK_TASKS[task_id]
        return local_query_task_status(task_id)

    def generate_reference_image(
        self,
        prompt: str,
        entity_type: str,
        reference_variant: str = "pure_character",
        aspect_ratio: str = "",
        input_images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return local_generate_reference_image(
            prompt=prompt,
            entity_type=entity_type,
            reference_variant=reference_variant,
            aspect_ratio=aspect_ratio,
            input_images=input_images,
        )

    # ------------------------------------------------------------------
    # Multi-view / Expression / Pose sheets
    # ------------------------------------------------------------------

    def generate_multi_view(
        self, prompt: str, character_name: str, ref_image: str,
    ) -> Dict[str, Any]:
        full_prompt = (
            f"{prompt}\n"
            f"根据输入图1中 {character_name} 的角色参考图，生成角色多视图拼图（单张图，16:9）。 "
            "左侧 1/3 是角色大脸特写照，右侧 2/3 依次是角色的正面全身照、3/4 侧面全身照、背面全身照。 "
            "无任何分割线，无文字，无标签，无水印，无 UI 元素。 "
            "背景必须保持纯净的中性背景；如果上游提示词没有明确指定其他中性背景，则使用干净的白色摄影棚背景。 "
            "左侧特写必须是正面视角，脸部占大比例，务必包含完整头部轮廓，头发不得被裁切出画框，清晰展示五官与发型细节。 "
            "右侧三列必须全部从头到脚完整展示，包含完整发型和鞋子，不得裁切四肢，不得遗漏鞋面或鞋底。 "
            "四个视图必须是同一角色、同一服饰与配色、同一画风、同一身份设定。 "
            "造型、画风、着装、发型、配饰都严格参考输入图1，不得改变角色身份，不得新增道具、武器、挂件、额外角色或场景叙事元素。 "
            "强调 production-ready character layout sheet、consistent design across all views、white or neutral plain background、full body completeness、4K、high quality、ultra detailed、masterpiece。"
        )
        return self.generate_image(
            full_prompt,
            aspect_ratio="16:9",
            input_images=[ref_image] if ref_image else None,
        )

    def generate_expression_sheet(
        self, prompt: str, character_name: str, ref_image: str,
    ) -> Dict[str, Any]:
        full_prompt = (
            f"{prompt}\n"
            f"根据输入图1中 {character_name} 的角色参考图，生成角色表情设定拼图（单张图，3x3）。 "
            "单张图共九格，顺序固定为：第一行 neutral / happy / laughing；第二行 sad / angry / surprised；第三行 fearful / disgusted / determined。 "
            "无任何分割线，无文字，无标签，无水印，无 UI 元素。 "
            "每一格都必须是角色头部到上肩的近景特写，务必包含完整头部轮廓，头发不得裁切出画框。 "
            "九格必须保持同一角色身份、同一发型、同一发色、同一服装领口与可见配饰、同一画风与配色。 "
            "五官结构、发际线、眉形、眼型、鼻子、嘴型、下颌线都要严格参考输入图1，不得改变角色身份。 "
            "每个表情必须通过清晰的微表情差异体现：眉毛位置、眼睑开合、嘴角弧度、鼻翼、脸颊紧张度。 "
            "不得新增道具、武器、挂件、额外角色或环境叙事元素。 "
            "背景必须保持纯净的中性背景；如果上游提示词没有明确指定其他中性背景，则使用干净的白色摄影棚背景。 "
            "强调 production-ready expression sheet、consistent design across all panels、complete head silhouette、ultra detailed facial features、4K、high quality、masterpiece。"
        )
        return self.generate_image(
            full_prompt,
            aspect_ratio="1:1",
            input_images=[ref_image] if ref_image else None,
        )

    def generate_pose_sheet(
        self, prompt: str, character_name: str, ref_image: str,
    ) -> Dict[str, Any]:
        full_prompt = (
            f"{prompt}\n"
            f"根据输入图1中 {character_name} 的角色参考图，生成角色姿势设定拼图（单张图，16:9）。 "
            "采用 3x2 或 3x3 的多格布局，至少包含六个姿势，顺序优先为：idle standing、walking mid-stride、running/sprinting、signature action pose、seated/resting pose、iconic power pose。 "
            "无任何分割线，无文字，无标签，无水印，无 UI 元素。 "
            "每一格都必须完整展示角色从头到脚的全身，包含完整发型、双手、双脚和鞋子，不得裁切肢体，不得遗漏鞋面或鞋底。 "
            "所有格子必须是同一角色、同一服饰与配色、同一发型、同一体型比例、同一画风。 "
            "造型、画风、着装、发型、配饰都严格参考输入图1，不得改变角色身份。 "
            "不得新增道具、武器、挂件、额外角色或环境叙事元素；除非该元素已经属于输入图1中的基础角色设计。 "
            "动作可以变化，但角色设定不能漂移；动态姿势必须具备清晰的动作线、自然重心、合理的布料与头发运动反馈。 "
            "背景必须保持纯净的中性背景；如果上游提示词没有明确指定其他中性背景，则使用干净的白色摄影棚背景。 "
            "强调 production-ready pose sheet、consistent design across all panels、full body completeness、clear silhouette readability、4K、high quality、ultra detailed、masterpiece。"
        )
        return self.generate_image(
            full_prompt,
            aspect_ratio="16:9",
            input_images=[ref_image] if ref_image else None,
        )

    # ------------------------------------------------------------------
    # Design methods (LLM-powered)
    # ------------------------------------------------------------------

    def design_character(
        self,
        character_name: str,
        character_brief: str,
        style: str,
        story_context: str = "",
        reference_variant: str = "pure_character",
    ) -> Dict[str, Any]:
        normalized_variant = (reference_variant or "pure_character").strip().lower()
        if normalized_variant in {"full", "full_character", "full_character_sheet", "complete", "complete_character"}:
            variant_rule = (
                "角色参考图模式：完整角色设定图。可以包含明确要求的标志性武器或 hand-held props，"
                "但不要加入坐骑、伴生体或额外角色，除非用户再次明确要求。"
            )
        elif normalized_variant in {"mounted", "with_mount", "mount", "mounted_character"}:
            variant_rule = (
                "角色参考图模式：带坐骑/伴生体的完整角色设定图。允许保留明确要求的坐骑、伴生体与标志性武器，"
                "但角色仍必须是第一视觉主体，不要加入其他额外角色。"
            )
        else:
            variant_rule = (
                "角色参考图模式：默认纯人物参考图。提示词中不得出现武器、坐骑、宠物、伴生体、额外角色、交通工具、"
                "大型手持道具或单独特写道具；只保留人物本体、服装、发型、体态和必要的穿戴式配饰。"
            )
        user_prompt = (
            f"角色名称：{character_name}\n"
            f"角色简介：{character_brief}\n"
            f"风格：{style}\n"
            f"背景故事：{story_context}\n"
            f"参考图版本：{normalized_variant}\n"
            f"参考图约束：{variant_rule}\n\n"
            "请设计这个角色的完整视觉形象。"
            "提示词中必须包含 'clean white background, character design sheet'。"
        )
        return self._call_llm_json(_SYS_DESIGN_CHARACTER, user_prompt, "DESIGN_CHARACTER")

    def design_scene(
        self, scene_name: str, scene_brief: str, style: str,
        story_context: str = "",
    ) -> Dict[str, Any]:
        user_prompt = (
            f"场景名称：{scene_name}\n"
            f"场景简介：{scene_brief}\n"
            f"风格：{style}\n"
            f"背景故事：{story_context}\n\n"
            "请设计这个场景的完整视觉概念。"
            "用灯光师的语言描述光影，用建筑师的语言描述空间。"
        )
        return self._call_llm_json(_SYS_DESIGN_SCENE, user_prompt, "DESIGN_SCENE")

    def design_prop(
        self, prop_name: str, prop_brief: str, style: str,
        story_context: str = "",
    ) -> Dict[str, Any]:
        user_prompt = (
            f"道具名称：{prop_name}\n"
            f"道具简介：{prop_brief}\n"
            f"风格：{style}\n"
            f"背景故事：{story_context}\n\n"
            "请设计这个道具的完整视觉概念。"
            "描述材质时要让人能感受到光线与表面的交互。"
        )
        return self._call_llm_json(_SYS_DESIGN_PROP, user_prompt, "DESIGN_PROP")

    # ------------------------------------------------------------------
    # Storyboard & prompts (LLM-powered)
    # ------------------------------------------------------------------

    def breakdown_storyboard(
        self, script: str, aspect_ratio: str, style: str, target_duration: float,
    ) -> Dict[str, Any]:
        user_prompt = (
            f"剧本/故事：\n{script}\n\n"
            f"画面比例：{aspect_ratio}\n"
            f"风格：{style}\n"
            f"目标总时长（秒）：{target_duration}\n\n"
            "请按照系统提示词中的专业标准进行分镜拆解。\n"
            "确保：\n"
            "1. 包含至少1个环境建立广角镜头、1个近景特写、1个大特写、1个动态角度（低角度或高角度）\n"
            "2. 至少覆盖5种不同的构图技法\n"
            "3. 总时长之和约等于目标时长\n"
            "4. 保持180度规则和视线匹配的剪辑逻辑\n"
            "5. 情绪弧线清晰：铺垫→升级→转折→收尾"
        )
        return self._call_llm_json(_SYS_BREAKDOWN_STORYBOARD, user_prompt, "BREAKDOWN_STORYBOARD")

    def generate_keyframe_prompts(
        self, segments: List[Any], entity_names: List[str],
        aspect_ratio: str, style: str,
    ) -> Dict[str, Any]:
        user_prompt = (
            f"分镜列表：\n{json.dumps(segments, ensure_ascii=False, indent=2)}\n\n"
            f"包含实体（角色/道具/场景）：{json.dumps(entity_names, ensure_ascii=False)}\n"
            f"画面比例：{aspect_ratio}\n"
            f"风格：{style}\n\n"
            "为每个分镜生成穷尽式关键帧提示词。\n"
            "要求：\n"
            "1. prompt 字段必须是可直接喂给文生图模型的完整英文提示词\n"
            "2. keyframe_json 必须包含完整的 meta/subject/environment/lighting/composition/technical_style/prompt_bundle\n"
            "3. lighting 必须具体到主光方向(clock position)、硬柔、补光来源、轮廓光有无、光比、高光与阴影落点\n"
            "4. composition_technique 必须从七种电影构图技法中选择并说明如何落地\n"
            f"5. 画面比例 {aspect_ratio} 必须在 prompt 和 prompt_bundle 中重复强调"
        )
        return self._call_llm_json(_SYS_KEYFRAME_PROMPTS, user_prompt, "GENERATE_KEYFRAME_PROMPTS")

    def generate_video_prompts(
        self, segments: List[Any], entity_names: List[str],
        aspect_ratio: str, style: str,
    ) -> Dict[str, Any]:
        user_prompt = (
            f"分镜列表：\n{json.dumps(segments, ensure_ascii=False, indent=2)}\n\n"
            f"包含实体（角色/道具/场景）：{json.dumps(entity_names, ensure_ascii=False)}\n"
            f"画面比例：{aspect_ratio}\n"
            f"风格：{style}\n\n"
            "为每个分镜生成专业视频生成提示词（分镜脚本格式 + 时间码）。\n"
            "要求：\n"
            "1. 使用【Style】和【Duration】标头 + [00:00-00:XX] 时间码格式\n"
            "2. 风格锚点必须具体到导演/电影/艺术流派，禁止使用泛化的'cinematic'\n"
            "3. 描述物理动作而非抽象概念：'dust particles float in slow motion' 而非 'atmospheric feel'\n"
            "4. 每个镜头必须明确指定镜头运动方式和速度\n"
            "5. 以一致性约束结尾：角色设计/光影逻辑/物理效果的连贯性\n"
            "6. 每个镜头片段控制在3-5秒以内"
        )
        return self._call_llm_json(_SYS_VIDEO_PROMPTS, user_prompt, "GENERATE_VIDEO_PROMPTS")

    # ------------------------------------------------------------------
    # Image analysis (Vision LLM)
    # ------------------------------------------------------------------

    def analyze_image(
        self, image_url_or_path: str, analyze_type: str,
    ) -> Dict[str, Any]:
        analyze_type_upper = analyze_type.upper() if analyze_type else ""

        if analyze_type_upper == "FULL":
            system_prompt = _SYS_ANALYZE_IMAGE_FULL
            user_text = (
                "Analyze this image exhaustively. Produce a complete JSON covering: "
                "meta, subject, emotion_psychology, environment, lighting (with key_light direction, "
                "fill, rim, contrast, highlight/shadow placement), composition, color_palette, "
                "technical_details, cinematic_references, style_analysis, and prompt_bundle. "
                "Be concrete and specific — use film-industry terminology for lighting and "
                "photography terminology for technical details."
            )
        elif analyze_type_upper == "CHARACTER":
            system_prompt = _SYS_ANALYZE_IMAGE_CHARACTER
            user_text = (
                "Extract every visible character detail from this image. Produce a complete JSON covering: "
                "demographics, full physical description (face bone structure, skin texture, "
                "eye shape/color/expression, nose bridge, mouth shape, chin, cheeks, hair texture/style), "
                "complete clothing analysis (each garment layer, materials, colors, patterns, fit, "
                "cultural elements), pose and body language, emotion/psychology analysis, "
                "and a prompt_bundle with flat prompts that could recreate this character."
            )
        elif analyze_type_upper == "ENVIRONMENT":
            system_prompt = _SYS_ANALYZE_IMAGE_ENV
            user_text = (
                "Analyze the environment and scene in this image with production-designer precision. "
                "Produce a complete JSON covering: setting (location type, indoor/outdoor, urban/rural), "
                "geography and terrain, architectural elements (style, materials, period, condition), "
                "props, atmosphere (time of day, season, weather, temperature feel), "
                "lighting (natural and artificial sources, direction, color temperature, volumetric effects), "
                "composition (perspective, layers, focal points), color palette, "
                "mood/atmosphere, and a prompt_bundle for recreation."
            )
        else:
            system_prompt = _SYS_ANALYZE_IMAGE_FULL
            user_text = (
                "Provide a comprehensive analysis of this image. "
                "Return a structured JSON covering all visible elements: "
                "subject, environment, lighting, composition, color, style, and prompt_bundle."
            )

        if not image_url_or_path.startswith(("http", "data:image")):
            if os.path.exists(image_url_or_path):
                image_url_or_path = _encode_image_to_data_uri(image_url_or_path)

        result = self._call_vision_llm_json(system_prompt, user_text, image_url_or_path)

        if "error" not in result:
            task_id = f"mock_task_{uuid.uuid4().hex}"
            _MOCK_TASKS[task_id] = {
                "task_id": task_id,
                "status": "completed",
                "result": result,
            }
            return {"task_id": task_id}
        return result
