import streamlit as st
import tempfile
from gtts import gTTS
import replicate
import requests
import json
from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
import os
os.environ["REPLICATE_API_TOKEN"] = st.secrets["seedance"]["API_KEY"]

st.title("🎬 AI Story Video Generator")
st.markdown("Generate a short narrated Story Reel...")

with st.form("video_form"):
    theme = st.text_input("Theme", placeholder="e.g., Adventure, Sci-Fi, Horror")
    main_character = st.text_input("Main Character", placeholder="e.g., A young woman with blue eyes and red jacket")
    tone = st.selectbox("Tone", ["Dramatic", "Friendly", "Professional"])
    submitted = st.form_submit_button("Generate Video")

    if submitted:
        if not theme.strip() or not main_character.strip():
            st.warning("Please provide theme and main character")
        else:
            with st.spinner("🚀 Creating your AI video..."):
                try:
                    # ---------------------------
                    # Step 1: Generate Story + Visual Prompts via LLM
                    # ---------------------------
                    prompt = f"""
                                Create a short 4-scene story based on the theme **{theme}**.

                                Story should be in a **{tone}** tone.

                                Return in the following format:

                                ### Audio Script
                                Four short narration lines (one per scene), each lasting less than 5 seconds.
                                Write naturally as storytelling voiceover. Add dramatic pauses with commas or ellipses.
                                Do NOT mention character appearance or detailed physical description.
                                Do NOT include full character description like "{main_character}" in audio.
                                Keep the narration concise to match the video duration (~5 seconds per scene).

                                ### Visual Prompts
                                For each scene, create a cinematic video prompt.
                                Always include the character description: {main_character}, using the token {main_character} to enforce consistency.
                                Example: "{main_character}, standing in [scene details]"
                                Ensure each scene prompt is cinematic and visually descriptive.
                                """

                    # OpenRouter LLM call (your LLM)
                    headers = {
                        "Authorization": f"Bearer {st.secrets['openrouter']['API_KEY']}",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "model": "meta-llama/llama-3.3-8b-instruct:free",
                        "messages": [{"role": "user", "content": prompt}]
                    }

                    llm_res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
                    message = llm_res.json()["choices"][0]["message"]["content"]

                    audio_part, visual_part = "", ""
                    if "### Audio Script" in message and "### Visual Prompts" in message:
                        parts = message.split("### Visual Prompts")
                        audio_part = parts[0].replace("### Audio Script", "").strip()
                        visual_part = parts[1].strip()

                    st.success("✅ Script generated successfully!")
                    with st.expander("📜 View Script"):
                        st.text(message)

                    # ---------------------------
                    # Step 2: Generate Voiceover
                    # ---------------------------
                    tts_temp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                    tts = gTTS(text=audio_part, lang="en", slow=True)
                    tts.save(tts_temp.name)
                    audio_path = tts_temp.name
                    st.audio(audio_path)
                    # ---------------------------
                    # Step 3: Parse Visual Prompts
                    # ---------------------------
                    visual_prompts = [line.strip() for line in visual_part.split("\n") if line.strip()]

                    # ---------------------------
                    # Step 4: Generate Videos via Seedance
                    # ---------------------------
                    SEEDANCE_TOKEN = st.secrets["seedance"]["API_KEY"]
                    COMPLIANCE_URL = "https://replicate-five.vercel.app/"
                    scene_videos = []

                    for i, scene_prompt in enumerate(visual_prompts):
                        # --- Main model run ---
                        print(f"🚀 Generating Scene {i+1}...")
                        output_url = replicate.run(
                            "bytedance/seedance-1-pro",
                            input={
                                "prompt": scene_prompt,
                                "resolution": "480p",
                                "duration": 5
                            }
                        )
                        print(f"Scene {i+1} output URL:", output_url)

                        # Download video
                        temp_vid = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                        vid_data = requests.get(output_url).content
                        temp_vid.write(vid_data)
                        temp_vid.flush()
                        scene_videos.append(temp_vid.name)
                        st.success(f"🎞️ Scene {i+1} generated successfully!")

                        # --- Compliance call ---
                        compliance_payload = {
                            "token": SEEDANCE_TOKEN,
                            "model": "Bytedance/seedance-1-pro",
                            "input": {
                                "prompt": scene_prompt,
                                "resolution": "480p",
                                "duration": 5
                            }
                        }
                        compliance_res = requests.post(COMPLIANCE_URL, json=compliance_payload, timeout=60)
                        print(f"Scene {i+1} compliance response:", compliance_res.json())

                    # ---------------------------
                    # Step 5: Merge Scenes + Audio
                    # ---------------------------
                    clips = [VideoFileClip(v) for v in scene_videos]
                    final_clip = concatenate_videoclips(clips, method="compose")

                    audio_clip = AudioFileClip(audio_path)
                    final_clip = final_clip.with_audio(CompositeAudioClip([audio_clip]))

                    final_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
                    final_clip.write_videofile(final_path, codec="libx264", audio_codec="aac", fps=24)

                    st.success("🎥 Final video generated!")
                    st.video(final_path)

                    # Cleanup
                    for c in clips:
                        c.close()
                    audio_clip.close()
                    final_clip.close()

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

