import json
import re
import streamlit as st
from google import genai
from google.genai import types

# ==========================================================
# CONSTANTS & CONFIGURATION
# ==========================================================
AGE_GROUPS = {
    "Early Reader (Ages 5-7)": {
        "allowed_parents": ["Fantasy", "Sci-Fi", "Drama"],
        "sub_genres": {
            "Fantasy": ["Whimsical Fantasy", "Fable / Moral Tale"],
            "Sci-Fi": ["Outer Space Adventure", "Friendly Robots"],
            "Drama": ["Family & Friendship", "School Life"],
        },
        "system_instruction": "Target Audience: Children ages 5-7. Use simple vocabulary, short sentences, whimsical/fun tone, and zero dark, violent, or romantic themes.",
    },
    "Middle Grade (Ages 8-12)": {
        "allowed_parents": ["Fantasy", "Sci-Fi", "Drama", "Mystery"],
        "sub_genres": {
            "Fantasy": ["High Fantasy", "Urban Fantasy"],
            "Sci-Fi": ["Soft Sci-Fi", "Space Opera"],
            "Drama": ["Coming of Age", "Friendship"],
            "Mystery": ["Sleuth / Puzzle", "Adventure Mystery"],
        },
        "system_instruction": "Target Audience: Middle Grade (Ages 8-12). Pacing should be adventurous, age-appropriate action, light humor, and accessible sentence structure.",
    },
    "Young Adult (Ages 13-17)": {
        "allowed_parents": ["Fantasy", "Sci-Fi", "Drama", "Mystery", "Romance", "Horror"],
        "sub_genres": {
            "Fantasy": ["High Fantasy", "Urban Fantasy", "Dark Fantasy"],
            "Sci-Fi": ["Cyberpunk", "Dystopian", "Hard Sci-Fi"],
            "Drama": ["Emotional / Social", "Survival"],
            "Mystery": ["Thriller", "Whodunit"],
            "Romance": ["First Love", "Slow Burn"],
            "Horror": ["Supernatural", "Cosmic Horror"],
        },
        "system_instruction": "Target Audience: Young Adult (Ages 13-17). Character-driven focus, emotional depth, moderate intensity, and modern dialogue pacing.",
    },
    "Adult (Ages 18+)": {
        "allowed_parents": ["Fantasy", "Sci-Fi", "Drama", "Mystery", "Romance", "Horror"],
        "sub_genres": {
            "Fantasy": ["High Fantasy", "Grimdark", "Urban Fantasy"],
            "Sci-Fi": ["Hard Sci-Fi", "Cyberpunk", "Post-Apocalyptic"],
            "Drama": ["Psychological", "Domestic Drama"],
            "Mystery": ["Noir", "Psychological Thriller"],
            "Romance": ["Contemporary Romance", "Romantic Suspense"],
            "Horror": ["Psychological Horror", "Body Horror", "Cosmic Horror"],
        },
        "system_instruction": "Target Audience: Adults. Complex prose, unconstrained thematic elements, mature emotional subtext, and rich world-building.",
    },
}

# ==========================================================
# HELPER FUNCTIONS
# ==========================================================
def split_into_chapters(text: str):
    """Splits manuscript into chapters using regex on common headings."""
    pattern = r"(?i)(?=^#+\s|^Chapter\s+\d+|^CHAPTER\s+\d+)"
    chapters = [c.strip() for c in re.split(pattern, text, flags=re.MULTILINE) if c.strip()]
    if not chapters:
        return [text]
    return chapters

def balance_percentages(values_dict, changed_key, target_total=100.0):
    """Normalizes interactive slider values so the total equals target_total."""
    num_items = len(values_dict)
    if num_items <= 1:
        return {k: target_total for k in values_dict}

    new_val = values_dict[changed_key]
    remaining_target = target_total - new_val
    old_sum_others = sum(v for k, v in values_dict.items() if k != changed_key)

    result = {}
    for k, v in values_dict.items():
        if k == changed_key:
            result[k] = new_val
        elif old_sum_others == 0:
            result[k] = remaining_target / (num_items - 1)
        else:
            result[k] = round((v / old_sum_others) * remaining_target, 1)

    return result

def get_gemini_client(api_key: str):
    """Initializes the official Google GenAI client."""
    if not api_key:
        return None
    return genai.Client(api_key=api_key)

