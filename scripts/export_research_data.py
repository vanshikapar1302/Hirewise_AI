import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from sqlalchemy import create_engine

# Set professional research styles using standard matplotlib
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'figure.titlesize': 14,
    'figure.dpi': 300
})

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = BASE_DIR / "exports"
GRAPH_DIR = EXPORT_DIR / "graphs"
EXPORT_DIR.mkdir(exist_ok=True)
GRAPH_DIR.mkdir(exist_ok=True)

def get_db_connection():
    """Returns a SQLAlchemy engine connecting to PostgreSQL (from env)."""
    # Check .env first
    env_path = BASE_DIR / ".env"
    db_uri = None
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    db_uri = line.split("DATABASE_URL=")[1].strip()
                    break
    
    if not db_uri:
        db_uri = os.environ.get("DATABASE_URL")

    if not db_uri:
        raise ValueError("[ERROR] DATABASE_URL is missing. SQLite fallback is disabled by configuration rules.")

    # Normalize postgres protocol for SQLAlchemy
    if db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
        
    masked_uri = db_uri
    if "@" in db_uri:
        masked_uri = db_uri.split("@")[-1]
    print(f"[INFO] Using Supabase PostgreSQL URL from .env: postgresql://*****@{masked_uri}")
    return create_engine(db_uri)

def load_data(engine):
    """Loads all relevant tables from the database into Pandas DataFrames."""
    tables = [
        "users", "resume_uploads", "interview_sessions", 
        "responses", "questions", "session_skill_states", 
        "session_skill_history", "performance_reports", 
        "chat_sessions", "chat_messages", "practice_history"
    ]
    data = {}
    for table in tables:
        try:
            data[table] = pd.read_sql_table(table, engine)
            print(f"[SUCCESS] Loaded table '{table}' with {len(data[table])} rows.")
        except Exception as e:
            print(f"[WARNING] Could not load table '{table}': {e}")
            data[table] = pd.DataFrame()
    return data

