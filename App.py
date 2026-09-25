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
# CONFIGURATION & AGE FILTERS
# ==========================================================
st.set_page_config(page_title="Multiverse Novel Remix Engine", page_icon="📚", layout="wide")

AGE_GROUPS = {
    "Early Reader (Ages 5-7)": {
        "parents": ["Fantasy", "Sci-Fi", "Drama"],
        "sub_genres": {
            "Fantasy": ["Whimsical Fantasy", "Fable / Moral Tale"],
            "Sci-Fi": ["Outer Space Adventure", "Friendly Robots"],
            "Drama": ["Family & Friendship", "School Life"],
        },
        "instruction": "Target Audience: Children ages 5-7. Use simple vocabulary, short sentences, whimsical/fun tone, and zero dark, violent, or romantic themes.",
    },
    "Middle Grade (Ages 8-12)": {
        "parents": ["Fantasy", "Sci-Fi", "Drama", "Mystery"],
        "sub_genres": {
            "Fantasy": ["High Fantasy", "Urban Fantasy"],
            "Sci-Fi": ["Soft Sci-Fi", "Space Opera"],
            "Drama": ["Coming of Age", "Friendship"],
            "Mystery": ["Sleuth / Puzzle", "Adventure Mystery"],
        },
        "instruction": "Target Audience: Middle Grade (Ages 8-12). Pacing should be adventurous, age-appropriate action, light humor, and accessible sentence structure.",
    },
    "Young Adult (Ages 13-17)": {
        "parents": ["Fantasy", "Sci-Fi", "Drama", "Mystery", "Romance", "Horror"],
        "sub_genres": {
            "Fantasy": ["High Fantasy", "Urban Fantasy", "Dark Fantasy"],
            "Sci-Fi": ["Cyberpunk", "Dystopian", "Hard Sci-Fi"],
            "Drama": ["Emotional / Social", "Survival"],
            "Mystery": ["Thriller", "Whodunit"],
            "Romance": ["First Love", "Slow Burn"],
            "Horror": ["Supernatural", "Cosmic Horror"],
        },
        "instruction": "Target Audience: Young Adult (Ages 13-17). Character-driven focus, emotional depth, moderate intensity, and modern dialogue pacing.",
    },
    "Adult (Ages 18+)": {
        "parents": ["Fantasy", "Sci-Fi", "Drama", "Mystery", "Romance", "Horror"],
        "sub_genres": {
            "Fantasy": ["High Fantasy", "Grimdark", "Urban Fantasy"],
            "Sci-Fi": ["Hard Sci-Fi", "Cyberpunk", "Post-Apocalyptic"],
            "Drama": ["Psychological", "Domestic Drama"],
            "Mystery": ["Noir", "Psychological Thriller"],
            "Romance": ["Contemporary Romance", "Romantic Suspense"],
            "Horror": ["Psychological Horror", "Body Horror", "Cosmic Horror"],
        },
        "instruction": "Target Audience: Adults. Complex prose, unconstrained thematic elements, mature emotional subtext, and rich world-building.",
    },
}

# ==========================================================
# FILE PARSING & CHAPTER CHUNKING
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
        chunk_size = 2500
        chapters = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
    return chapters or [text]

# ==========================================================
# SLIDER STATE MANAGEMENT & MATH BALANCE
# ==========================================================
def update_parent_weights(changed_key, allowed_parents):
    new_val = st.session_state[f"slider_parent_{changed_key}"]
    remaining = 100.0 - new_val
    other_keys = [p for p in allowed_parents if p != changed_key]
    old_sum_others = sum(st.session_state.get(f"slider_parent_{k}", 0.0) for k in other_keys)

    for k in other_keys:
        if old_sum_others == 0:
            st.session_state[f"slider_parent_{k}"] = round(remaining / len(other_keys), 1)
        else:
            old_val = st.session_state.get(f"slider_parent_{k}", 0.0)
            st.session_state[f"slider_parent_{k}"] = round((old_val / old_sum_others) * remaining, 1)

