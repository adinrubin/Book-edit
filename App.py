import json
import re
import io
import streamlit as st
from openai import OpenAI
import pypdf
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

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
# FILE PARSING FUNCTIONS
# ==========================================================
def extract_text_from_file(uploaded_file):
    filename = uploaded_file.name.lower()
    
    if filename.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")
    
    elif filename.endswith(".pdf"):
        pdf_reader = pypdf.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text
    
    elif filename.endswith(".epub"):
        bytes_data = uploaded_file.read()
        book = epub.read_epub(io.BytesIO(bytes_data))
        text = ""
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text += soup.get_text() + "\n"
        return text
    
    return ""

def split_into_chapters(text: str):
    pattern = r"(?i)(?=^#+\s|^Chapter\s+\d+|^CHAPTER\s+\d+)"
    chapters = [c.strip() for c in re.split(pattern, text, flags=re.MULTILINE) if c.strip()]
    if not chapters:
        words = text.split()
        chunk_size = 3000
        chapters = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
    return chapters or [text]

def balance_percentages(values_dict, changed_key, target_total=100.0):
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

# ==========================================================
# STREAMLIT UI SETUP & SESSION STATE
# ==========================================================
st.set_page_config(page_title="Multiverse Novel Remix Engine", layout="wide")
st.title("🌌 The Multiverse Novel Remix Engine")

if "story_bible" not in st.session_state:
    st.session_state.story_bible = {"characters": [], "world_rules": [], "plot_threads": []}
if "remixed_chapters" not in st.session_state:
    st.session_state.remixed_chapters = []
if "parent_weights" not in st.session_state:
    st.session_state.parent_weights = {}
if "sub_weights" not in st.session_state:
    st.session_state.sub_weights = {}

# Sidebar Setup
st.sidebar.header("🔑 Configuration")
openrouter_api_key = st.sidebar.text_input("Enter OpenRouter API Key", type="password")
st.sidebar.caption("Get a free key instantly at [openrouter.ai](https://openrouter.ai)")

selected_age_group = st.sidebar.selectbox("Target Audience Age Group", list(AGE_GROUPS.keys()))
age_config = AGE_GROUPS[selected_age_group]
allowed_parents = age_config["allowed_parents"]

# Re-initialize sliders if age group constraints change
for p in allowed_parents:
    if p not in st.session_state.parent_weights:
        st.session_state.parent_weights[p] = round(100.0 / len(allowed_parents), 1)

st.session_state.parent_weights = {
    k: v for k, v in st.session_state.parent_weights.items() if k in allowed_parents
}

total_p = sum(st.session_state.parent_weights.values()) or 1.0
st.session_state.parent_weights = {
    k: round((v / total_p) * 100.0, 1) for k, v in st.session_state.parent_weights.items()
}

# ==========================================================
# MAIN INTERFACE
# ==========================================================
uploaded_file = st.file_uploader("Upload Manuscript (.txt, .pdf, .epub)", type=["txt", "pdf", "epub"])