def flatten_json_telemetry(sessions_df):
    """Flattens the JSON decision_log and competency_map from interview_sessions."""
    decision_records = []
    competency_records = []
    inflation_records = []
    mismatch_records = []
    convergence_telemetry_records = []
    convergence_records = []

    for _, row in sessions_df.iterrows():
        sess_id = row['id']
        u_id = row['user_id']
        mode = row.get('experiment_mode', 'fixed')

        # 1. Parse decision log (Fisher Information and selection reasons per turn)
        dec_log = row.get('decision_log')
        if dec_log and isinstance(dec_log, str) and dec_log.strip():
            try:
                log_data = json.loads(dec_log)
                for entry in log_data:
                    entry['session_id'] = sess_id
                    entry['user_id'] = u_id
                    entry['experiment_mode'] = mode
                    decision_records.append(entry)
            except Exception as e:
                print(f"[WARNING] Error parsing decision log for session {sess_id}: {e}")

        # 2. Parse competency map (skill bounds and uncertainties)
        comp_map = row.get('competency_map')
        if comp_map and isinstance(comp_map, str) and comp_map.strip():
            try:
                map_data = json.loads(comp_map)
                for skill_name, meta in map_data.items():
                    if skill_name in ["resume_inflation_analysis", "multimodal_convergence_telemetry", "multimodal_convergence_analysis", "project_inputs", "project_understanding", "project_feedback", "project_all_question_ids"]:
                        continue
                    competency_records.append({
                        "session_id": sess_id,
                        "user_id": u_id,
                        "experiment_mode": mode,
                        "skill_name": skill_name,
                        "estimated_score": meta.get("score") if isinstance(meta, dict) else None,
                        "uncertainty_sigma": meta.get("uncertainty") if isinstance(meta, dict) else None,
                        "confidence_level": meta.get("confidence_level") if isinstance(meta, dict) else None,
                        "inferred_boundary": meta.get("boundary") if isinstance(meta, dict) else None
                    })
                
                # Parse resume inflation score and details
                inflation_data = map_data.get("resume_inflation_analysis")
                if inflation_data:
                    inflation_records.append({
                        "session_id": sess_id,
                        "user_id": u_id,
                        "experiment_mode": mode,
                        "resume_inflation_score": inflation_data.get("resume_inflation_score", 0.0),
                        "explainability_log": "\n".join(inflation_data.get("explainability_log", []))
                    })
                    for mismatch in inflation_data.get("skills_mismatch", []):
                        mismatch_records.append({
                            "session_id": sess_id,
                            "user_id": u_id,
                            "experiment_mode": mode,
                            "skill_name": mismatch.get("skill_name"),
                            "claimed_level": mismatch.get("claimed_level"),
                            "estimated_level": mismatch.get("estimated_level"),
                            "estimated_score": mismatch.get("estimated_score"),
                            "mismatch_percentage": mismatch.get("mismatch_percentage"),
                            "justification": mismatch.get("justification")
                        })
                
                # Parse multimodal convergence telemetry and analysis
                telemetry_list = map_data.get("multimodal_convergence_telemetry", [])
                for turn in telemetry_list:
                    convergence_telemetry_records.append({
                        "session_id": sess_id,
                        "user_id": u_id,
                        "experiment_mode": mode,
                        "turn_number": turn.get("turn_number"),
                        "sigma_before": turn.get("sigma_before"),
                        "sigma_after": turn.get("sigma_after"),
                        "sigma_change": turn.get("sigma_change"),
                        "confidence_signal": turn.get("confidence_signal"),
                        "eye_contact_score": turn.get("eye_contact_score"),
                        "filler_count": turn.get("filler_count"),
                        "speech_confidence": turn.get("speech_confidence"),
                        "attention_duration": turn.get("attention_duration"),
                        "head_stability": turn.get("head_stability")
                    })
                
                analysis_data = map_data.get("multimodal_convergence_analysis")
                if analysis_data:
                    convergence_records.append({
                        "session_id": sess_id,
                        "user_id": u_id,
                        "experiment_mode": mode,
                        "total_questions_until_sigma_stabilizes": analysis_data.get("total_questions_until_sigma_stabilizes"),
                        "average_sigma_reduction_per_turn": analysis_data.get("average_sigma_reduction_per_turn"),
                        "confidence_category": analysis_data.get("confidence_category"),
                        "convergence_category": analysis_data.get("convergence_category"),
                        "average_confidence_signal": analysis_data.get("average_confidence_signal")
                    })
            except Exception as e:
                print(f"[WARNING] Error parsing competency map for session {sess_id}: {e}")

    dec_df = pd.DataFrame(decision_records)
    comp_df = pd.DataFrame(competency_records)
    
    inflation_df = pd.DataFrame(inflation_records)
    if inflation_df.empty:
        inflation_df = pd.DataFrame(columns=["session_id", "user_id", "experiment_mode", "resume_inflation_score", "explainability_log"])
        
    mismatch_df = pd.DataFrame(mismatch_records)
    if mismatch_df.empty:
        mismatch_df = pd.DataFrame(columns=["session_id", "user_id", "experiment_mode", "skill_name", "claimed_level", "estimated_level", "estimated_score", "mismatch_percentage", "justification"])
        
    conv_tel_df = pd.DataFrame(convergence_telemetry_records)
    if conv_tel_df.empty:
        conv_tel_df = pd.DataFrame(columns=["session_id", "user_id", "experiment_mode", "turn_number", "sigma_before", "sigma_after", "sigma_change", "confidence_signal", "eye_contact_score", "filler_count", "speech_confidence", "attention_duration", "head_stability"])
        
    conv_df = pd.DataFrame(convergence_records)
    if conv_df.empty:
        conv_df = pd.DataFrame(columns=["session_id", "user_id", "experiment_mode", "total_questions_until_sigma_stabilizes", "average_sigma_reduction_per_turn", "confidence_category", "convergence_category", "average_confidence_signal"])
    
    return dec_df, comp_df, inflation_df, mismatch_df, conv_tel_df, conv_df