# ==========================================================
# SESSION STATE INITIALIZATION
# ==========================================================
if "remixed_text" not in st.session_state:
    st.session_state.remixed_text = ""
if "story_bible" not in st.session_state:
    st.session_state.story_bible = {"characters": [], "world_rules": [], "plot_threads": []}
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False

# Sidebar Config
st.sidebar.title("🛠️ Control Panel")
openrouter_api_key = st.sidebar.text_input("OpenRouter API Key", type="password")
st.sidebar.caption("Get a free key at [openrouter.ai](https://openrouter.ai)")

selected_age_group = st.sidebar.selectbox("Target Audience Age Group", list(AGE_GROUPS.keys()))
age_config = AGE_GROUPS[selected_age_group]
allowed_parents = age_config["parents"]

# Initialize Parent Sliders
for idx, p in enumerate(allowed_parents):
    if f"slider_parent_{p}" not in st.session_state:
        st.session_state[f"slider_parent_{p}"] = round(100.0 / len(allowed_parents), 1)

# ==========================================================
# HEADER & SLIDER UI
# ==========================================================
st.title("📚 Multiverse Novel Remix Engine")
st.markdown("Upload a novel, balance the theme sliders, and automatically transform the entire manuscript into a new parallel narrative.")

uploaded_file = st.file_uploader("Upload Manuscript (.txt, .pdf, .epub)", type=["txt", "pdf", "epub"])