if uploaded_file:
    raw_text = extract_text_from_file(uploaded_file)
    if not raw_text.strip():
        st.error("Could not extract text from this file. Please ensure it contains readable text.")
    else:
        chapters = split_into_chapters(raw_text)
        st.success(f"File parsed! Extracted ~{len(raw_text.split())} words divided into {len(chapters)} chapter chunk(s).")

        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("🎛️ Theme & Genre Sliders")
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

            for k, v in updated_parents.items():
                if v != st.session_state.parent_weights.get(k, 0.0):
                    st.session_state.parent_weights = balance_percentages(updated_parents, k)
                    st.rerun()

            st.subheader("🧩 Sub-Genre Allocation")
            final_composition = {}
            
            for parent, parent_weight in st.session_state.parent_weights.items():
                if parent_weight > 0 and parent in age_config["sub_genres"]:
                    sub_list = age_config["sub_genres"][parent]
                    
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

                        for sk, sv in updated_subs.items():
                            if sv != st.session_state.sub_weights[parent].get(sk, 0.0):
                                st.session_state.sub_weights[parent] = balance_percentages(updated_subs, sk)
                                st.rerun()

                        for sub, sub_pct in st.session_state.sub_weights[parent].items():
                            effective_weight = (parent_weight * sub_pct) / 100.0
                            final_composition[f"{parent} -> {sub}"] = round(effective_weight, 1)

        with col2:
            st.subheader("⚙️ Execution Engine")
            st.write("**Target Composition Matrix:**")
            st.json(final_composition)

            active_chapter_idx = st.number_input(
                "Select Chapter Chunk to Process", 
                min_value=1, 
                max_value=len(chapters), 
                value=1
            ) - 1

            selected_chapter_text = chapters[active_chapter_idx]

            if st.button("🚀 Process & Remix Chapter"):
                if not openrouter_api_key:
                    st.error("Please enter a valid OpenRouter API Key in the sidebar.")
                else:
                    client = OpenAI(
                        base_url="https://openrouter.ai/api/v1",
                        api_key=openrouter_api_key
                    )
                    # Using a top-performing free model hosted on OpenRouter
                    model_name = "meta-llama/llama-3.3-70b-instruct:free"

                    with st.spinner("Analyzing Chapter Scenario..."):
                        analysis_prompt = f"""
                        Analyze the text. Extract 3 to 5 narrative pillars driving it.
                        Return strictly JSON format:
                        {{
                            "narrative_pillars": ["pillar1", "pillar2"],
                            "estimated_genre": "description"
                        }}
                        TEXT:
                        {selected_chapter_text[:2500]}
                        """
                        
                        try:
                            analysis_response = client.chat.completions.create(
                                model=model_name,
                                messages=[{"role": "user", "content": analysis_prompt}],
                                response_format={"type": "json_object"}
                            )
                            scenario_data = json.loads(analysis_response.choices[0].message.content)
                            st.subheader("Adaptive Scenario Mapping Result")
                            st.json(scenario_data)

                        except Exception as e:
                            st.error(f"Analysis Error: {str(e)}")
                            scenario_data = {"narrative_pillars": ["General Progression"]}

                    with st.spinner("Generating Remixed Chapter & Updating Story Bible..."):
                        history_summary = "\n".join([
                            f"- Chapter {i+1}: {c[:150]}..." 
                            for i, c in enumerate(st.session_state.remixed_chapters)
                        ]) or "None (Chapter 1)."

                        generation_prompt = f"""
                        You are an author executing a full thematic remix of a novel chapter.

                        === TARGET AUDIENCE ===
                        {age_config["system_instruction"]}

                        === THEMATIC COMPOSITION MATRIX ===
                        {json.dumps(final_composition, indent=2)}

                        === NARRATIVE PILLARS ===
                        {json.dumps(scenario_data.get("narrative_pillars", []))}

                        === STORY BIBLE STATE ===
                        {json.dumps(st.session_state.story_bible, indent=2)}

                        === PREVIOUS CHAPTERS SUMMARY ===
                        {history_summary}

                        === ORIGINAL TEXT ===
                        {selected_chapter_text}

                        === INSTRUCTIONS ===
                        1. Rewrite the chapter matching the target composition and age limits.
                        2. BUTTERFLY EFFECT PERMISSION: If slider weights force character decisions to shift, alter their actions and branch the story timeline.
                        """

                        try:
                            gen_response = client.chat.completions.create(
                                model=model_name,
                                messages=[{"role": "user", "content": generation_prompt}]
                            )
                            remixed_text = gen_response.choices[0].message.content
                            st.session_state.remixed_chapters.append(remixed_text)

                            # Update Story Bible
                            bible_prompt = f"""
                            Read this chapter and return an updated JSON Story Bible:
                            {{
                                "characters": ["list of characters and states"],
                                "world_rules": ["world rules or tech levels"],
                                "plot_threads": ["active plot arcs"]
                            }}
                            TEXT:
                            {remixed_text[:3000]}
                            """

                            bible_response = client.chat.completions.create(
                                model=model_name,
                                messages=[{"role": "user", "content": bible_prompt}],
                                response_format={"type": "json_object"}
                            )
                            st.session_state.story_bible = json.loads(bible_response.choices[0].message.content)

                            st.subheader("📖 Generated Remixed Text")
                            st.text_area("Output Text", remixed_text, height=400)

                            st.subheader("📚 Updated Story Bible State")
                            st.json(st.session_state.story_bible)

                        except Exception as e:
                            st.error(f"Generation Error: {str(e)}")