# ==========================================================
# STREAMLIT UI SETUP & SESSION STATE
# ==========================================================
st.set_page_config(page_title="Multiverse Novel Remix Engine", layout="wide")
st.title("🌌 The Multiverse Novel Remix Engine")

# Initialize Session State Variables
if "story_bible" not in st.session_state:
    st.session_state.story_bible = {
        "characters": [],
        "world_rules": [],
        "plot_threads": []
    }
if "remixed_chapters" not in st.session_state:
    st.session_state.remixed_chapters = []
if "parent_weights" not in st.session_state:
    st.session_state.parent_weights = {}
if "sub_weights" not in st.session_state:
    st.session_state.sub_weights = {}

# Sidebar Setup
st.sidebar.header("🔑 Configuration")
api_key = st.sidebar.text_input("Gemini API Key", type="password")

selected_age_group = st.sidebar.selectbox("Target Audience Age Group", list(AGE_GROUPS.keys()))
age_config = AGE_GROUPS[selected_age_group]
allowed_parents = age_config["allowed_parents"]

# Re-initialize sliders if age group constraints change
for p in allowed_parents:
    if p not in st.session_state.parent_weights:
        st.session_state.parent_weights[p] = round(100.0 / len(allowed_parents), 1)

# Remove restricted parents from session state
st.session_state.parent_weights = {
    k: v for k, v in st.session_state.parent_weights.items() if k in allowed_parents
}

# Normalize parent weights
total_p = sum(st.session_state.parent_weights.values()) or 1.0
st.session_state.parent_weights = {
    k: round((v / total_p) * 100.0, 1) for k, v in st.session_state.parent_weights.items()
}

# ==========================================================
# MAIN INTERFACE
# ==========================================================
uploaded_file = st.file_uploader("Upload Manuscript (.txt)", type=["txt"])