if uploaded_file:
    raw_text = extract_text_from_file(uploaded_file)
    if not raw_text.strip():
        st.error("Error reading file content. Please check the uploaded file.")
    else:
        chapters = split_into_chapters(raw_text)
        
        st.subheader("🎛️ Genre & Sub-Genre Balance")
        col_sliders, col_summary = st.columns([2, 1])

        with col_sliders:
            # Parent Genre Sliders
            for parent in allowed_parents:
                st.slider(
                    f"**{parent}** (%)",
                    min_value=0.0,
                    max_value=100.0,
                    key=f"slider_parent_{parent}",
                    on_change=update_parent_weights,
                    args=(parent, allowed_parents)
                )

            # Sub-Genre Expanders
            final_composition = {}
            for parent in allowed_parents:
                p_weight = st.session_state.get(f"slider_parent_{parent}", 0.0)
                if p_weight > 0 and parent in age_config["sub_genres"]:
                    sub_list = age_config["sub_genres"][parent]
                    with st.expander(f"Fine-tune {parent} Sub-Genres"):
                        sub_weight = round(p_weight / len(sub_list), 1)
                        for sub in sub_list:
                            final_composition[f"{parent} -> {sub}"] = sub_weight
                            st.caption(f"• **{sub}**: ~{sub_weight}% allocated")
                elif p_weight > 0:
                    final_composition[parent] = p_weight

        with col_summary:
            st.info(f"**Manuscript Parsed**\n- **Total Words:** ~{len(raw_text.split()):,}\n- **Chapter Chunks:** {len(chapters)}")
            st.markdown("**Effective Target Matrix:**")
            for genre_name, weight in final_composition.items():
                st.progress(min(int(weight), 100), text=f"{genre_name}: {weight:.1f}%")

            start_button = st.button("🚀 Remix Entire Novel", type="primary", use_container_width=True)

        # ==========================================================
        # AUTOMATED PROCESSING ENGINE
        # ==========================================================
        if start_button:
            if not openrouter_api_key:
                st.error("Please enter a valid OpenRouter API Key in the sidebar.")
            else:
                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=openrouter_api_key
                )
                model_name = "meta-llama/llama-3.3-70b-instruct:free"

                st.divider()
                st.subheader("⚙️ Automated Remix Pipeline Running...")
                
                progress_bar = st.progress(0, text="Initializing Story Engine...")
                status_box = st.empty()

                remixed_chapters_list = []
                story_bible = {"characters": [], "world_rules": [], "plot_threads": []}

                for idx, ch_text in enumerate(chapters):
                    ch_num = idx + 1
                    status_box.info(f"🔄 Processing Chapter {ch_num} of {len(chapters)}...")
                    progress_bar.progress(int((idx / len(chapters)) * 100), text=f"Transforming Chapter {ch_num}...")

                    history_summary = "\n".join([
                        f"- Chapter {i+1}: {c[:200]}..." 
                        for i, c in enumerate(remixed_chapters_list)
                    ]) or "None (Beginning of book)."

                    # Main Rewrite Prompt
                    rewrite_prompt = f"""
                    You are a master developmental novelist executing a thematic remix of a chapter.

                    === TARGET AUDIENCE ===
                    {age_config["instruction"]}

                    === TARGET THEMATIC COMPOSITION MATRIX ===
                    {json.dumps(final_composition, indent=2)}

                    === CURRENT GLOBAL STORY BIBLE STATE ===
                    {json.dumps(story_bible, indent=2)}

                    === SUMMARY OF RECENTLY REMIXED CHAPTERS ===
                    {history_summary}

                    === ORIGINAL CHAPTER TEXT ===
                    {ch_text}

                    === INSTRUCTIONS ===
                    1. Completely rewrite this chapter to embody the target thematic composition and target audience guidelines.
                    2. BUTTERFLY EFFECT PERMISSION: If the new target themes dictate that characters would make a different decision, EXECUTE THAT CHANGE. Let the plot branch and flow into a new timeline naturally.
                    3. Write directly in rich narrative prose. Do not include introductory commentary or system notes.
                    """

                    try:
                        res = client.chat.completions.create(
                            model=model_name,
                            messages=[{"role": "user", "content": rewrite_prompt}]
                        )
                        remixed_ch = res.choices[0].message.content
                        remixed_chapters_list.append(remixed_ch)

                        # Story Bible Update Prompt
                        bible_prompt = f"""
                        Read this newly generated chapter and return an updated JSON Story Bible.
                        Return ONLY valid JSON with no backticks:
                        {{
                            "characters": ["updated list of characters and current emotional states"],
                            "world_rules": ["updated active world mechanics or tech levels"],
                            "plot_threads": ["active unresolved plot arcs"]
                        }}

                        TEXT:
                        {remixed_ch[:3000]}
                        """

                        bible_res = client.chat.completions.create(
                            model=model_name,
                            messages=[{"role": "user", "content": bible_prompt}],
                            response_format={"type": "json_object"}
                        )
                        story_bible = json.loads(bible_res.choices[0].message.content)

                    except Exception as e:
                        st.error(f"Error encountered on Chapter {ch_num}: {str(e)}")
                        break

                progress_bar.progress(100, text="Transformation Complete!")
                status_box.success("🎉 Entire novel remixed successfully!")

                st.session_state.remixed_text = "\n\n=== NEXT CHAPTER ===\n\n".join(remixed_chapters_list)
                st.session_state.story_bible = story_bible
                st.session_state.processing_complete = True

        # ==========================================================
        # CLEAN OUTPUT TABS
        # ==========================================================
        if st.session_state.processing_complete:
            st.divider()
            tab_novel, tab_bible = st.tabs(["📖 Remixed Manuscript", "📚 Dynamic Story Bible"])

            with tab_novel:
                st.download_button(
                    "💾 Download Full Remixed Novel (.txt)",
                    data=st.session_state.remixed_text,
                    file_name="remixed_novel.txt",
                    mime="text/plain"
                )
                st.text_area("Full Manuscript Output", st.session_state.remixed_text, height=600)

            with tab_bible:
                st.subheader("Global Narrative Continuity State")
                col_c, col_w, col_p = st.columns(3)
                
                with col_c:
                    st.markdown("### 👤 Characters")
                    for item in st.session_state.story_bible.get("characters", []):
                        st.write(f"- {item}")
                        
                with col_w:
                    st.markdown("### 🌐 World Rules")
                    for item in st.session_state.story_bible.get("world_rules", []):
                        st.write(f"- {item}")
                        
                with col_p:
                    st.markdown("### 🎯 Plot Threads")
                    for item in st.session_state.story_bible.get("plot_threads", []):
                        st.write(f"- {item}")