def run_statistical_analysis(data, dec_df, comp_df, inflation_df=None, mismatch_df=None, conv_tel_df=None, conv_df=None):
    """Computes statistical metrics (correlations, learning curves, group comparisons) for research."""
    stats = {}
    
    # Analysis 1: Communication vs Technical Score Correlation
    sessions = data["interview_sessions"]
    if not sessions.empty and "communication_score" in sessions.columns and "technical_score" in sessions.columns:
        valid_sess = sessions[sessions['status'] == 'completed']
        if len(valid_sess) > 1:
            corr = valid_sess['communication_score'].corr(valid_sess['technical_score'])
            stats["comm_tech_correlation"] = corr
            print(f"[STAT] Pearson Correlation (Comm vs Tech): {corr:.3f}")

    # Analysis 2: Performance metrics across Experiment Modes
    if not sessions.empty and "experiment_mode" in sessions.columns and "overall_score" in sessions.columns:
        valid_sess = sessions[sessions['status'] == 'completed']
        group_means = valid_sess.groupby('experiment_mode')['overall_score'].agg(['count', 'mean', 'std']).reset_index()
        stats["experiment_modes_summary"] = group_means
        print("\n[STAT] Overall Score Summary by Experiment Mode:")
        print(group_means.to_string())

    # Analysis 3: Fisher Information and Uncertainty over Interview Turns
    if not dec_df.empty and "question_index" in dec_df.columns and "uncertainty_sigma" in dec_df.columns:
        turn_summary = dec_df.groupby(['experiment_mode', 'question_index']).agg({
            'uncertainty_sigma': 'mean',
            'fisher_information': 'mean'
        }).reset_index()
        stats["telemetry_by_turn"] = turn_summary
        print("\n[STAT] Turn-by-Turn Telemetry Averaged:")
        print(turn_summary.to_string())

    # Analysis 4: Resume Inflation Summary Statistics
    if inflation_df is not None and not inflation_df.empty:
        inf_summary = inflation_df.groupby('experiment_mode')['resume_inflation_score'].agg(['count', 'mean', 'std', 'min', 'max']).reset_index()
        stats["resume_inflation_summary"] = inf_summary
        print("\n[STAT] Resume Inflation Summary Statistics:")
        print(inf_summary.to_string())

    # Analysis 5: Multimodal Convergence Analysis Summary
    if conv_df is not None and not conv_df.empty:
        conv_summary = conv_df.groupby('confidence_category')['total_questions_until_sigma_stabilizes'].agg(['count', 'mean', 'std']).reset_index()
        stats["convergence_summary"] = conv_summary
        print("\n[STAT] Total Questions Until Sigma Stabilizes by Confidence Category:")
        print(conv_summary.to_string())
        
        if len(conv_df) > 1 and "average_confidence_signal" in conv_df.columns:
            corr = conv_df['average_confidence_signal'].corr(conv_df['total_questions_until_sigma_stabilizes'])
            stats["confidence_vs_stabilization_corr"] = corr
            print(f"[STAT] Pearson Correlation (Confidence Signal vs Questions Needed to Stabilize): {corr:.3f}")

    return stats