if uploaded_file:
    raw_text = uploaded_file.read().decode("utf-8")
    chapters = split_into_chapters(raw_text)
    st.success(f"Manuscript loaded successfully! Detected {len(chapters)} chapter(s).")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("🎛️ Theme & Genre Sliders")
        st.info("Adjust the primary theme weights. Total always equals 100%.")

        # Parent Sliders
        updated_parents = {}
        for parent in allowed_parents:
            val = st.slider(
                f"{parent} Weight (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(st.session_state.parent_weights.get(parent, 0.0)),
                step=1.0,
                key=f"slider_parent_{parent}"
            )
            updated_parents[parent] = val

        # Handle normalization if slider moved
        for k, v in updated_parents.items():
            if v != st.session_state.parent_weights.get(k, 0.0):
                st.session_state.parent_weights = balance_percentages(updated_parents, k)
                st.rerun()

        # Nested Sub-Genre Sliders
        st.subheader("🧩 Sub-Genre Allocation")
        final_composition = {}
        
        for parent, parent_weight in st.session_state.parent_weights.items():
            if parent_weight > 0 and parent in age_config["sub_genres"]:
                sub_list = age_config["sub_genres"][parent]
                
                # Initialize sub weights
                if parent not in st.session_state.sub_weights:
                    st.session_state.sub_weights[parent] = {
                        sub: round(100.0 / len(sub_list), 1) for sub in sub_list
                    }

                with st.expander(f"{parent} Sub-Genres (Allocated Share: {parent_weight:.1f}%)"):
                    updated_subs = {}
                    for sub in sub_list:
                        s_val = st.slider(
                            f"{sub} (%)",
                            min_value=0.0,
                            max_value=100.0,
                            value=float(st.session_state.sub_weights[parent].get(sub, 0.0)),
                            step=1.0,
                            key=f"slider_sub_{parent}_{sub}"
                        )
                        updated_subs[sub] = s_val

                    # Normalize sub-genres
                    for sk, sv in updated_subs.items():
                        if sv != st.session_state.sub_weights[parent].get(sk, 0.0):
                            st.session_state.sub_weights[parent] = balance_percentages(updated_subs, sk)
                            st.rerun()

                    # Calculate absolute contribution to full novel
                    for sub, sub_pct in st.session_state.sub_weights[parent].items():
                        effective_weight = (parent_weight * sub_pct) / 100.0
                        final_composition[f"{parent} -> {sub}"] = round(effective_weight, 1)

    with col2:
        st.subheader("⚙️ Execution Engine")
        st.write("**Target Composition Matrix:**")
        st.json(final_composition)

        active_chapter_idx = st.number_input(
            "Select Chapter to Process", 
            min_value=1, 
            max_value=len(chapters), 
            value=1
        ) - 1

        selected_chapter_text = chapters[active_chapter_idx]

        if st.button("🚀 Process & Remix Chapter"):
            client = get_gemini_client(api_key)
            if not client:
                st.error("Please provide a valid Gemini API Key in the sidebar.")
            else:
                with st.spinner("Analyzing Chapter Scenario..."):
                    # Step 1: Adaptive Scenario Mapping
                    analysis_prompt = f"""
                    Analyze the following chapter text. Identify the 3 to 5 primary narrative pillars 
                    driving this specific text block (e.g., Action Tension, Character Subtext, Atmospheric Dread).
                    Return your analysis strictly as a JSON object matching this schema:
                    {{
                        "narrative_pillars": ["pillar1", "pillar2", "pillar3"],
                        "estimated_original_genre": "description"
                    }}

                    TEXT:
                    {selected_chapter_text[:3000]}
                    """
                    
                    try:
                        analysis_response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=analysis_prompt,
                            config=types.GenerateContentConfig(response_mime_type="application/json")
                        )
                        scenario_data = json.loads(analysis_response.text)
                        st.subheader("Adaptive Scenario Mapping Result")
                        st.json(scenario_data)

                    except Exception as e:
                        st.error(f"Analysis Error: {str(e)}")
                        scenario_data = {"narrative_pillars": ["General Plot Progression"]}

                # Step 2: Remixed Output Generation with Timeline Variance
                with st.spinner("Generating Remixed Chapter & Updating Story Bible..."):
                    history_summary = "\n".join([
                        f"- Chapter {i+1}: {c[:150]}..." 
                        for i, c in enumerate(st.session_state.remixed_chapters)
                    ]) or "None (This is Chapter 1)."

                    generation_prompt = f"""
                    You are a developmental author executing a total thematic remix of a chapter.

                    === TARGET AUDIENCE CONSTRAINT ===
                    {age_config["system_instruction"]}

                    === TARGET THEMATIC COMPOSITION ===
                    {json.dumps(final_composition, indent=2)}

                    === NARRATIVE PILLARS TO ADAPT ===
                    {json.dumps(scenario_data.get("narrative_pillars", []))}

                    === CURRENT GLOBAL STORY BIBLE ===
                    {json.dumps(st.session_state.story_bible, indent=2)}

                    === PREVIOUS REMIXED CHAPTERS SUMMARY ===
                    {history_summary}

                    === ORIGINAL CHAPTER TEXT ===
                    {selected_chapter_text}

                    === INSTRUCTIONS ===
                    1. Re-imagine and rewrite the chapter to match the TARGET THEMATIC COMPOSITION and TARGET AUDIENCE CONSTRAINTS.
                    2. TIMELINE VARIANCE PERMISSION: If the new thematic weights logically cause the characters to make a completely different decision than in the original text, EXECUTE THAT CHANGE. Let the plot branch organically (Butterfly Effect).
                    3. Maintain narrative continuity with the previous remixed chapters.
                    """

                    try:
                        gen_response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=generation_prompt
                        )
                        remixed_text = gen_response.text
                        st.session_state.remixed_chapters.append(remixed_text)

                        # Step 3: Update Story Bible Background Call
                        bible_prompt = f"""
                        Read this newly generated chapter and update the global Story Bible.
                        Return ONLY a valid JSON object matching this schema:
                        {{
                            "characters": ["updated list of characters and emotional states"],
                            "world_rules": ["updated active world mechanics or tech levels"],
                            "plot_threads": ["active open unresolved plot arcs"]
                        }}

                        NEW CHAPTER TEXT:
                        {remixed_text}
                        """

                        bible_response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=bible_prompt,
                            config=types.GenerateContentConfig(response_mime_type="application/json")
                        )
                        st.session_state.story_bible = json.loads(bible_response.text)

                        # Display Results
                        st.subheader("📖 Generated Remixed Text")
                        st.text_area("Output Text", remixed_text, height=400)

                        st.subheader("📚 Updated Story Bible State")
                        st.json(st.session_state.story_bible)

                    except Exception as e:
                        st.error(f"Generation Error: {str(e)}")
