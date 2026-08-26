import streamlit as st
import google.generativeai as genai
from PIL import Image
import sqlite3
import datetime
import re

# --- DATABASE SETUP (Stores your meals locally) ---
def init_db():
    conn = sqlite3.connect("macro_history.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            meal_name TEXT,
            calories REAL,
            protein REAL,
            carbs REAL,
            fats REAL
        )
    ''')
    conn.commit()
    conn.close()

def save_meal(meal_name, calories, protein, carbs, fats):
    conn = sqlite3.connect("macro_history.db")
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    c.execute('''
        INSERT INTO meals (date, meal_name, calories, protein, carbs, fats)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (today, meal_name, calories, protein, carbs, fats))
    conn.commit()
    conn.close()

def get_today_totals():
    conn = sqlite3.connect("macro_history.db")
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    c.execute('''
        SELECT SUM(calories), SUM(protein), SUM(carbs), SUM(fats) 
        FROM meals WHERE date = ?
    ''', (today,))
    result = c.fetchone()
    conn.close()
    return [r if r is not None else 0.0 for r in result]

def get_history():
    conn = sqlite3.connect("macro_history.db")
    c = conn.cursor()
    c.execute('SELECT date, meal_name, calories, protein, carbs, fats FROM meals ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    return rows

init_db()

# --- STREAMLIT PAGE SETUP ---
st.set_page_config(page_title="AI Macro Tracker & Targets", page_icon="🥗", layout="centered")

# --- SIDEBAR SETUP (API Key & Goals) ---
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

if not api_key:
    st.warning("Please enter your Gemini API Key in the sidebar or setup Streamlit Secrets.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# Sidebar Goal Controls
st.sidebar.header("🎯 Daily Goals")
target_cal = st.sidebar.number_input("Calorie Target (kcal)", value=2000, step=50)
target_prot = st.sidebar.number_input("Protein Target (g)", value=150, step=5)
target_carbs = st.sidebar.number_input("Carbs Target (g)", value=200, step=5)
target_fats = st.sidebar.number_input("Fats Target (g)", value=65, step=5)

# --- DAILY PROGRESS DASHBOARD ---
st.title("🥗 AI Macro Tracker")
st.subheader("📊 Today's Progress")

daily_cal, daily_prot, daily_carbs, daily_fats = get_today_totals()

def get_progress(current, target):
    return min(1.0, current / target) if target > 0 else 0.0

# Calorie Progress Bar
cal_pct = get_progress(daily_cal, target_cal)
st.write(f"**Calories:** {int(daily_cal)} / {target_cal} kcal ({int(cal_pct * 100)}%)")
st.progress(cal_pct)

# Macro Progress Bars
col1, col2, col3 = st.columns(3)

with col1:
    p_pct = get_progress(daily_prot, target_prot)
    st.write(f"**Protein:** {int(daily_prot)} / {target_prot}g")
    st.progress(p_pct)

with col2:
    c_pct = get_progress(daily_carbs, target_carbs)
    st.write(f"**Carbs:** {int(daily_carbs)} / {target_carbs}g")
    st.progress(c_pct)

with col3:
    f_pct = get_progress(daily_fats, target_fats)
    st.write(f"**Fats:** {int(daily_fats)} / {target_fats}g")
    st.progress(f_pct)

st.divider()

# --- MEAL INPUT SECTION ---
tab1, tab2, tab3 = st.tabs(["📸 Upload Image", "✍️ Describe Meal", "📜 Daily Log"])

image = None
text_description = ""

with tab1:
    uploaded_file = st.file_uploader("Upload meal image", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Meal", use_container_width=True)

with tab2:
    text_description = st.text_area("Meal description", placeholder="e.g., Grilled chicken breast with rice")

# --- AI ANALYSIS AND LOGGING ---
PROMPT = """
Analyze the meal and provide estimates. Response MUST strictly start with these lines:
Name: <short meal name>
Calories: <number>
Protein: <number>
Carbs: <number>
Fats: <number>

Followed by a brief explanation.
"""

if st.button("Log Meal 🚀"):
    if not image and not text_description.strip():
        st.error("Please upload an image or type a description.")
    else:
        with st.spinner("Analyzing and updating progress..."):
            inputs = [PROMPT]
            if text_description.strip():
                inputs.append(f"Description: {text_description}")
            if image:
                inputs.append(image)

            try:
                response = model.generate_content(inputs)
                raw_text = response.text

                # Extract nutrient values
                cals = re.search(r"Calories:\s*(\d+)", raw_text)
                prot = re.search(r"Protein:\s*(\d+)", raw_text)
                carbs = re.search(r"Carbs:\s*(\d+)", raw_text)
                fats = re.search(r"Fats:\s*(\d+)", raw_text)
                name = re.search(r"Name:\s*(.+)", raw_text)

                meal_name = name.group(1).strip() if name else "Logged Meal"
                c_val = float(cals.group(1)) if cals else 0.0
                p_val = float(prot.group(1)) if prot else 0.0
                cb_val = float(carbs.group(1)) if carbs else 0.0
                f_val = float(fats.group(1)) if fats else 0.0

                save_meal(meal_name, c_val, p_val, cb_val, f_val)
                st.success(f"Logged: {meal_name} ({int(c_val)} kcal)")
                st.rerun()

            except Exception as e:
                st.error(f"Error analyzing meal: {e}")

with tab3:
    history = get_history()
    if history:
        for date, meal, c, p, cb, f in history:
            st.write(f"**{date}** | {meal} — **{int(c)} kcal** (P: {int(p)}g | C: {int(cb)}g | F: {int(f)}g)")
    else:
        st.info("No meals logged yet.")
  