def generate_visualizations(data, dec_df, comp_df, inflation_df=None, mismatch_df=None, conv_tel_df=None, conv_df=None):
    """Generates research-ready visual figures for the paper and saves them as PNGs."""
    print("\n[INFO] Generating research visualizations...")
    
    # Plot 1: Bayesian Uncertainty Convergence Rate over Turns
    if not dec_df.empty and "question_index" in dec_df.columns and "uncertainty_sigma" in dec_df.columns:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for name, group in dec_df.groupby("experiment_mode"):
            # Group by turn and calculate mean
            gp = group.groupby("question_index")["uncertainty_sigma"].mean().reset_index()
            ax.plot(gp["question_index"], gp["uncertainty_sigma"], marker="o", label=name, linewidth=2)
        ax.set_title("Bayesian Competency Estimation: Uncertainty ($\\sigma$) Convergence Rate")
        ax.set_xlabel("Interview Turn (Question Index)")
        ax.set_ylabel("Estimation Uncertainty Standard Error ($\\sigma$)")
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        plt.savefig(GRAPH_DIR / "competency_uncertainty_convergence.png", dpi=300)
        plt.close()
        print("[VISUAL] Saved: competency_uncertainty_convergence.png")
 
    # Plot 2: Fisher Information by Turn
    if not dec_df.empty and "question_index" in dec_df.columns and "fisher_information" in dec_df.columns:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for name, group in dec_df.groupby("experiment_mode"):
            gp = group.groupby("question_index")["fisher_information"].mean().reset_index()
            ax.plot(gp["question_index"], gp["fisher_information"], marker="s", label=name, linewidth=2)
        ax.set_title("Fisher Information Optimization per Turn")
        ax.set_xlabel("Interview Turn")
        ax.set_ylabel("Fisher Information value ($I(\\theta)$)")
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        plt.savefig(GRAPH_DIR / "fisher_information_by_turn.png", dpi=300)
        plt.close()
        print("[VISUAL] Saved: fisher_information_by_turn.png")
 
    # Plot 3: Boxplot comparing Overall Scores between Adaptive and Control Groups
    sessions = data["interview_sessions"]
    if not sessions.empty and "experiment_mode" in sessions.columns and "overall_score" in sessions.columns:
        completed_sessions = sessions[sessions['status'] == 'completed']
        if len(completed_sessions) > 0:
            fig, ax = plt.subplots(figsize=(6, 5))
            groups = completed_sessions.groupby("experiment_mode")
            box_data = [group["overall_score"].values for name, group in groups]
            labels = [name for name, group in groups]
            
            bp = ax.boxplot(box_data, patch_artist=True, widths=0.4)
            ax.set_xticklabels(labels)
            for patch in bp['boxes']:
                patch.set_facecolor('#d9f0a3')
                patch.set_alpha(0.8)
                
            # Plot individual data points as scatter for scientific visualization
            for i, (name, group) in enumerate(groups):
                y = group["overall_score"].values
                x = np.random.normal(i + 1, 0.04, size=len(y))
                ax.scatter(x, y, alpha=0.6, color="black", edgecolor="none", s=30)
                
            ax.set_title("Candidate Overall Performance Across Selection Policies")
            ax.set_xlabel("Orchestration Mode")
            ax.set_ylabel("Overall Interview Rating (%)")
            ax.grid(True, linestyle="--", alpha=0.6)
            plt.tight_layout()
            plt.savefig(GRAPH_DIR / "overall_score_comparison.png", dpi=300)
            plt.close()
            print("[VISUAL] Saved: overall_score_comparison.png")
 
    # Plot 4: Correlation Matrix Heatmap
    if not sessions.empty:
        score_cols = [c for c in ["communication_score", "technical_score", "confidence_score", "answer_quality_score", "professionalism_score", "overall_score"] if c in sessions.columns]
        completed_sessions = sessions[sessions['status'] == 'completed']
        if len(completed_sessions) > 1 and len(score_cols) > 1:
            fig, ax = plt.subplots(figsize=(7, 6))
            corr_mat = completed_sessions[score_cols].corr()
            im = ax.imshow(corr_mat.values, cmap="coolwarm", vmin=-1, vmax=1)
            
            # Add annotations
            for i in range(len(score_cols)):
                for j in range(len(score_cols)):
                    ax.text(j, i, f"{corr_mat.values[i, j]:.2f}", ha="center", va="center", color="black" if abs(corr_mat.values[i, j]) < 0.7 else "white")
            
            ax.set_xticks(np.arange(len(score_cols)))
            ax.set_yticks(np.arange(len(score_cols)))
            ax.set_xticklabels([c.replace("_", "\n") for c in score_cols])
            ax.set_yticklabels([c.replace("_", " ") for c in score_cols])
            fig.colorbar(im, ax=ax, shrink=0.8)
            ax.set_title("Correlation Matrix of Extracted Interview Ratings")
            plt.tight_layout()
            plt.savefig(GRAPH_DIR / "interview_dimensions_correlation.png", dpi=300)
            plt.close()
            print("[VISUAL] Saved: interview_dimensions_correlation.png")

    # Plot 5: Distribution of Resume Inflation Scores
    if inflation_df is not None and not inflation_df.empty and "resume_inflation_score" in inflation_df.columns:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        scores = inflation_df["resume_inflation_score"]
        ax.hist(scores, bins=np.arange(0, 105, 10), color="#8dd3c7", edgecolor="#555555", alpha=0.8, rwidth=0.8)
        ax.set_title("Distribution of Candidate Resume Inflation Scores")
        ax.set_xlabel("Resume Inflation Score (0 - 100)")
        ax.set_ylabel("Count of Candidates")
        ax.set_xlim(-5, 105)
        ax.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        plt.savefig(GRAPH_DIR / "resume_inflation_distribution.png", dpi=300)
        plt.close()
        print("[VISUAL] Saved: resume_inflation_distribution.png")

    # Plot 6: Claimed Skill vs. Estimated Skill Bubble Plot
    if mismatch_df is not None and not mismatch_df.empty and "claimed_level" in mismatch_df.columns and "estimated_level" in mismatch_df.columns:
        level_map = {"Beginner": 1, "Intermediate": 2, "Advanced": 3, "Expert": 3}
        plot_df = mismatch_df.copy()
        plot_df["claimed_val"] = plot_df["claimed_level"].map(level_map)
        plot_df["estimated_val"] = plot_df["estimated_level"].map(level_map)
        
        plot_df = plot_df.dropna(subset=["claimed_val", "estimated_val"])
        if not plot_df.empty:
            counts_df = plot_df.groupby(["claimed_val", "estimated_val"]).size().reset_index(name="count")
            
            fig, ax = plt.subplots(figsize=(7, 6))
            ax.scatter(
                counts_df["claimed_val"],
                counts_df["estimated_val"],
                s=counts_df["count"] * 100,
                color="#bebada",
                edgecolor="#555555",
                alpha=0.8,
                label="Candidate Count"
            )
            
            # Add labels to bubbles
            for _, r in counts_df.iterrows():
                ax.text(
                    r["claimed_val"],
                    r["estimated_val"],
                    str(int(r["count"])),
                    ha="center",
                    va="center",
                    color="black",
                    fontweight="bold"
                )
                
            ax.set_title("Claimed Skill Level vs. Measured Competency Level")
            ax.set_xlabel("Claimed Skill Level (Resume)")
            ax.set_ylabel("Measured Competency Level (Interview)")
            
            ax.set_xticks([1, 2, 3])
            ax.set_xticklabels(["Beginner", "Intermediate", "Expert/Advanced"])
            ax.set_yticks([1, 2, 3])
            ax.set_yticklabels(["Beginner", "Intermediate", "Advanced"])
            
            ax.plot([0.5, 3.5], [0.5, 3.5], color="red", linestyle="--", alpha=0.5, label="Perfect Match")
            
            ax.set_xlim(0.5, 3.5)
            ax.set_ylim(0.5, 3.5)
            ax.grid(True, linestyle=":", alpha=0.5)
            ax.legend(loc="upper left")
            
            plt.tight_layout()
            plt.savefig(GRAPH_DIR / "claimed_vs_estimated_comparison.png", dpi=300)
            plt.close()
            print("[VISUAL] Saved: claimed_vs_estimated_comparison.png")

    # Plot 7: sigma_convergence_curves.png
    if conv_tel_df is not None and not conv_tel_df.empty and conv_df is not None and not conv_df.empty:
        merged_df = pd.merge(conv_tel_df, conv_df[['session_id', 'confidence_category']], on='session_id')
        if not merged_df.empty:
            fig, ax = plt.subplots(figsize=(7, 4.5))
            colors = {"High Confidence": "#1b9e77", "Medium Confidence": "#7570b3", "Low Confidence": "#d95f02"}
            
            for category, group in merged_df.groupby("confidence_category"):
                gp = group.groupby("turn_number")["sigma_after"].mean().reset_index()
                ax.plot(gp["turn_number"], gp["sigma_after"], marker="o", color=colors.get(category, "blue"), label=category, linewidth=2)
                
            ax.set_title("Bayesian Uncertainty ($\\sigma$) Convergence Curves")
            ax.set_xlabel("Interview Turn (Question Number)")
            ax.set_ylabel("Estimation Standard Error ($\\sigma$)")
            ax.legend()
            ax.grid(True, linestyle="--", alpha=0.6)
            plt.tight_layout()
            plt.savefig(GRAPH_DIR / "sigma_convergence_curves.png", dpi=300)
            plt.close()
            print("[VISUAL] Saved: sigma_convergence_curves.png")

    # Plot 8: confidence_vs_questions_needed.png
    if conv_df is not None and not conv_df.empty:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        cat_means = conv_df.groupby("confidence_category")["total_questions_until_sigma_stabilizes"].mean().reindex(["Low Confidence", "Medium Confidence", "High Confidence"]).fillna(0)
        
        colors = ["#d95f02", "#7570b3", "#1b9e77"]
        bars = ax.bar(cat_means.index, cat_means.values, color=colors, edgecolor="#555555", width=0.5, alpha=0.8)
        
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.2f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontweight='bold')
                        
        ax.set_title("Average Questions Needed for Sigma to Stabilize")
        ax.set_xlabel("Confidence Category")
        ax.set_ylabel("Questions Needed (Turns)")
        ax.set_ylim(0, (max(cat_means.values) if len(cat_means.values) > 0 else 5) + 1.5)
        ax.grid(True, linestyle="--", alpha=0.6, axis='y')
        plt.tight_layout()
        plt.savefig(GRAPH_DIR / "confidence_vs_questions_needed.png", dpi=300)
        plt.close()
        print("[VISUAL] Saved: confidence_vs_questions_needed.png")

    # Plot 9: confidence_vs_sigma_reduction.png
    if conv_df is not None and not conv_df.empty:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        cat_means = conv_df.groupby("confidence_category")["average_sigma_reduction_per_turn"].mean().reindex(["Low Confidence", "Medium Confidence", "High Confidence"]).fillna(0)
        
        colors = ["#d95f02", "#7570b3", "#1b9e77"]
        bars = ax.bar(cat_means.index, cat_means.values, color=colors, edgecolor="#555555", width=0.5, alpha=0.8)
        
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.3f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontweight='bold')
                        
        ax.set_title("Average Sigma Reduction Rate per Turn")
        ax.set_xlabel("Confidence Category")
        ax.set_ylabel("Mean Sigma Reduction per Turn")
        ax.set_ylim(0, (max(cat_means.values) if len(cat_means.values) > 0 else 2.0) * 1.3)
        ax.grid(True, linestyle="--", alpha=0.6, axis='y')
        plt.tight_layout()
        plt.savefig(GRAPH_DIR / "confidence_vs_sigma_reduction.png", dpi=300)
        plt.close()
        print("[VISUAL] Saved: confidence_vs_sigma_reduction.png")

