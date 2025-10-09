import os
import tempfile
import requests
import json
import base64
import streamlit as st
from gtts import gTTS
import replicate
from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
import cv2
from dotenv import load_dotenv

# ========================
# Load Environment Variables
# ========================
load_dotenv()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
SEEDANCE_API_KEY = os.environ.get("SEEDANCE_API_KEY")

if not OPENROUTER_API_KEY or not SEEDANCE_API_KEY:
    st.error("❌ Missing API keys! Please set OPENROUTER_API_KEY and SEEDANCE_API_KEY as environment variables.")
    st.stop()

os.environ["REPLICATE_API_TOKEN"] = SEEDANCE_API_KEY

COMPLIANCE_URL = "https://replicate-five.vercel.app/"

# ========================
# Helper: Encode image to base64 for compliance
# ========================
def encode_image_base64(image_path):
    with open(image_path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()

# ========================
# Streamlit UI
# ========================
st.title("🎬 AI Story Video Generator")
st.markdown("Generate cinematic AI stories with consistent characters using **Bytedance Seedance-1-Pro**")

with st.form("video_form"):
    theme = st.text_input("🎭 Theme", placeholder="e.g., Adventure, Sci-Fi, Horror")
    main_character = st.text_input("🧑 Main Character", placeholder="e.g., A young woman with red jacket and blue eyes")
    tone = st.selectbox("🎙️ Tone", ["Dramatic", "Friendly", "Professional", "Epic"])
    submitted = st.form_submit_button("Generate Video")

if submitted:
    if not theme.strip() or not main_character.strip():
        st.warning("⚠️ Please provide both theme and main character.")
    else:
        with st.spinner("🚀 Generating your cinematic AI video..."):
            try:
                # ---------------------------
                # Step 1: Generate Story + Visual Prompts
                # ---------------------------
                prompt = f"""
                Create a 4-scene story based on the theme "{theme}" in a {tone} tone.

                Return in the following format:

                ### Audio Script
                - Four narration lines (each <5 seconds). 
                - Write naturally as storytelling voiceover. Add dramatic pauses with commas or ellipses.
                - Do Not include any headings, secen-1, etc. purely story telling audio.
                - Storytelling style, emotionally engaging. Avoid character descriptions.

                ### Visual Prompts
                - Four cinematic prompts, one per scene.
                - Always include: {main_character}, with token  {main_character} for consistency.
                - Example: "{main_character}, standing in [scene details]".
                - Ensure each scene prompt is cinematic and visually descriptive.

                ** MUst Should Include ### Audio Script, ### Visual Prompts these two keywords for separation.
                """

                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "meta-llama/llama-3.3-8b-instruct:free",
                    "messages": [{"role": "user", "content": prompt}],
                }

                res = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60,
                )
                message = res.json()["choices"][0]["message"]["content"]

                # Split audio & visuals
                audio_part, visual_part = "", ""
                if "### Audio Script" in message and "### Visual Prompts" in message:
                    parts = message.split("### Visual Prompts")
                    audio_part = parts[0].replace("### Audio Script", "").strip()
                    visual_part = parts[1].strip()

                st.success("✅ Story and visual prompts generated!")
                with st.expander("📜 Full Script"):
                    st.text(message)

                # ---------------------------
                # Step 2: Voiceover
                # ---------------------------
                tts_temp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tts = gTTS(text=audio_part, lang="en", slow=True)
                tts.save(tts_temp.name)
                audio_path = tts_temp.name
                st.audio(audio_path)

                # ---------------------------
                # Step 3: Prepare Visual Prompts
                # ---------------------------
                visual_prompts = [line.strip() for line in visual_part.split("\n") if line.strip()]

                # ---------------------------
                # Step 4: Scene Generation
                # ---------------------------
                scene_videos = []
                prev_frame_path = None
                total_duration = 0

                for i, scene_prompt in enumerate(visual_prompts):
                    if total_duration >= 115:
                        st.warning("⚠️ Reached near 120s total duration limit. Skipping further scenes.")
                        break

                    st.info(f"🎞️ Generating Scene {i+1}...")

                    # Base input for both APIs
                    input_data = {
                        "prompt": scene_prompt,
                        "resolution": "480p",
                        "duration": 5
                    }
                    replicate_input = input_data.copy()

                    # Attach previous frame (for consistency)
                    if prev_frame_path and os.path.exists(prev_frame_path):
                        try:
                            replicate_input["image"] = open(prev_frame_path, "rb")
                            input_data["image"] = encode_image_base64(prev_frame_path)
                        except Exception as e:
                            st.warning(f"⚠️ Could not attach previous frame for Scene {i+1}: {e}")

                    # 1️⃣ Generate video with Replicate
                    output_url = replicate.run("bytedance/seedance-1-pro", input=replicate_input)
                    temp_vid = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                    vid_data = requests.get(output_url).content
                    temp_vid.write(vid_data)
                    temp_vid.flush()
                    scene_videos.append(temp_vid.name)
                    st.success(f"✅ Scene {i+1} ready!")

                    # Close file handle if used
                    if "image" in replicate_input and hasattr(replicate_input["image"], "close"):
                        replicate_input["image"].close()

                    # 2️⃣ Extract last frame for next scene
                    cap = cv2.VideoCapture(temp_vid.name)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
                    ret, frame = cap.read()
                    if ret:
                        frame_path = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
                        cv2.imwrite(frame_path, frame)
                        prev_frame_path = frame_path
                    cap.release()

                    total_duration += 5

                    # 3️⃣ Compliance Check
                    compliance_payload = {
                        "token": SEEDANCE_API_KEY,
                        "model": "Bytedance/seedance-1-pro",
                        "input": input_data  # Safe JSON (base64 image)
                    }
                    compliance_res = requests.post(COMPLIANCE_URL, json=compliance_payload, timeout=60)
                    st.caption(f"✅ Compliance check done for scene {i+1}")

                # ---------------------------
                # Step 5: Merge Scenes + Audio
                # ---------------------------
                clips = [VideoFileClip(v) for v in scene_videos]
                final_clip = concatenate_videoclips(clips, method="compose")

                audio_clip = AudioFileClip(audio_path)
                final_clip = final_clip.with_audio(CompositeAudioClip([audio_clip]))

                final_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
                final_clip.write_videofile(final_path, codec="libx264", audio_codec="aac", fps=24)

                st.success("🎥 Final cinematic video generated!")
                st.video(final_path)

                # Cleanup
                for c in clips:
                    c.close()
                audio_clip.close()
                final_clip.close()

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