def save_to_excel(data, dec_df, comp_df, stats, inflation_df=None, mismatch_df=None, conv_tel_df=None, conv_df=None):
    """Exports all datasets and flattened tables into a single formatted Excel workbook."""
    excel_path = EXPORT_DIR / "hirewise_research_data.xlsx"
    print(f"\n[INFO] Exporting sheets to Excel: {excel_path}")
    
    # We require openpyxl
    try:
        import openpyxl
    except ImportError:
        print("[WARNING] openpyxl not installed. Attempting installation...")
        import subprocess
        subprocess.run(["pip", "install", "openpyxl"], stdout=subprocess.DEVNULL)
        
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        # Base database tables
        for tab_name, df in data.items():
            if not df.empty:
                # Truncate large texts for readability
                df_clean = df.copy()
                for col in df_clean.select_dtypes(include=['object']).columns:
                    df_clean[col] = df_clean[col].astype(str).str.slice(0, 1000)
                df_clean.to_excel(writer, sheet_name=tab_name[:30], index=False)
        
        # Derived flattened research telemetry sheets
        if not dec_df.empty:
            dec_df.to_excel(writer, sheet_name="Turn_Decision_Log", index=False)
        if not comp_df.empty:
            comp_df.to_excel(writer, sheet_name="Candidate_Competencies", index=False)
            
        # Save resume inflation DataFrames
        if inflation_df is not None and not inflation_df.empty:
            inflation_df.to_excel(writer, sheet_name="Resume_Inflation_Overview", index=False)
        if mismatch_df is not None and not mismatch_df.empty:
            mismatch_df.to_excel(writer, sheet_name="Skill_Mismatches", index=False)
            
        # Save multimodal convergence DataFrames
        if conv_tel_df is not None and not conv_tel_df.empty:
            conv_tel_df.to_excel(writer, sheet_name="Convergence_Analysis", index=False)
        if conv_df is not None and not conv_df.empty:
            conv_df.to_excel(writer, sheet_name="Confidence_vs_Convergence", index=False)
            
        # Analysis stats summary
        if "experiment_modes_summary" in stats:
            stats["experiment_modes_summary"].to_excel(writer, sheet_name="Experiment_Mode_Stats", index=False)
        if "telemetry_by_turn" in stats:
            stats["telemetry_by_turn"].to_excel(writer, sheet_name="Turn_Telemetry_Stats", index=False)
        if "resume_inflation_summary" in stats:
            stats["resume_inflation_summary"].to_excel(writer, sheet_name="Resume_Inflation_Stats", index=False)
        if "convergence_summary" in stats:
            stats["convergence_summary"].to_excel(writer, sheet_name="Convergence_Summary_Stats", index=False)
            
    print(f"[SUCCESS] Research dataset exported successfully!")
 
def main():
    print("=" * 60)
    print("      HIREWISE AI RESEARCH DATA EXPORT & ANALYTICS TOOL      ")
    print("=" * 60)
    
    try:
        engine = get_db_connection()
        data = load_data(engine)
        
        # Flatten complex JSON telemetry columns
        sessions_df = data.get("interview_sessions", pd.DataFrame())
        if not sessions_df.empty:
            dec_df, comp_df, inflation_df, mismatch_df, conv_tel_df, conv_df = flatten_json_telemetry(sessions_df)
        else:
            dec_df, comp_df = pd.DataFrame(), pd.DataFrame()
            inflation_df = pd.DataFrame(columns=["session_id", "user_id", "experiment_mode", "resume_inflation_score", "explainability_log"])
            mismatch_df = pd.DataFrame(columns=["session_id", "user_id", "experiment_mode", "skill_name", "claimed_level", "estimated_level", "estimated_score", "mismatch_percentage", "justification"])
            conv_tel_df = pd.DataFrame(columns=["session_id", "user_id", "experiment_mode", "turn_number", "sigma_before", "sigma_after", "sigma_change", "confidence_signal", "eye_contact_score", "filler_count", "speech_confidence", "attention_duration", "head_stability"])
            conv_df = pd.DataFrame(columns=["session_id", "user_id", "experiment_mode", "total_questions_until_sigma_stabilizes", "average_sigma_reduction_per_turn", "confidence_category", "convergence_category", "average_confidence_signal"])
            
        # Run analysis and plot graphs
        stats = run_statistical_analysis(data, dec_df, comp_df, inflation_df, mismatch_df, conv_tel_df, conv_df)
        generate_visualizations(data, dec_df, comp_df, inflation_df, mismatch_df, conv_tel_df, conv_df)
        
        # Save structured workbook
        save_to_excel(data, dec_df, comp_df, stats, inflation_df, mismatch_df, conv_tel_df, conv_df)
        print("=" * 60)
        print(f"Audit completed. Data files stored in: {EXPORT_DIR.resolve()}")
        print("=" * 60)
    except Exception as e:
        import traceback
        traceback.print_exc()
 
if __name__ == "__main__":
    main()
